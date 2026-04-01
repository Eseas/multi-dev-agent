#!/usr/bin/env python3
"""Interactive CLI for multi-agent development system.

방향키(↑↓)와 Enter로 모든 조작이 가능한 인터랙티브 CLI.

사용법:
    python cli.py            # 인터랙티브 모드 (기본)
    python cli.py run -s ... # 레거시 arg 모드
"""

from __future__ import annotations

import json
import logging
import os
import select
import sys
import threading
import tty
import termios
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

# 라이브러리 로그 억제
logging.basicConfig(level=logging.WARNING)

# ─── ANSI ────────────────────────────────────────────────────────────────────

RST   = '\033[0m'
BOLD  = '\033[1m'
DIM   = '\033[2m'
RED   = '\033[91m'
GRN   = '\033[92m'
YLW   = '\033[93m'
BLU   = '\033[94m'
CYN   = '\033[96m'
SEL   = '\033[48;5;237m'   # 선택 배경 (dark grey)
SEL2  = '\033[48;5;24m'    # 옵션 선택 배경 (dark blue)

def _hide_cursor():  sys.stdout.write('\033[?25l'); sys.stdout.flush()
def _show_cursor():  sys.stdout.write('\033[?25h'); sys.stdout.flush()
def _home():         sys.stdout.write('\033[H');    sys.stdout.flush()
def _clear():        sys.stdout.write('\033[2J\033[H'); sys.stdout.flush()
def _clear_below():  sys.stdout.write('\033[J');    sys.stdout.flush()


# ─── CJK 문자폭 ──────────────────────────────────────────────────────────────

def _cjk_width(s: str) -> int:
    """터미널 표시 너비 계산 (한글/한자 = 2칸)."""
    w = 0
    for ch in s:
        cp = ord(ch)
        if (0xAC00 <= cp <= 0xD7AF or   # 한글 음절
                0x1100 <= cp <= 0x11FF or   # 한글 자모
                0x2E80 <= cp <= 0x9FFF or   # CJK
                0xF900 <= cp <= 0xFAFF or
                0xFF00 <= cp <= 0xFFEF):
            w += 2
        else:
            w += 1
    return w


def _pad(s: str, width: int) -> str:
    """표시 너비에 맞춰 오른쪽 공백 패딩."""
    cur = _cjk_width(s)
    return s + ' ' * max(0, width - cur)


# ─── 키 입력 ─────────────────────────────────────────────────────────────────

class KeyReader:
    """원시(raw) 터미널 키 입력 리더."""

    def read_raw(self) -> str:
        """단일 키 읽기 (블로킹). 키 이름 문자열 반환."""
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = os.read(fd, 1)

            if ch == b'\x1b':
                # 이스케이프 시퀀스 처리 (짧은 타임아웃)
                r, _, _ = select.select([sys.stdin], [], [], 0.05)
                if r:
                    ch2 = os.read(fd, 1)
                    if ch2 == b'[':
                        r2, _, _ = select.select([sys.stdin], [], [], 0.05)
                        if r2:
                            ch3 = os.read(fd, 1)
                            if ch3 == b'A': return 'UP'
                            if ch3 == b'B': return 'DOWN'
                            if ch3 == b'C': return 'RIGHT'
                            if ch3 == b'D': return 'LEFT'
                return 'ESC'

            if ch in (b'\r', b'\n'): return 'ENTER'
            if ch == b'\x03':        return 'CTRL_C'
            if ch in (b'\x7f', b'\x08'): return 'BACKSPACE'
            if ch == b'\t':          return 'TAB'

            try:
                return ch.decode('utf-8')
            except Exception:
                return ''
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    def read(self, timeout: float = 0.1) -> Optional[str]:
        """논블로킹 읽기. timeout 내 입력 없으면 None 반환."""
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        return self.read_raw() if r else None


# ─── 상태 ─────────────────────────────────────────────────────────────────────

ST_MAIN    = 'main'
ST_SPEC    = 'spec'
ST_RUN     = 'running'
ST_DONE    = 'done'
ST_STATUS  = 'status'
ST_QUIT    = 'quit'

# 메인 메뉴 항목
MAIN_ITEMS: List[Tuple[str, str]] = [
    ('run',    '  파이프라인 실행'),
    ('status', '  작업 상태 보기'),
    ('quit',   '  종료'),
]


# ─── CLI ─────────────────────────────────────────────────────────────────────

class InteractiveCLI:
    """방향키 + Enter로 제어하는 오케스트레이터 CLI."""

    def __init__(self, config_path: Path = Path('config.yaml')):
        self.config_path = config_path
        self.keys = KeyReader()
        self.state = ST_MAIN

        # 메인 메뉴
        self.main_sel = 0

        # 기획서 선택
        self.spec_files: List[Path] = []
        self.spec_sel = 0

        # 파이프라인
        self.current_spec: Optional[Path] = None
        self.orchestrator = None
        self._pipeline_thread: Optional[threading.Thread] = None
        self._pipeline_result: Optional[dict] = None
        self._pipeline_error: Optional[str] = None
        self._pipeline_start: Optional[float] = None

        # 질문 UI
        self.q_sel = 0          # 질문 목록 인덱스 (복수 질문 시)
        self.opt_sel = 0        # 선택지 인덱스
        self.text_mode = False  # True = 자유 텍스트 입력 중
        self.text_buf = ''

        # 상태 화면
        self.status_items: List[dict] = []
        self.status_sel = 0

    # ─── 메인 루프 ────────────────────────────────────────────────────────────

    def run(self):
        """인터랙티브 루프 시작."""
        _hide_cursor()
        _clear()
        try:
            while self.state != ST_QUIT:
                key = self.keys.read(timeout=0.1)
                if key:
                    self._dispatch(key)
                self._render()
        except KeyboardInterrupt:
            pass
        finally:
            _clear()
            _show_cursor()
            if self._pipeline_thread and self._pipeline_thread.is_alive():
                print(f'{YLW}파이프라인이 백그라운드에서 실행 중입니다.{RST}')

    # ─── 키 디스패치 ──────────────────────────────────────────────────────────

    def _dispatch(self, key: str):
        if key == 'CTRL_C':
            self.state = ST_QUIT
            return
        {
            ST_MAIN:   self._key_main,
            ST_SPEC:   self._key_spec,
            ST_RUN:    self._key_run,
            ST_DONE:   self._key_done,
            ST_STATUS: self._key_status,
        }.get(self.state, lambda k: None)(key)

    def _key_main(self, key: str):
        n = len(MAIN_ITEMS)
        if key == 'UP':
            self.main_sel = (self.main_sel - 1) % n
        elif key == 'DOWN':
            self.main_sel = (self.main_sel + 1) % n
        elif key in ('ENTER', ' '):
            action = MAIN_ITEMS[self.main_sel][0]
            if action == 'run':
                self._enter_spec()
            elif action == 'status':
                self._enter_status()
            elif action == 'quit':
                self.state = ST_QUIT
        elif key == 'q':
            self.state = ST_QUIT

    def _key_spec(self, key: str):
        n = len(self.spec_files)
        if n == 0:
            if key in ('q', 'ESC'): self.state = ST_MAIN
            return
        if key == 'UP':
            self.spec_sel = (self.spec_sel - 1) % n
        elif key == 'DOWN':
            self.spec_sel = (self.spec_sel + 1) % n
        elif key == 'ENTER':
            self.current_spec = self.spec_files[self.spec_sel]
            self._start_pipeline()
        elif key in ('q', 'ESC'):
            self.state = ST_MAIN

    def _key_run(self, key: str):
        """파이프라인 실행 중 키 처리."""
        orc = self.orchestrator
        if not orc or not orc.question_queue:
            return

        pending = orc.question_queue.get_pending()
        if not pending:
            return

        self.q_sel = min(self.q_sel, len(pending) - 1)
        q = pending[self.q_sel]

        if self.text_mode:
            # 자유 텍스트 입력 모드
            if key == 'ENTER':
                if self.text_buf.strip():
                    orc.question_queue.answer(q.id, self.text_buf.strip())
                    self.text_buf = ''
                    self.text_mode = False
                    self.q_sel = 0
                    self.opt_sel = 0
            elif key == 'BACKSPACE':
                self.text_buf = self.text_buf[:-1]
            elif key == 'ESC':
                self.text_mode = False
                self.text_buf = ''
            elif len(key) == 1:
                self.text_buf += key
        else:
            # 네비게이션 모드
            if key == 'UP':
                if q.options:
                    self.opt_sel = (self.opt_sel - 1) % len(q.options)
                else:
                    self.q_sel = (self.q_sel - 1) % max(1, len(pending))
            elif key == 'DOWN':
                if q.options:
                    self.opt_sel = (self.opt_sel + 1) % len(q.options)
                else:
                    self.q_sel = (self.q_sel + 1) % max(1, len(pending))
            elif key == 'ENTER':
                if q.options:
                    orc.question_queue.answer(q.id, q.options[self.opt_sel])
                    self.opt_sel = 0
                    self.q_sel = 0
                else:
                    self.text_mode = True
                    self.text_buf = ''
            elif key in ('1', '2', '3', '4', '5'):
                idx = int(key) - 1
                if q.options and idx < len(q.options):
                    orc.question_queue.answer(q.id, q.options[idx])
                    self.opt_sel = 0
                    self.q_sel = 0

    def _key_done(self, key: str):
        if key in ('q', 'ESC', 'ENTER'):
            self.state = ST_MAIN
            self._pipeline_result = None
            self._pipeline_error = None
            self.orchestrator = None

    def _key_status(self, key: str):
        n = len(self.status_items)
        if key == 'UP':
            self.status_sel = max(0, self.status_sel - 1)
        elif key == 'DOWN':
            self.status_sel = min(n - 1, self.status_sel + 1)
        elif key in ('q', 'ESC'):
            self.state = ST_MAIN

    # ─── 액션 ────────────────────────────────────────────────────────────────

    def _enter_spec(self):
        """기획서 파일 목록 로드 후 선택 화면으로."""
        specs: List[Path] = []
        for pattern in [
            'workspaces/**/planning/completed/*.md',
            'workspaces/**/planning/in-progress/*.md',
            'workspace/planning/completed/*.md',
            'workspace/planning/in-progress/*.md',
            'planning-spec.md',
            '**/planning-spec.md',
        ]:
            specs.extend(Path('.').glob(pattern))

        # 중복 제거, 수정 시간 역순 정렬
        seen: set = set()
        unique: List[Path] = []
        for s in sorted(specs, key=lambda p: p.stat().st_mtime, reverse=True):
            key = str(s.resolve())
            if key not in seen:
                seen.add(key)
                unique.append(s)

        self.spec_files = unique[:30]
        self.spec_sel = 0
        self.state = ST_SPEC

    def _start_pipeline(self):
        """오케스트레이터를 백그라운드 스레드에서 실행."""
        self.state = ST_RUN
        self._pipeline_result = None
        self._pipeline_error = None
        self._pipeline_start = time.time()
        self.q_sel = 0
        self.opt_sel = 0
        self.text_mode = False
        self.text_buf = ''

        def _run():
            try:
                from orchestrator.main import Orchestrator
                orc = Orchestrator(config_path=self.config_path)
                self.orchestrator = orc
                result = orc.run_from_spec(self.current_spec)
                self._pipeline_result = result
            except Exception as e:
                self._pipeline_error = str(e)
            finally:
                if self.state == ST_RUN:
                    self.state = ST_DONE

        self._pipeline_thread = threading.Thread(target=_run, daemon=True)
        self._pipeline_thread.start()

    def _enter_status(self):
        """작업 이력 로드."""
        items: List[dict] = []
        for manifest in sorted(
            list(Path('.').glob('workspaces/**/work/**/manifest.json')) +
            list(Path('.').glob('workspace/tasks/**/manifest.json')),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:20]:
            try:
                data = json.loads(manifest.read_text())
                items.append({
                    'task_id': data.get('task_id', manifest.parent.name),
                    'stage':   data.get('stage', '?'),
                    'created': data.get('created_at', ''),
                    'path':    str(manifest.parent),
                })
            except Exception:
                pass
        self.status_items = items
        self.status_sel = 0
        self.state = ST_STATUS

    # ─── 렌더링 ───────────────────────────────────────────────────────────────

    def _render(self):
        _home()
        out = {
            ST_MAIN:   self._draw_main,
            ST_SPEC:   self._draw_spec,
            ST_RUN:    self._draw_run,
            ST_DONE:   self._draw_done,
            ST_STATUS: self._draw_status,
        }.get(self.state, lambda: '')()
        sys.stdout.write(out)
        _clear_below()
        sys.stdout.flush()

    @staticmethod
    def _term_cols() -> int:
        try:
            return os.get_terminal_size().columns
        except OSError:
            return 80

    def _draw_main(self) -> str:
        W = min(self._term_cols() - 4, 52)
        lines = [
            '',
            f'{BOLD}{CYN}  ┌{"─" * W}┐{RST}',
            f'{BOLD}{CYN}  │{_pad("  Multi-Agent Development System", W)}│{RST}',
            f'{BOLD}{CYN}  └{"─" * W}┘{RST}',
            '',
        ]
        for i, (_, label) in enumerate(MAIN_ITEMS):
            if i == self.main_sel:
                inner = _pad(f'{BOLD}> {label}', W)
                lines.append(f'  {SEL}  {inner}  {RST}')
            else:
                inner = _pad(f'  {label}', W)
                lines.append(f'  {DIM}{inner}{RST}')
        lines += ['', f'  {DIM}↑↓ 이동  ·  Enter 선택  ·  q 종료{RST}']
        return '\n'.join(lines)

    def _draw_spec(self) -> str:
        W = min(self._term_cols() - 6, 70)
        lines = [
            '',
            f'  {BOLD}{BLU}기획서 선택{RST}',
            f'  {DIM}{"─" * 40}{RST}',
            '',
        ]
        if not self.spec_files:
            lines += [
                f'  {YLW}기획서(.md)를 찾을 수 없습니다.{RST}',
                f'  {DIM}planning/completed/ 디렉토리에 파일을 추가하세요.{RST}',
                '',
                f'  {DIM}ESC / q  →  뒤로{RST}',
            ]
            return '\n'.join(lines)

        for i, spec in enumerate(self.spec_files):
            try:
                label = str(spec.relative_to(Path('.')))
            except ValueError:
                label = str(spec)
            label = label[-W:] if len(label) > W else label
            if i == self.spec_sel:
                lines.append(f'  {SEL}{BOLD}> {_pad(label, W)}  {RST}')
            else:
                lines.append(f'  {DIM}  {_pad(label, W)}{RST}')

        lines += ['', f'  {DIM}↑↓ 이동  ·  Enter 실행  ·  ESC / q 뒤로{RST}']
        return '\n'.join(lines)

    def _draw_run(self) -> str:
        lines = ['']
        spec_name = self.current_spec.name if self.current_spec else '?'

        # 헤더
        elapsed = f'{time.time() - self._pipeline_start:.0f}s' if self._pipeline_start else ''
        lines.append(f'  {BOLD}{CYN}파이프라인 실행 중{RST}  {DIM}{spec_name}  {elapsed}{RST}')
        lines.append(f'  {DIM}{"─" * 50}{RST}')
        lines.append('')

        # 현재 단계
        stage_line = self._get_stage_line()
        lines.append(f'  {stage_line}')
        lines.append('')

        # 타임라인 최근 3줄
        for tl in self._get_timeline_tail(3):
            lines.append(f'  {DIM}{tl}{RST}')

        # 질문 섹션
        orc = self.orchestrator
        if orc and orc.question_queue:
            pending = orc.question_queue.get_pending()
            if pending:
                self.q_sel = min(self.q_sel, len(pending) - 1)
                q = pending[self.q_sel]

                lines += [
                    '',
                    f'  {YLW}{BOLD}{"─" * 50}{RST}',
                    f'  {YLW}{BOLD}❓ 질문{RST}'
                    + (f' [{self.q_sel + 1}/{len(pending)}]' if len(pending) > 1 else '')
                    + f'  {DIM}[{q.type.value}  {q.source}]{RST}',
                    f'  {BOLD}  {q.title}{RST}',
                ]

                # 상세 내용 (최대 4줄)
                if q.detail:
                    for dl in q.detail.split('\n')[:4]:
                        dl = dl.strip()
                        if dl:
                            lines.append(f'  {DIM}  {dl}{RST}')
                lines.append('')

                if q.options:
                    for oi, opt in enumerate(q.options):
                        if oi == self.opt_sel:
                            lines.append(f'  {SEL2}{BOLD}    > {_pad(opt, 40)}  {RST}')
                        else:
                            lines.append(f'  {DIM}      {opt}{RST}')
                    lines += [
                        '',
                        f'  {DIM}↑↓ 이동  ·  Enter 선택  ·  1/2/3 빠른선택{RST}',
                    ]
                else:
                    if self.text_mode:
                        lines += [
                            f'  {BOLD}  > {self.text_buf}█{RST}',
                            f'  {DIM}  Enter 전송  ·  ESC 취소{RST}',
                        ]
                    else:
                        lines.append(f'  {DIM}  Enter 눌러 답변 입력{RST}')
            else:
                lines += ['', f'  {GRN}진행 중... (질문 없음){RST}']
        else:
            lines += ['', f'  {CYN}오케스트레이터 초기화 중...{RST}']

        return '\n'.join(lines)

    def _draw_done(self) -> str:
        lines = ['', '']
        r = self._pipeline_result
        if r and r.get('success'):
            task_id = r.get('task_id', '')
            lines += [
                f'  {BOLD}{GRN}✓ 파이프라인 완료{RST}',
                f'  {DIM}Task: {task_id}{RST}' if task_id else '',
            ]
        elif self._pipeline_error:
            lines += [
                f'  {BOLD}{RED}✗ 파이프라인 실패{RST}',
                f'  {YLW}{self._pipeline_error[:120]}{RST}',
            ]
        else:
            lines.append(f'  {BOLD}{YLW}파이프라인 종료{RST}')

        lines += ['', f'  {DIM}Enter / q  →  메인 메뉴{RST}']
        return '\n'.join(lines)

    def _draw_status(self) -> str:
        lines = [
            '',
            f'  {BOLD}{BLU}작업 이력{RST}',
            f'  {DIM}{"─" * 50}{RST}',
            '',
        ]
        if not self.status_items:
            lines.append(f'  {DIM}실행된 작업이 없습니다.{RST}')
        else:
            for i, item in enumerate(self.status_items):
                stage = item['stage']
                icon = '✓' if stage == 'done' else '●' if stage == 'running' else '·'
                col = GRN if stage == 'done' else YLW if stage == 'running' else DIM
                created = item['created'][:16].replace('T', ' ') if item['created'] else ''
                label = f'{icon} {item["task_id"]}  [{stage}]  {created}'
                if i == self.status_sel:
                    lines.append(f'  {SEL}{BOLD}  {_pad(label, 54)}  {RST}')
                else:
                    lines.append(f'  {col}  {label}{RST}')

        lines += ['', f'  {DIM}↑↓ 이동  ·  ESC / q 뒤로{RST}']
        return '\n'.join(lines)

    # ─── 헬퍼 ────────────────────────────────────────────────────────────────

    def _get_stage_line(self) -> str:
        """현재 파이프라인 단계 표시줄."""
        orc = self.orchestrator
        if not orc:
            return f'{DIM}초기화 중...{RST}'

        # manifest.json에서 stage 읽기
        try:
            ws = orc.workspace_root
            # 가장 최근 task 디렉토리
            task_dirs = sorted(
                (ws / 'tasks').glob('task-*'), reverse=True
            )
            if task_dirs:
                manifest = task_dirs[0] / 'manifest.json'
                if manifest.exists():
                    data = json.loads(manifest.read_text())
                    stage = data.get('stage', '...')
                    task_id = data.get('task_id', '')
                    return (
                        f'{BOLD}{task_id}{RST}  '
                        f'{CYN}[{stage}]{RST}'
                    )
        except Exception:
            pass
        return f'{DIM}실행 중...{RST}'

    def _get_timeline_tail(self, n: int) -> List[str]:
        """timeline.log 마지막 n줄."""
        orc = self.orchestrator
        if not orc:
            return []
        try:
            ws = orc.workspace_root
            task_dirs = sorted(
                (ws / 'tasks').glob('task-*'), reverse=True
            )
            if task_dirs:
                log = task_dirs[0] / 'timeline.log'
                if log.exists():
                    lines = log.read_text().splitlines()
                    return lines[-n:] if lines else []
        except Exception:
            pass
        return []


# ─── 레거시 arg 모드 (하위 호환) ─────────────────────────────────────────────

def _run_legacy():
    """기존 argparse 기반 CLI 동작 (args 있을 때)."""
    import argparse
    from orchestrator.main import Orchestrator

    parser = argparse.ArgumentParser(
        description='Multi-Agent Development System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py run -s planning-spec.md
  python cli.py run -s planning-spec.md --no-tui
  python cli.py status
        """,
    )
    sub = parser.add_subparsers(dest='cmd')

    # run
    rp = sub.add_parser('run', help='파이프라인 실행')
    rp.add_argument('-s', '--spec', type=Path, required=True)
    rp.add_argument('-c', '--config', type=Path, default=Path('config.yaml'))
    rp.add_argument('-v', '--verbose', action='store_true')
    rp.add_argument('--no-tui', action='store_true', help='인터랙티브 없이 실행')

    # status
    sub.add_parser('status', help='작업 상태 보기')

    args = parser.parse_args()

    if args.cmd == 'run':
        if args.verbose:
            logging.getLogger().setLevel(logging.INFO)

        if args.no_tui:
            orc = Orchestrator(config_path=args.config)
            result = orc.run_from_spec(args.spec)
            if result.get('success'):
                print(f'{GRN}완료: {result.get("task_id", "")}{RST}')
            else:
                print(f'{RED}실패: {result.get("error", "")}{RST}')
                sys.exit(1)
        else:
            # 인터랙티브 단축 실행
            cli = InteractiveCLI(config_path=args.config)
            cli.current_spec = args.spec
            cli._pipeline_start = time.time()
            cli.state = ST_RUN
            cli._start_pipeline()
            cli.run()

    elif args.cmd == 'status':
        cli = InteractiveCLI()
        cli._enter_status()
        cli.run()
    else:
        parser.print_help()


# ─── 진입점 ──────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        _run_legacy()
    else:
        # 인터랙티브 모드
        config = Path('config.yaml')
        if not config.exists():
            print(
                f'{YLW}config.yaml 없음.{RST}  '
                f'{DIM}config-example.yaml 참고하여 생성하세요.{RST}\n'
            )
        InteractiveCLI(config_path=config).run()


if __name__ == '__main__':
    main()

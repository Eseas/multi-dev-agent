#!/usr/bin/env python3
"""Command-line interface for the multi-agent development system.

v4: select 커맨드, 개별 승인(--approaches/--reject), 확장 status, auto_revalidate.
"""

import argparse
import json
import sys
import time
import logging
from pathlib import Path

from orchestrator.main import Orchestrator
from orchestrator.utils import atomic_write


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Multi-Agent Development System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 기본 설정 파일 생성
  multi-agent-dev init

  # 기획서 기반으로 파이프라인 실행
  multi-agent-dev run -s planning-spec.md

  # Phase 1 체크포인트 승인
  multi-agent-dev approve task-20250210-153000

  # 수정 요청 (피드백 포함)
  multi-agent-dev revise task-20250210-153000 --feedback "API 설계를 변경해주세요"

  # 중단
  multi-agent-dev abort task-20250210-153000

  # 태스크 상태 확인
  multi-agent-dev status
  multi-agent-dev status task-20250210-153000

  # Phase 5에서 구현 선택 (N≥2)
  multi-agent-dev select task-20250210-153000 2

  # 특정 approach만 승인 (N≥2)
  multi-agent-dev approve task-20250210-153000 --approaches 1,2
  multi-agent-dev approve task-20250210-153000 --reject 3

  # 기획서 감시 모드
  multi-agent-dev watch
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령')

    # init
    init_parser = subparsers.add_parser(
        'init', help='기본 설정 파일 생성'
    )
    init_parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path('config.yaml'),
        help='설정 파일 출력 경로 (기본값: config.yaml)'
    )

    # run
    run_parser = subparsers.add_parser(
        'run', help='기획서 기반 파이프라인 실행'
    )
    run_parser.add_argument(
        '-s', '--spec',
        type=Path,
        required=True,
        help='기획서(planning-spec.md) 경로'
    )
    run_parser.add_argument(
        '-c', '--config',
        type=Path,
        default=Path('config.yaml'),
        help='설정 파일 경로 (기본값: config.yaml)'
    )
    run_parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='상세 로깅 활성화'
    )

    # approve
    approve_parser = subparsers.add_parser(
        'approve', help='체크포인트 승인'
    )
    approve_parser.add_argument(
        'task_id', type=str, help='태스크 ID (예: task-20250210-153000)'
    )
    approve_parser.add_argument(
        '-c', '--config',
        type=Path,
        default=Path('config.yaml'),
        help='설정 파일 경로'
    )
    approve_parser.add_argument(
        '--approaches',
        type=str,
        default=None,
        help='승인할 approach ID 목록 (쉼표 구분, 예: 1,2)'
    )
    approve_parser.add_argument(
        '--reject',
        type=str,
        default=None,
        help='반려할 approach ID 목록 (쉼표 구분, 예: 3)'
    )

    # select (Phase 5: 구현 선택)
    select_parser = subparsers.add_parser(
        'select', help='구현 선택 (Phase 5, N≥2)'
    )
    select_parser.add_argument(
        'task_id', type=str, help='태스크 ID'
    )
    select_parser.add_argument(
        'impl_id', type=int, help='선택할 구현 ID (예: 2)'
    )
    select_parser.add_argument(
        '-c', '--config',
        type=Path,
        default=Path('config.yaml'),
        help='설정 파일 경로'
    )

    # revise
    revise_parser = subparsers.add_parser(
        'revise', help='수정 요청 (체크포인트)'
    )
    revise_parser.add_argument(
        'task_id', type=str, help='태스크 ID'
    )
    revise_parser.add_argument(
        '--feedback', '-f',
        type=str,
        default='',
        help='수정 피드백'
    )
    revise_parser.add_argument(
        '-c', '--config',
        type=Path,
        default=Path('config.yaml'),
        help='설정 파일 경로'
    )

    # abort
    abort_parser = subparsers.add_parser(
        'abort', help='태스크 중단'
    )
    abort_parser.add_argument(
        'task_id', type=str, help='태스크 ID'
    )
    abort_parser.add_argument(
        '-c', '--config',
        type=Path,
        default=Path('config.yaml'),
        help='설정 파일 경로'
    )

    # status
    status_parser = subparsers.add_parser(
        'status', help='태스크 상태 확인'
    )
    status_parser.add_argument(
        'task_id', type=str, nargs='?', default=None,
        help='태스크 ID (생략 시 전체 목록)'
    )
    status_parser.add_argument(
        '-c', '--config',
        type=Path,
        default=Path('config.yaml'),
        help='설정 파일 경로'
    )

    # watch
    watch_parser = subparsers.add_parser(
        'watch', help='기획서 감시 모드 (자동 실행)'
    )
    watch_parser.add_argument(
        '-c', '--config',
        type=Path,
        default=Path('config.yaml'),
        help='설정 파일 경로'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        'init': cmd_init,
        'run': cmd_run,
        'approve': cmd_approve,
        'select': cmd_select,
        'revise': cmd_revise,
        'abort': cmd_abort,
        'status': cmd_status,
        'watch': cmd_watch,
    }

    handler = commands.get(args.command)
    if handler:
        return handler(args)

    parser.print_help()
    return 1


def cmd_init(args):
    """기본 설정 파일을 생성한다."""
    output_path = args.output

    if output_path.exists():
        response = input(f'{output_path} 이(가) 이미 존재합니다. 덮어쓰시겠습니까? [y/N]: ')
        if response.lower() != 'y':
            print('중단되었습니다.')
            return 1

    Orchestrator.create_default_config(output_path)
    print(f'기본 설정 파일 생성 완료: {output_path}')
    print()
    print('다음 단계:')
    print('  1. config.yaml을 편집하여 target_repo를 설정하세요')
    print('  2. 기획서를 작성하세요 (planning-spec.md)')
    print('  3. 실행: multi-agent-dev run -s planning-spec.md')

    return 0


def cmd_run(args):
    """기획서 기반으로 파이프라인을 실행한다."""
    spec_path = args.spec.resolve()

    if not spec_path.exists():
        print(f'오류: 기획서를 찾을 수 없습니다: {spec_path}', file=sys.stderr)
        return 1

    if not args.config.exists():
        print(f'오류: 설정 파일을 찾을 수 없습니다: {args.config}', file=sys.stderr)
        print('"multi-agent-dev init"으로 기본 설정을 생성하세요', file=sys.stderr)
        return 1

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    try:
        print(f'기획서: {spec_path}')
        print('=' * 60)
        print('파이프라인을 시작합니다...')
        print()

        orchestrator = Orchestrator(args.config)
        result = orchestrator.run_from_spec(spec_path)

        print()
        print('=' * 60)

        if result['success']:
            task_id = result['task_id']

            # 평가 요약에서 브랜치 정보 추출
            eval_summary = result.get('evaluation_summary', {})
            implementations = result.get('implementations', [])

            # 브랜치 목록 생성
            if eval_summary.get('status') == 'single_implementation':
                # N=1: 단일 구현
                branch = eval_summary.get('branch', 'N/A')
                print(f'[SUCCESS] 파이프라인 완료!')
                print(f'  태스크 ID: {task_id}')
                print(f'  브랜치:    {branch}')
                print()
                print(f'평가 결과: workspace/tasks/{task_id}/evaluation-result.md')
                print(f'통합하려면: cd <타겟-프로젝트> && git merge {branch}')
            elif eval_summary.get('rankings'):
                # N≥2: 비교 평가
                rankings = eval_summary['rankings']
                recommended_id = rankings[0] if rankings else None
                branches = [impl['branch'] for impl in implementations if impl.get('success')]

                print(f'[SUCCESS] 파이프라인 완료!')
                print(f'  태스크 ID: {task_id}')
                print(f'  구현 개수: {len(branches)}개')
                if recommended_id:
                    recommended_branch = next((impl['branch'] for impl in implementations if impl['approach_id'] == recommended_id), None)
                    print(f'  추천 구현: impl-{recommended_id} ({recommended_branch})')
                print()
                print(f'평가 결과: workspace/tasks/{task_id}/evaluation-result.md')
                print(f'비교 보고서: workspace/tasks/{task_id}/comparator/comparison.md')
            else:
                # 평가 실패 또는 기타
                print(f'[SUCCESS] 파이프라인 완료 (평가 없음)')
                print(f'  태스크 ID: {task_id}')
                print()
                print(f'결과 확인: workspace/tasks/{task_id}/')

            return 0
        else:
            print(f'[FAILED] 파이프라인 실패', file=sys.stderr)
            print(f'  오류: {result.get("error")}', file=sys.stderr)

            if 'validation_errors' in result:
                print('  검증 오류:', file=sys.stderr)
                for err in result['validation_errors']:
                    print(f'    - {err}', file=sys.stderr)

            if 'feedback' in result:
                print(f'  피드백: {result["feedback"]}', file=sys.stderr)

            return 1

    except KeyboardInterrupt:
        print('\n사용자에 의해 중단되었습니다', file=sys.stderr)
        return 130
    except Exception as e:
        print(f'[ERROR] 예상치 못한 오류: {e}', file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


def _get_task_dir(args, task_id: str) -> Path:
    """태스크 디렉토리 경로를 반환한다."""
    import yaml
    config_path = args.config
    if not config_path.exists():
        print(f'오류: 설정 파일을 찾을 수 없습니다: {config_path}', file=sys.stderr)
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    workspace_root = Path(config['workspace']['root'])
    return workspace_root / 'tasks' / task_id


def _write_checkpoint_decision(task_dir: Path, decision: dict) -> bool:
    """체크포인트 결정 파일을 작성한다."""
    if not task_dir.exists():
        print(f'오류: 태스크 디렉토리가 없습니다: {task_dir}', file=sys.stderr)
        return False

    decision_file = task_dir / 'checkpoint-decision.json'
    atomic_write(decision_file, decision)
    return True


def cmd_approve(args):
    """체크포인트를 승인한다."""
    task_dir = _get_task_dir(args, args.task_id)

    decision = {
        'action': 'approve',
        'task_id': args.task_id,
    }

    # N≥2 개별 승인
    if args.approaches:
        try:
            approved = [int(x.strip()) for x in args.approaches.split(',')]
            decision['approved_approaches'] = approved
        except ValueError:
            print('오류: --approaches는 쉼표로 구분된 숫자여야 합니다 (예: 1,2)', file=sys.stderr)
            return 1

    if args.reject:
        try:
            rejected = [int(x.strip()) for x in args.reject.split(',')]
            decision['rejected_approaches'] = rejected
        except ValueError:
            print('오류: --reject는 쉼표로 구분된 숫자여야 합니다 (예: 3)', file=sys.stderr)
            return 1

    if _write_checkpoint_decision(task_dir, decision):
        msg = f'[APPROVED] {args.task_id} 승인 완료'
        if 'approved_approaches' in decision:
            msg += f' (승인: {decision["approved_approaches"]})'
        if 'rejected_approaches' in decision:
            msg += f' (반려: {decision["rejected_approaches"]})'
        print(msg)
        print('파이프라인이 다음 단계로 진행됩니다.')
        return 0
    return 1


def cmd_select(args):
    """Phase 5에서 구현을 선택한다 (N≥2)."""
    task_dir = _get_task_dir(args, args.task_id)

    if not task_dir.exists():
        print(f'오류: 태스크 디렉토리가 없습니다: {task_dir}', file=sys.stderr)
        return 1

    decision = {
        'selected_id': args.impl_id,
        'action': 'approve',
        'task_id': args.task_id,
    }

    decision_file = task_dir / 'selection-decision.json'
    atomic_write(decision_file, decision)

    print(f'[SELECTED] {args.task_id}: impl-{args.impl_id} 선택 완료')
    print('파이프라인이 Phase 6 (통합)으로 진행됩니다.')
    return 0


def cmd_revise(args):
    """수정을 요청한다."""
    task_dir = _get_task_dir(args, args.task_id)

    feedback = args.feedback
    if not feedback:
        print('수정 피드백을 입력하세요 (빈 줄로 종료):')
        lines = []
        try:
            while True:
                line = input()
                if line == '':
                    break
                lines.append(line)
        except EOFError:
            pass
        feedback = '\n'.join(lines)

    decision = {
        'action': 'revise',
        'task_id': args.task_id,
        'feedback': feedback,
    }

    if _write_checkpoint_decision(task_dir, decision):
        print(f'[REVISE] {args.task_id} 수정 요청 완료')
        if feedback:
            print(f'  피드백: {feedback[:100]}...' if len(feedback) > 100 else f'  피드백: {feedback}')
        return 0
    return 1


def cmd_abort(args):
    """태스크를 중단한다."""
    task_dir = _get_task_dir(args, args.task_id)

    decision = {
        'action': 'abort',
        'task_id': args.task_id,
    }

    if _write_checkpoint_decision(task_dir, decision):
        print(f'[ABORTED] {args.task_id} 중단 완료')
        return 0
    return 1


def cmd_status(args):
    """태스크 상태를 확인한다."""
    import yaml

    config_path = args.config
    if not config_path.exists():
        print(f'오류: 설정 파일을 찾을 수 없습니다: {config_path}', file=sys.stderr)
        return 1

    with open(config_path) as f:
        config = yaml.safe_load(f)

    workspace_root = Path(config['workspace']['root'])
    tasks_dir = workspace_root / 'tasks'

    if args.task_id:
        # 특정 태스크 상세 상태
        task_dir = tasks_dir / args.task_id
        manifest_file = task_dir / 'manifest.json'

        if not manifest_file.exists():
            print(f'오류: 태스크를 찾을 수 없습니다: {args.task_id}', file=sys.stderr)
            return 1

        with open(manifest_file) as f:
            manifest = json.load(f)

        print(f'태스크: {manifest.get("task_id", "N/A")}')
        print(f'상태:   {manifest.get("stage", "N/A")}')
        print(f'생성:   {manifest.get("created_at", "N/A")}')
        print(f'갱신:   {manifest.get("updated_at", "N/A")}')
        print(f'기획서: {manifest.get("spec_path", "N/A")}')

        phases = manifest.get('phases', {})
        if phases:
            print()
            print('Phase 상태:')
            for phase_name, phase_data in phases.items():
                status = phase_data.get('status', 'unknown')
                print(f'  {phase_name}: {status}')

        # 구현 상세 (N≥2)
        phase2 = phases.get('phase2', {})
        impl_list = phase2.get('implementations', [])
        if impl_list:
            print()
            print('구현 목록:')
            for impl_info in impl_list:
                aid = impl_info.get('approach_id', '?')
                branch = impl_info.get('branch', 'N/A')
                success = impl_info.get('success', False)
                status_icon = 'OK' if success else 'FAIL'
                print(f'  impl-{aid}: [{status_icon}] {branch}')

        # comparison/rankings 확인 (Phase 4)
        phase4 = phases.get('phase4', {})
        if phase4.get('rankings'):
            print()
            print(f'Rankings: {phase4["rankings"]}')
            comparison_file = task_dir / 'comparator' / 'comparison.md'
            if comparison_file.exists():
                print(f'비교 보고서: {comparison_file}')

        # human-review 확인 (Phase 5)
        review_file = task_dir / 'human-review.json'
        if review_file.exists():
            with open(review_file) as f:
                review = json.load(f)
            recommended = review.get('recommended')
            if recommended:
                print()
                print(f'추천 구현: impl-{recommended}')
                print(f'선택하려면: multi-agent-dev select {args.task_id} <impl-id>')

        # integration-info 확인
        integration_file = task_dir / 'integration-info.json'
        if integration_file.exists():
            with open(integration_file) as f:
                info = json.load(f)
            print()
            print('통합 정보:')
            print(f'  브랜치: {info.get("branch", "N/A")}')
            print(f'  상태:   {info.get("status", "N/A")}')

    else:
        # 전체 태스크 목록
        if not tasks_dir.exists():
            print('아직 실행된 태스크가 없습니다.')
            return 0

        task_dirs = sorted(tasks_dir.iterdir(), reverse=True)
        if not task_dirs:
            print('아직 실행된 태스크가 없습니다.')
            return 0

        print(f'{"태스크 ID":<30} {"상태":<20} {"생성일시"}')
        print('-' * 70)

        for td in task_dirs:
            manifest_file = td / 'manifest.json'
            if not manifest_file.exists():
                continue

            try:
                with open(manifest_file) as f:
                    manifest = json.load(f)

                task_id = manifest.get('task_id', td.name)
                stage = manifest.get('stage', 'unknown')
                created = manifest.get('created_at', 'N/A')

                print(f'{task_id:<30} {stage:<20} {created}')
            except (json.JSONDecodeError, OSError):
                print(f'{td.name:<30} {"읽기 오류":<20}')

    return 0


def _read_key():
    """터미널에서 단일 키 입력을 읽는다 (화살표 키 포함)."""
    import tty
    import termios

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == '\x1b':
            seq = sys.stdin.read(2)
            if seq == '[A':
                return 'up'
            elif seq == '[B':
                return 'down'
            return 'esc'
        elif ch == ' ':
            return 'space'
        elif ch in ('\r', '\n'):
            return 'enter'
        elif ch == '\x03':
            return 'ctrl_c'
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _select_watch_dirs(all_dirs: list) -> list:
    """화살표 키 기반 대화형 UI로 감시할 디렉토리를 선택받는다.

    Args:
        all_dirs: config에서 읽어온 전체 감시 대상 디렉토리 리스트

    Returns:
        사용자가 선택한 디렉토리 Path 리스트
    """
    resolved = []
    for d in all_dirs:
        p = Path(d).resolve()
        exists = p.exists()
        resolved.append((p, exists))

    cursor = 0
    checked = [False] * len(resolved)
    total = len(resolved)

    def render():
        # 커서를 맨 위로 이동하여 다시 그리기
        sys.stdout.write(f'\033[{total + 5}A')  # 위로 이동
        sys.stdout.write('\033[J')  # 아래 전체 지우기

        print('  감시할 디렉토리를 선택하세요')
        print(f'  (위/아래: 이동, Space: 선택/해제, Enter: 확정)\n')

        for i, (p, exists) in enumerate(resolved):
            marker = '[*]' if checked[i] else '[ ]'
            arrow = '>' if i == cursor else ' '
            status = ' (자동 생성)' if not exists else ''
            print(f'  {arrow} {marker} {p}{status}')

        selected_count = sum(checked)
        print(f'\n  {selected_count}개 선택됨')

    # 초기 출력용 빈 줄 확보
    for _ in range(total + 5):
        print()

    render()

    while True:
        key = _read_key()

        if key == 'ctrl_c':
            print('\n취소되었습니다.')
            sys.exit(0)
        elif key == 'up':
            cursor = (cursor - 1) % total
        elif key == 'down':
            cursor = (cursor + 1) % total
        elif key == 'space':
            checked[cursor] = not checked[cursor]
        elif key == 'enter':
            selected = [
                resolved[i][0]
                for i in range(total) if checked[i]
            ]
            if not selected:
                # 아무것도 선택 안 했으면 무시
                continue
            break

        render()

    # 존재하지 않는 디렉토리 자동 생성
    for d in selected:
        d.mkdir(parents=True, exist_ok=True)

    return selected


def cmd_watch(args):
    """기획서 감시 모드를 실행한다.

    config의 watch.dirs에 지정된 디렉토리들을 감시하여
    새로운 기획서가 감지되면 자동으로 파이프라인을 실행한다.
    auto_revalidate가 true면 기존 기획서의 수정도 감지하여 재실행한다.
    """
    if not args.config.exists():
        print(f'오류: 설정 파일을 찾을 수 없습니다: {args.config}', file=sys.stderr)
        return 1

    import yaml
    with open(args.config) as f:
        config = yaml.safe_load(f)

    # watch.dirs에서 감시 경로 목록 로드
    watch_dirs = config.get('watch', {}).get('dirs', [])
    if not watch_dirs:
        print('config에 watch.dirs가 설정되지 않았습니다.')
        print()
        print('config.yaml에 다음을 추가하세요:')
        print()
        print('  watch:')
        print('    dirs:')
        print('      - /path/to/planning/completed')
        print('      - /path/to/another/planning/completed')
        print()

        # 기본 경로 제안
        workspace_root = config.get('workspace', {}).get('root', '')
        if workspace_root:
            default_dir = str(
                (Path(workspace_root) / 'planning' / 'completed').resolve()
            )
            answer = input(
                f'기본 경로({default_dir})를 사용하시겠습니까? [Y/n]: '
            ).strip().lower()
            if answer in ('', 'y', 'yes'):
                watch_dirs = [default_dir]
                print(f'기본 경로를 사용합니다: {default_dir}')
                print()
            else:
                return 1
        else:
            return 1

    # 디렉토리 선택 시퀀스
    if len(watch_dirs) == 1:
        # 단일 경로면 선택 없이 바로 사용
        selected_dirs = [Path(watch_dirs[0]).resolve()]
        selected_dirs[0].mkdir(parents=True, exist_ok=True)
    else:
        selected_dirs = _select_watch_dirs(watch_dirs)

    auto_revalidate = config.get('validation', {}).get('auto_revalidate', False)

    print()
    print('=== 감시 모드 시작 ===')
    print()
    for d in selected_dirs:
        print(f'  감시 중: {d}')
    print()
    print('새로운 planning-spec.md 파일을 감지하면 자동으로 실행합니다.')
    if auto_revalidate:
        print('auto_revalidate 활성화: 기존 기획서 수정 시 재실행합니다.')
    print('Ctrl+C로 종료')
    print()

    processed = set()
    # mtime 추적 (auto_revalidate용)
    file_mtimes = {}

    # 기존 파일 등록 (모든 감시 디렉토리)
    for watch_dir in selected_dirs:
        for existing in watch_dir.rglob('planning-spec.md'):
            spec_str = str(existing)
            processed.add(spec_str)
            file_mtimes[spec_str] = existing.stat().st_mtime

    try:
        while True:
            for watch_dir in selected_dirs:
                for spec_file in watch_dir.rglob('planning-spec.md'):
                    spec_str = str(spec_file)

                    should_run = False

                    if spec_str not in processed:
                        # 새 파일
                        processed.add(spec_str)
                        file_mtimes[spec_str] = spec_file.stat().st_mtime
                        should_run = True
                        print(f'새 기획서 감지: {spec_file}')
                    elif auto_revalidate:
                        # 기존 파일 수정 감지
                        current_mtime = spec_file.stat().st_mtime
                        if current_mtime > file_mtimes.get(spec_str, 0):
                            file_mtimes[spec_str] = current_mtime
                            should_run = True
                            print(f'기획서 수정 감지: {spec_file}')

                    if should_run:
                        print('파이프라인을 시작합니다...')
                        print()

                        try:
                            orchestrator = Orchestrator(args.config)
                            result = orchestrator.run_from_spec(spec_file)

                            if result['success']:
                                print(f'[SUCCESS] 완료: {result["task_id"]}')
                            else:
                                print(f'[FAILED] 실패: {result.get("error")}')
                        except Exception as e:
                            print(f'[ERROR] 오류: {e}', file=sys.stderr)

                        print()

            time.sleep(5)  # 5초마다 폴링

    except KeyboardInterrupt:
        print('\n감시 모드를 종료합니다.')
        return 0


if __name__ == '__main__':
    sys.exit(main())

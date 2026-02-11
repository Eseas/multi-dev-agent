#!/usr/bin/env python3
"""Command-line interface for the multi-agent development system.

v3: spec 기반 실행, approve/revise/abort 체크포인트, watch 모드.
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
            branch = result.get('selected_branch', 'N/A')
            print(f'[SUCCESS] 파이프라인 완료!')
            print(f'  태스크 ID: {task_id}')
            print(f'  브랜치:    {branch}')
            print()
            print(f'통합하려면: git merge {branch}')
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

    if _write_checkpoint_decision(task_dir, decision):
        print(f'[APPROVED] {args.task_id} 승인 완료')
        print('파이프라인이 다음 단계로 진행됩니다.')
        return 0
    return 1


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


def cmd_watch(args):
    """기획서 감시 모드를 실행한다.

    workspace/planning/completed/ 디렉토리를 감시하여
    새로운 기획서가 감지되면 자동으로 파이프라인을 실행한다.
    """
    if not args.config.exists():
        print(f'오류: 설정 파일을 찾을 수 없습니다: {args.config}', file=sys.stderr)
        return 1

    import yaml
    with open(args.config) as f:
        config = yaml.safe_load(f)

    workspace_root = Path(config['workspace']['root'])
    completed_dir = workspace_root / 'planning' / 'completed'
    completed_dir.mkdir(parents=True, exist_ok=True)

    print(f'기획서 감시 중: {completed_dir}')
    print('새로운 planning-spec.md 파일을 감지하면 자동으로 실행합니다.')
    print('Ctrl+C로 종료')
    print()

    processed = set()

    # 기존 파일 스킵
    for existing in completed_dir.rglob('planning-spec.md'):
        processed.add(str(existing))

    try:
        while True:
            for spec_file in completed_dir.rglob('planning-spec.md'):
                spec_str = str(spec_file)
                if spec_str in processed:
                    continue

                processed.add(spec_str)
                print(f'새 기획서 감지: {spec_file}')
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

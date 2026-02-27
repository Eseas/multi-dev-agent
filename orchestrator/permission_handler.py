"""권한 관리 핸들러.

config.yaml의 permissions 설정을 기반으로 도구 실행 권한을 평가하고,
"ask" 대상 도구에 대해 파일 기반 사용자 승인 흐름을 제공한다.
"""

import json
import fnmatch
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from .watcher import FileWaitHelper
from .utils.atomic_write import atomic_write


logger = logging.getLogger(__name__)


@dataclass
class PermissionRule:
    """단일 권한 규칙.

    Attributes:
        tool: 도구 이름 ("Bash", "Write", "Read" 등)
        pattern: glob 패턴 ("*", "npm run *", "src/**")
        action: "allow" | "deny" | "ask"
    """
    tool: str
    pattern: str
    action: str

    def matches(self, tool_name: str, tool_argument: str) -> bool:
        """이 규칙이 주어진 도구/인자와 매칭되는지 확인.

        Args:
            tool_name: 도구 이름 (e.g., "Bash")
            tool_argument: 도구 인자 (e.g., "npm run build" or "src/main.py")

        Returns:
            매칭 여부
        """
        if self.tool != tool_name:
            return False

        if self.pattern == '*':
            return True

        return fnmatch.fnmatch(tool_argument, self.pattern)


class PermissionHandler:
    """도구 실행 권한 관리자.

    규칙 평가 순서: deny → allow → ask → 기본값(ask)

    Usage:
        handler = PermissionHandler.from_config(config['permissions'], notifier)
        decision = handler.evaluate("Bash", {"command": "rm -rf tmp/"})
        if decision == "ask":
            decision = handler.request_human_decision("Bash", {...}, working_dir)
    """

    def __init__(
        self,
        rules: List[PermissionRule],
        notifier=None,
        ask_timeout: float = 300.0,
        question_queue=None,
    ):
        """
        Args:
            rules: 권한 규칙 목록 (평가 순서: deny → allow → ask)
            notifier: SystemNotifier 인스턴스 (사용자 알림용)
            ask_timeout: 사용자 응답 대기 시간 (초)
            question_queue: QuestionQueue 인스턴스 (있으면 큐 경유, 없으면 파일 기반)
        """
        self.notifier = notifier
        self.ask_timeout = ask_timeout
        self.question_queue = question_queue

        # 규칙을 action별로 분류 (평가 순서 보장)
        self._deny_rules = [r for r in rules if r.action == 'deny']
        self._allow_rules = [r for r in rules if r.action == 'allow']
        self._ask_rules = [r for r in rules if r.action == 'ask']

    def evaluate(self, tool_name: str, tool_input: dict) -> str:
        """규칙 기반 권한 평가.

        평가 순서: deny → allow → ask → 기본값(ask)

        Args:
            tool_name: 도구 이름 (e.g., "Bash", "Write")
            tool_input: 도구 입력 딕셔너리

        Returns:
            "allow" | "deny" | "ask"
        """
        argument = self._extract_argument(tool_name, tool_input)

        # 1. deny 규칙 먼저 (보안 최우선)
        for rule in self._deny_rules:
            if rule.matches(tool_name, argument):
                logger.info(f"Permission DENIED: {tool_name}({argument}) by rule {rule}")
                return 'deny'

        # 2. allow 규칙
        for rule in self._allow_rules:
            if rule.matches(tool_name, argument):
                logger.debug(f"Permission ALLOWED: {tool_name}({argument}) by rule {rule}")
                return 'allow'

        # 3. ask 규칙
        for rule in self._ask_rules:
            if rule.matches(tool_name, argument):
                logger.info(f"Permission ASK: {tool_name}({argument}) by rule {rule}")
                return 'ask'

        # 4. 기본값: ask (안전한 기본값)
        logger.info(f"Permission ASK (default): {tool_name}({argument})")
        return 'ask'

    def request_human_decision(
        self,
        tool_name: str,
        tool_input: dict,
        working_dir: Path,
    ) -> str:
        """사용자 승인 요청.

        QuestionQueue가 설정되어 있으면 큐를 경유하고,
        없으면 기존 파일 기반 방식을 사용한다.

        Args:
            tool_name: 도구 이름
            tool_input: 도구 입력
            working_dir: 작업 디렉토리

        Returns:
            "allow" | "deny"
        """
        argument = self._extract_argument(tool_name, tool_input)

        # QuestionQueue 경유 경로
        if self.question_queue:
            return self._request_via_queue(tool_name, argument, tool_input)

        # 기존 파일 기반 경로
        return self._request_via_file(tool_name, argument, tool_input, working_dir)

    def _request_via_queue(
        self,
        tool_name: str,
        argument: str,
        tool_input: dict,
    ) -> str:
        """QuestionQueue를 통한 사용자 승인 요청."""
        from .queue.models import Question, QuestionType

        input_preview = json.dumps(tool_input, ensure_ascii=False)
        if len(input_preview) > 500:
            input_preview = input_preview[:500] + '...'

        q = Question(
            type=QuestionType.PERMISSION,
            source=f"executor",
            phase="execution",
            title=f"{tool_name} 도구 사용 승인",
            detail=f"인자: {argument}\n입력: {input_preview}",
            options=["allow", "deny"],
            default="deny",
            timeout=self.ask_timeout,
        )
        answer = self.question_queue.ask(q)
        decision = answer.response
        if decision not in ('allow', 'deny'):
            logger.warning(f"Invalid decision '{decision}', defaulting to DENY")
            return 'deny'
        return decision

    def _request_via_file(
        self,
        tool_name: str,
        argument: str,
        tool_input: dict,
        working_dir: Path,
    ) -> str:
        """기존 파일 기반 사용자 승인 요청."""
        request_file = working_dir / 'permission-request.json'
        decision_file = working_dir / 'permission-decision.json'

        # 이전 결정 파일 제거 (새 요청이므로)
        if decision_file.exists():
            decision_file.unlink()

        # 1. 요청 파일 작성
        request_data = {
            'tool': tool_name,
            'argument': argument,
            'input': tool_input,
            'timestamp': datetime.now().isoformat(),
            'instructions': (
                'permission-decision.json 파일에 '
                '{"decision": "allow"} 또는 {"decision": "deny"}를 '
                '작성해주세요.'
            ),
        }
        atomic_write(request_file, request_data)
        logger.info(
            f"Permission request written: {request_file} "
            f"(tool={tool_name}, arg={argument})"
        )

        # 2. OS 알림
        if self.notifier:
            self.notifier.notify_permission_needed(tool_name, argument)

        # 3. 결정 대기
        logger.info(
            f"Waiting for human decision (timeout={self.ask_timeout}s)..."
        )
        result = FileWaitHelper.wait_for_file_content(
            file_path=decision_file,
            expected_key='decision',
            timeout=self.ask_timeout,
            poll_interval=1.0,
        )

        # 4. 결과 처리
        if result is None:
            logger.warning(
                f"Permission request timed out after {self.ask_timeout}s, "
                f"defaulting to DENY"
            )
            return 'deny'

        decision = result.get('decision', 'deny')
        if decision not in ('allow', 'deny'):
            logger.warning(f"Invalid decision '{decision}', defaulting to DENY")
            return 'deny'

        logger.info(f"Human decision received: {decision}")

        # 요청/결정 파일 정리
        try:
            request_file.unlink(missing_ok=True)
            decision_file.unlink(missing_ok=True)
        except OSError:
            pass

        return decision

    def generate_settings(self) -> dict:
        """현재 규칙을 .claude/settings.json 형식으로 변환.

        allow/deny 규칙만 settings에 반영하고,
        ask 규칙은 settings에 넣지 않는다 (stream-json으로 처리).

        Returns:
            settings.json에 쓸 딕셔너리
        """
        allow_list = []
        deny_list = []

        for rule in self._allow_rules:
            if rule.pattern == '*':
                allow_list.append(rule.tool)
            else:
                allow_list.append(f"{rule.tool}({rule.pattern})")

        for rule in self._deny_rules:
            if rule.pattern == '*':
                deny_list.append(rule.tool)
            else:
                deny_list.append(f"{rule.tool}({rule.pattern})")

        settings = {
            "permissions": {}
        }

        if allow_list:
            settings["permissions"]["allow"] = allow_list
        if deny_list:
            settings["permissions"]["deny"] = deny_list

        return settings

    @classmethod
    def from_config(
        cls,
        config: dict,
        notifier=None,
    ) -> 'PermissionHandler':
        """config.yaml의 permissions 섹션에서 PermissionHandler 생성.

        config 형식:
            permissions:
              allow:
                - "Read(*)"
                - "Glob(*)"
              deny:
                - "Bash(rm -rf *)"
              ask:
                - "Bash(*)"
              ask_timeout: 300

        Args:
            config: permissions 섹션 딕셔너리
            notifier: SystemNotifier 인스턴스

        Returns:
            PermissionHandler 인스턴스
        """
        rules = []

        for action in ('deny', 'allow', 'ask'):
            entries = config.get(action, [])
            for entry in entries:
                tool, pattern = cls._parse_rule_entry(entry)
                rules.append(PermissionRule(
                    tool=tool,
                    pattern=pattern,
                    action=action,
                ))

        ask_timeout = config.get('ask_timeout', 300.0)

        return cls(
            rules=rules,
            notifier=notifier,
            ask_timeout=ask_timeout,
        )

    @staticmethod
    def _parse_rule_entry(entry: str) -> tuple:
        """규칙 문자열을 (tool, pattern) 튜플로 파싱.

        예시:
            "Bash(*)" → ("Bash", "*")
            "Write(src/**)" → ("Write", "src/**")
            "Read" → ("Read", "*")
            "Bash(npm run *)" → ("Bash", "npm run *")

        Args:
            entry: 규칙 문자열

        Returns:
            (tool_name, pattern) 튜플
        """
        match = re.match(r'^(\w+)\((.+)\)$', entry)
        if match:
            return match.group(1), match.group(2)

        # 패턴 없이 도구 이름만 → 전체 허용
        return entry.strip(), '*'

    @staticmethod
    def _extract_argument(tool_name: str, tool_input: dict) -> str:
        """도구 입력에서 매칭용 인자 문자열을 추출.

        도구별로 매칭에 사용할 핵심 인자가 다르다:
        - Bash: command 필드
        - Write/Edit/Read: file_path 필드
        - Glob: pattern 필드
        - Grep: pattern 필드

        Args:
            tool_name: 도구 이름
            tool_input: 도구 입력 딕셔너리

        Returns:
            매칭용 인자 문자열
        """
        if tool_name == 'Bash':
            return tool_input.get('command', '')
        elif tool_name in ('Write', 'Edit', 'Read'):
            return tool_input.get('file_path', '')
        elif tool_name == 'Glob':
            return tool_input.get('pattern', '')
        elif tool_name == 'Grep':
            return tool_input.get('pattern', '')
        else:
            # 알 수 없는 도구: 첫 번째 문자열 값 사용
            for v in tool_input.values():
                if isinstance(v, str):
                    return v
            return ''

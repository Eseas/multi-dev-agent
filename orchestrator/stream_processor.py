"""Stream-JSON 이벤트 프로세서.

Claude CLI의 --output-format stream-json 출력(NDJSON)을 파싱하여
텍스트를 누적하고, 도구 사용 이벤트를 감지하며, 최종 결과를 조립한다.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


logger = logging.getLogger(__name__)


@dataclass
class StreamEvent:
    """파싱된 단일 스트림 이벤트."""

    type: str
    """이벤트 유형:
    - "text_delta": 텍스트 조각
    - "tool_use_start": 도구 사용 시작
    - "tool_input_delta": 도구 입력 JSON 조각
    - "tool_use_complete": 도구 사용 블록 완료
    - "tool_result": 도구 실행 결과
    - "result": 최종 결과
    - "unknown": 분류 불가
    """

    data: dict = field(default_factory=dict)
    """원본 이벤트 데이터."""

    text: str = ""
    """text_delta인 경우 텍스트 내용."""

    tool_name: str = ""
    """tool_use 관련 이벤트인 경우 도구 이름."""

    tool_input: dict = field(default_factory=dict)
    """tool_use_complete인 경우 파싱된 도구 입력."""

    tool_use_id: str = ""
    """도구 사용 ID."""


@dataclass
class ToolUseRecord:
    """도구 사용 이력 레코드."""
    tool_name: str
    tool_use_id: str
    input_data: dict
    timestamp: str = ""


class StreamEventProcessor:
    """Claude CLI stream-json 출력을 실시간으로 처리한다.

    NDJSON 줄을 한 줄씩 받아 파싱하고, 텍스트를 누적하며,
    도구 사용 이벤트를 감지하고, 최종 결과를 조립한다.

    Usage:
        processor = StreamEventProcessor()
        for line in process.stdout:
            event = processor.process_line(line.strip())
            if event and event.type == 'result':
                break
        output = processor.build_output()
    """

    def __init__(self):
        self._text_parts: List[str] = []
        self._events: List[StreamEvent] = []
        self._tool_uses: List[ToolUseRecord] = []
        self._result: Optional[dict] = None
        self._session_id: str = ""
        self._cost_usd: float = 0.0
        self._seen_ids: set = set()

        # 현재 진행 중인 tool_use 블록 추적
        self._current_tool_name: str = ""
        self._current_tool_id: str = ""
        self._current_tool_input_parts: List[str] = []
        self._current_block_type: str = ""  # "text" | "tool_use"
        self._current_block_index: int = -1

    def process_line(self, line: str) -> Optional[StreamEvent]:
        """NDJSON 한 줄을 파싱하여 StreamEvent 반환.

        Args:
            line: 공백 제거된 NDJSON 한 줄

        Returns:
            파싱된 StreamEvent, 또는 무효한 줄이면 None
        """
        if not line:
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            logger.debug(f"Invalid JSON line: {line[:100]}")
            return None

        event_type = data.get('type', '')

        if event_type == 'stream_event':
            return self._process_stream_event(data)
        elif event_type == 'result':
            return self._process_result(data)
        else:
            # 알 수 없는 최상위 이벤트
            event = StreamEvent(type='unknown', data=data)
            self._events.append(event)
            return event

    def _process_stream_event(self, data: dict) -> Optional[StreamEvent]:
        """stream_event 타입 처리."""
        inner = data.get('event', {})
        inner_type = inner.get('type', '')

        if inner_type == 'content_block_start':
            return self._handle_content_block_start(inner, data)
        elif inner_type == 'content_block_delta':
            return self._handle_content_block_delta(inner, data)
        elif inner_type == 'content_block_stop':
            return self._handle_content_block_stop(inner, data)
        elif inner_type in ('message_start', 'message_delta', 'message_stop'):
            # 메시지 수준 이벤트: 로깅만
            return None
        else:
            return None

    def _handle_content_block_start(
        self, inner: dict, raw: dict
    ) -> Optional[StreamEvent]:
        """content_block_start 처리: 텍스트 또는 tool_use 블록 시작."""
        block = inner.get('content_block', {})
        block_type = block.get('type', '')
        block_index = inner.get('index', -1)

        self._current_block_index = block_index

        if block_type == 'tool_use':
            tool_name = block.get('name', '')
            tool_id = block.get('id', '')

            # 중복 체크
            if tool_id in self._seen_ids:
                return None
            self._seen_ids.add(tool_id)

            self._current_block_type = 'tool_use'
            self._current_tool_name = tool_name
            self._current_tool_id = tool_id
            self._current_tool_input_parts = []

            event = StreamEvent(
                type='tool_use_start',
                data=raw,
                tool_name=tool_name,
                tool_use_id=tool_id,
            )
            self._events.append(event)
            logger.debug(f"Tool use started: {tool_name} (id={tool_id})")
            return event

        elif block_type == 'text':
            self._current_block_type = 'text'
            return None

        else:
            self._current_block_type = block_type
            return None

    def _handle_content_block_delta(
        self, inner: dict, raw: dict
    ) -> Optional[StreamEvent]:
        """content_block_delta 처리: 텍스트 또는 도구 입력 조각."""
        delta = inner.get('delta', {})
        delta_type = delta.get('type', '')

        if delta_type == 'text_delta':
            text = delta.get('text', '')
            if text:
                self._text_parts.append(text)
                event = StreamEvent(type='text_delta', data=raw, text=text)
                self._events.append(event)
                return event

        elif delta_type == 'input_json_delta':
            partial = delta.get('partial_json', '')
            if partial:
                self._current_tool_input_parts.append(partial)
                event = StreamEvent(
                    type='tool_input_delta',
                    data=raw,
                    tool_name=self._current_tool_name,
                    tool_use_id=self._current_tool_id,
                )
                # input_delta는 너무 빈번하므로 _events에 추가하지 않음
                return event

        return None

    def _handle_content_block_stop(
        self, inner: dict, raw: dict
    ) -> Optional[StreamEvent]:
        """content_block_stop 처리: 블록 완료."""
        if self._current_block_type == 'tool_use':
            # 누적된 JSON 조각 합쳐서 파싱
            full_json_str = ''.join(self._current_tool_input_parts)
            tool_input = {}
            if full_json_str:
                try:
                    tool_input = json.loads(full_json_str)
                except json.JSONDecodeError:
                    logger.warning(
                        f"Failed to parse tool input JSON: "
                        f"{full_json_str[:200]}"
                    )

            event = StreamEvent(
                type='tool_use_complete',
                data=raw,
                tool_name=self._current_tool_name,
                tool_input=tool_input,
                tool_use_id=self._current_tool_id,
            )
            self._events.append(event)

            # 이력 기록
            self._tool_uses.append(ToolUseRecord(
                tool_name=self._current_tool_name,
                tool_use_id=self._current_tool_id,
                input_data=tool_input,
            ))

            logger.debug(
                f"Tool use complete: {self._current_tool_name} "
                f"(input keys: {list(tool_input.keys())})"
            )

            # 상태 리셋
            self._current_tool_name = ""
            self._current_tool_id = ""
            self._current_tool_input_parts = []
            self._current_block_type = ""

            return event

        # 텍스트 블록 종료 등
        self._current_block_type = ""
        return None

    def _process_result(self, data: dict) -> StreamEvent:
        """최종 result 이벤트 처리."""
        result_data = data.get('result', {})
        self._result = result_data
        self._session_id = result_data.get('session_id', '')
        self._cost_usd = result_data.get('total_cost_usd', 0.0)

        event = StreamEvent(type='result', data=data)
        self._events.append(event)

        logger.info(
            f"Stream result received: "
            f"session={self._session_id}, cost=${self._cost_usd:.4f}"
        )
        return event

    def get_accumulated_text(self) -> str:
        """지금까지 누적된 텍스트 출력."""
        return ''.join(self._text_parts)

    def get_result(self) -> Optional[dict]:
        """최종 result 이벤트 데이터. 없으면 None."""
        return self._result

    def get_session_id(self) -> str:
        """세션 ID."""
        return self._session_id

    def get_cost_usd(self) -> float:
        """총 비용 (USD)."""
        return self._cost_usd

    def get_tool_uses(self) -> List[ToolUseRecord]:
        """도구 사용 이력."""
        return list(self._tool_uses)

    def build_output(self) -> Dict[str, Any]:
        """최종 결과를 executor 반환 형식으로 변환.

        Returns:
            {success, output, error, session_id, cost_usd}
        """
        if self._result:
            subtype = self._result.get('subtype', '')
            is_error = self._result.get('is_error', False)
            result_text = self._result.get('result', '')

            # result 이벤트의 result 필드가 최종 텍스트
            # 텍스트 누적분보다 result 필드가 더 완전할 수 있음
            output = result_text or self.get_accumulated_text()

            return {
                'success': not is_error and subtype == 'success',
                'output': output,
                'error': result_text if is_error else '',
                'session_id': self._session_id,
                'cost_usd': self._cost_usd,
            }

        # result 이벤트가 오지 않은 경우 (타임아웃 등)
        accumulated = self.get_accumulated_text()
        return {
            'success': False,
            'output': accumulated,
            'error': 'No result event received',
            'session_id': self._session_id,
            'cost_usd': self._cost_usd,
        }

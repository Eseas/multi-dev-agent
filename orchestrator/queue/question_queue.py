"""Thread-safe, file-backed question queue."""

import threading
import json
import logging
from pathlib import Path
from typing import Optional, List, Callable
from datetime import datetime

from .models import Question, Answer, QuestionStatus
from ..utils.atomic_write import atomic_write


logger = logging.getLogger(__name__)


class QuestionQueue:
    """Thread-safe, file-backed question queue.

    에이전트 스레드에서 질문을 제출하면 답변이 올 때까지 해당 스레드만
    블로킹된다. TUI나 CLI에서 답변을 제출하면 대기 중인 스레드가 깨어난다.

    Usage:
        queue = QuestionQueue(task_dir)

        # 에이전트 스레드에서:
        q = Question(type=QuestionType.PERMISSION, ...)
        answer = queue.ask(q)  # 블로킹

        # TUI/CLI에서:
        pending = queue.get_pending()
        queue.answer("q-abc123", "allow")
    """

    def __init__(
        self,
        task_dir: Path,
        on_question: Optional[Callable[[Question], None]] = None,
    ):
        """초기화.

        Args:
            task_dir: 태스크 디렉토리 경로 (question-queue.json 저장 위치)
            on_question: 새 질문 등록 시 호출될 콜백 (TUI 갱신용)
        """
        self._task_dir = Path(task_dir)
        self._queue_file = self._task_dir / 'question-queue.json'
        self._lock = threading.Lock()
        self._events: dict[str, threading.Event] = {}
        self._questions: dict[str, Question] = {}
        self._on_question = on_question
        self._load()

    def ask(self, question: Question) -> Answer:
        """질문을 제출하고 답변을 대기한다 (블로킹).

        에이전트 스레드에서 호출한다. 답변이 올 때까지 호출 스레드만
        블로킹되며, 다른 에이전트 스레드는 영향 받지 않는다.

        Args:
            question: 제출할 질문

        Returns:
            사용자의 답변. 타임아웃 시 기본값(또는 "deny") 반환.
        """
        event = threading.Event()

        with self._lock:
            self._questions[question.id] = question
            self._events[question.id] = event
            self._persist()

        logger.info(
            f"[QUEUE] 질문 등록: {question.id} "
            f"(type={question.type.value}, source={question.source})"
        )

        # 콜백 호출 (lock 밖에서)
        if self._on_question:
            try:
                self._on_question(question)
            except Exception as e:
                logger.warning(f"on_question 콜백 오류: {e}")

        # 블로킹 대기
        answered = event.wait(timeout=question.timeout)

        if not answered:
            logger.warning(
                f"[QUEUE] 질문 타임아웃: {question.id} "
                f"({question.timeout}s)"
            )
            with self._lock:
                question.status = QuestionStatus.EXPIRED
                self._persist()
            default = question.default or "deny"
            return Answer(question_id=question.id, response=default)

        with self._lock:
            return Answer(
                question_id=question.id,
                response=question.answer or "",
            )

    def answer(self, question_id: str, response: str) -> bool:
        """질문에 답변한다 (논블로킹).

        TUI나 CLI에서 호출한다. 대기 중인 에이전트 스레드를 깨운다.

        Args:
            question_id: 대상 질문 ID
            response: 사용자 응답

        Returns:
            답변 성공 여부
        """
        with self._lock:
            q = self._questions.get(question_id)
            if not q:
                logger.warning(f"[QUEUE] 질문을 찾을 수 없음: {question_id}")
                return False
            if q.status != QuestionStatus.PENDING:
                logger.warning(
                    f"[QUEUE] 이미 처리된 질문: {question_id} "
                    f"(status={q.status.value})"
                )
                return False

            q.answer = response
            q.answered_at = datetime.now().isoformat()
            q.status = QuestionStatus.ANSWERED
            self._persist()

            event = self._events.get(question_id)

        logger.info(f"[QUEUE] 답변 완료: {question_id} → {response}")

        # 블로킹 해제 (lock 밖에서)
        if event:
            event.set()

        return True

    def cancel(self, question_id: str) -> bool:
        """질문을 취소한다.

        Args:
            question_id: 대상 질문 ID

        Returns:
            취소 성공 여부
        """
        with self._lock:
            q = self._questions.get(question_id)
            if not q or q.status != QuestionStatus.PENDING:
                return False

            q.status = QuestionStatus.CANCELLED
            q.answered_at = datetime.now().isoformat()
            self._persist()

            event = self._events.get(question_id)

        if event:
            event.set()

        return True

    def get_pending(self) -> List[Question]:
        """대기 중인 질문 목록을 반환한다 (생성순).

        Returns:
            PENDING 상태인 질문 리스트
        """
        with self._lock:
            return [
                q for q in self._questions.values()
                if q.status == QuestionStatus.PENDING
            ]

    def get_all(self) -> List[Question]:
        """모든 질문 목록을 반환한다.

        Returns:
            전체 질문 리스트
        """
        with self._lock:
            return list(self._questions.values())

    def get_question(self, question_id: str) -> Optional[Question]:
        """특정 질문을 반환한다.

        Args:
            question_id: 질문 ID

        Returns:
            질문 객체 또는 None
        """
        with self._lock:
            return self._questions.get(question_id)

    @property
    def pending_count(self) -> int:
        """대기 중인 질문 수."""
        with self._lock:
            return sum(
                1 for q in self._questions.values()
                if q.status == QuestionStatus.PENDING
            )

    def _persist(self):
        """큐 상태를 파일에 저장한다. _lock 내부에서 호출."""
        data = {
            'questions': [
                q.to_dict() for q in self._questions.values()
            ]
        }
        atomic_write(self._queue_file, data)

    def _load(self):
        """파일에서 큐 상태를 복구한다 (크래시 복구)."""
        if not self._queue_file.exists():
            return

        try:
            data = json.loads(self._queue_file.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"큐 파일 로드 실패: {e}")
            return

        for qd in data.get('questions', []):
            try:
                q = Question.from_dict(qd)
                self._questions[q.id] = q
                if q.status == QuestionStatus.PENDING:
                    self._events[q.id] = threading.Event()
            except (KeyError, ValueError) as e:
                logger.warning(f"질문 복구 실패: {e}")

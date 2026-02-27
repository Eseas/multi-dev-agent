"""Textual-based TUI dashboard application."""

import logging
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Header, Footer, Static, Input, Button
from textual.message import Message

from ..queue.models import Question, QuestionStatus
from ..queue.question_queue import QuestionQueue
from .widgets import QuestionCard, StatusPanel, QuestionDetail


logger = logging.getLogger(__name__)


class DashboardApp(App):
    """파이프라인 대시보드 + 질문 큐 TUI.

    좌측: 파이프라인 상태 패널
    우측: 질문 목록 + 상세 + 답변 입력
    """

    CSS = """
    Screen {
        layout: horizontal;
    }

    #left-panel {
        width: 30;
        min-width: 25;
        border-right: solid $accent;
        padding: 1;
    }

    #right-panel {
        width: 1fr;
        padding: 1;
    }

    #question-list {
        height: 1fr;
        min-height: 5;
        border: solid $primary;
        padding: 0 1;
    }

    #question-detail {
        height: auto;
        max-height: 12;
        border: solid $secondary;
        padding: 1;
        margin-top: 1;
    }

    #answer-section {
        height: auto;
        margin-top: 1;
    }

    #answer-input {
        width: 1fr;
    }

    #option-buttons {
        layout: horizontal;
        height: auto;
        margin-bottom: 1;
    }

    #option-buttons Button {
        margin-right: 1;
    }

    .selected {
        background: $accent 20%;
    }

    #status-panel {
        height: 1fr;
    }

    #pending-badge {
        text-style: bold;
        color: $warning;
    }

    #pipeline-result {
        margin-top: 1;
        border: solid $success;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("up,k", "move_up", "위로", show=False),
        Binding("down,j", "move_down", "아래로", show=False),
        Binding("enter", "select_question", "선택/답변", show=True),
        Binding("1", "quick_answer_1", "선택지 1", show=False),
        Binding("2", "quick_answer_2", "선택지 2", show=False),
        Binding("3", "quick_answer_3", "선택지 3", show=False),
        Binding("q", "quit", "종료", show=True),
    ]

    class PipelineComplete(Message):
        """파이프라인 완료 메시지."""
        def __init__(self, result: dict):
            super().__init__()
            self.result = result

    def __init__(
        self,
        orchestrator,
        spec_path: Path,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.orchestrator = orchestrator
        self.spec_path = spec_path
        self.queue: Optional[QuestionQueue] = None
        self._question_cards: list[QuestionCard] = []
        self._selected_idx = -1
        self._pipeline_result = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with Vertical(id="left-panel"):
                yield StatusPanel(id="status-panel")
            with Vertical(id="right-panel"):
                yield Static(
                    "[bold]대기 중인 질문[/]  "
                    "[dim]0개[/]",
                    id="question-header",
                )
                with VerticalScroll(id="question-list"):
                    yield Static(
                        "[dim]아직 질문이 없습니다[/]",
                        id="empty-msg",
                    )
                yield QuestionDetail(id="question-detail")
                with Vertical(id="answer-section"):
                    with Horizontal(id="option-buttons"):
                        pass
                    yield Input(
                        placeholder="답변을 입력하세요 (Enter로 전송)...",
                        id="answer-input",
                    )
        yield Footer()

    def on_mount(self) -> None:
        """앱 마운트 시 파이프라인 실행."""
        # 큐 생성 (on_question 콜백으로 TUI 갱신)
        self.orchestrator._on_question_callback = self._on_new_question
        # 파이프라인을 워커 스레드에서 실행
        self.run_worker(self._run_pipeline, thread=True)
        # 주기적 갱신
        self.set_interval(1.0, self._refresh_questions)

    def _on_new_question(self, question: Question) -> None:
        """새 질문이 큐에 등록될 때 호출 (워커 스레드에서)."""
        self.call_from_thread(self._refresh_questions)

    async def _run_pipeline(self) -> None:
        """워커 스레드에서 파이프라인 실행."""
        status = self.query_one("#status-panel", StatusPanel)

        try:
            self.call_from_thread(
                setattr, status, "phase", "파이프라인 시작 중..."
            )
            result = self.orchestrator.run_from_spec(self.spec_path)

            # 큐 참조 저장
            if self.orchestrator.question_queue:
                self.queue = self.orchestrator.question_queue

            self._pipeline_result = result

            if result.get('success'):
                self.call_from_thread(
                    setattr, status, "phase",
                    f"완료 - {result.get('task_id', '')}"
                )
            else:
                self.call_from_thread(
                    setattr, status, "phase",
                    f"실패: {result.get('error', '알 수 없는 오류')[:50]}"
                )

        except Exception as e:
            logger.error(f"파이프라인 오류: {e}")
            self.call_from_thread(
                setattr, status, "phase", f"오류: {str(e)[:50]}"
            )

    def _refresh_questions(self) -> None:
        """큐에서 대기 중인 질문을 갱신."""
        if not self.orchestrator.question_queue:
            return

        self.queue = self.orchestrator.question_queue
        pending = self.queue.get_pending()

        # 헤더 업데이트
        header = self.query_one("#question-header", Static)
        count = len(pending)
        header.update(
            f"[bold]대기 중인 질문[/]  "
            f"{'[bold yellow]' + str(count) + '개[/]' if count else '[dim]0개[/]'}"
        )

        # 질문 목록 업데이트
        list_container = self.query_one("#question-list", VerticalScroll)

        # empty 메시지 처리
        try:
            empty_msg = self.query_one("#empty-msg", Static)
            if pending:
                empty_msg.display = False
            else:
                empty_msg.display = True
                empty_msg.update("[dim]아직 질문이 없습니다[/]")
        except Exception:
            pass

        # 현재 카드 ID 목록
        current_ids = {c.question.id for c in self._question_cards}
        pending_ids = {q.id for q in pending}

        # 답변된/만료된 카드 제거
        for card in list(self._question_cards):
            if card.question.id not in pending_ids:
                card.remove()
                self._question_cards.remove(card)

        # 새 질문 카드 추가
        for q in pending:
            if q.id not in current_ids:
                card = QuestionCard(q, id=f"qc-{q.id}")
                list_container.mount(card)
                self._question_cards.append(card)

        # 선택 상태 유지
        if self._question_cards and self._selected_idx < 0:
            self._selected_idx = 0
            self._update_selection()

    def _update_selection(self) -> None:
        """선택 상태 시각적 업데이트."""
        for i, card in enumerate(self._question_cards):
            card.selected = (i == self._selected_idx)

        # 상세 패널 업데이트
        detail = self.query_one("#question-detail", QuestionDetail)
        if 0 <= self._selected_idx < len(self._question_cards):
            q = self._question_cards[self._selected_idx].question
            detail.set_question(q)
            self._update_option_buttons(q)
        else:
            detail.clear_question()
            self._clear_option_buttons()

    def _update_option_buttons(self, question: Question) -> None:
        """선택지 버튼 업데이트."""
        container = self.query_one("#option-buttons", Horizontal)
        container.remove_children()

        if question.options:
            for i, opt in enumerate(question.options, 1):
                btn = Button(f"{i}. {opt}", id=f"opt-{i}", variant="primary")
                btn._option_value = opt
                container.mount(btn)

    def _clear_option_buttons(self) -> None:
        """선택지 버튼 제거."""
        container = self.query_one("#option-buttons", Horizontal)
        container.remove_children()

    def action_move_up(self) -> None:
        """위로 이동."""
        if self._question_cards and self._selected_idx > 0:
            self._selected_idx -= 1
            self._update_selection()

    def action_move_down(self) -> None:
        """아래로 이동."""
        if self._question_cards and self._selected_idx < len(self._question_cards) - 1:
            self._selected_idx += 1
            self._update_selection()

    def action_select_question(self) -> None:
        """현재 선택된 질문의 답변 입력으로 포커스."""
        answer_input = self.query_one("#answer-input", Input)
        answer_input.focus()

    def action_quick_answer_1(self) -> None:
        self._quick_answer(0)

    def action_quick_answer_2(self) -> None:
        self._quick_answer(1)

    def action_quick_answer_3(self) -> None:
        self._quick_answer(2)

    def _quick_answer(self, option_idx: int) -> None:
        """선택지 번호로 빠른 답변."""
        if not (0 <= self._selected_idx < len(self._question_cards)):
            return
        q = self._question_cards[self._selected_idx].question
        if option_idx < len(q.options):
            self._submit_answer(q.id, q.options[option_idx])

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """선택지 버튼 클릭."""
        btn = event.button
        if hasattr(btn, '_option_value'):
            if 0 <= self._selected_idx < len(self._question_cards):
                q = self._question_cards[self._selected_idx].question
                self._submit_answer(q.id, btn._option_value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """텍스트 입력으로 답변."""
        if event.input.id == "answer-input" and event.value.strip():
            if 0 <= self._selected_idx < len(self._question_cards):
                q = self._question_cards[self._selected_idx].question
                self._submit_answer(q.id, event.value.strip())
                event.input.value = ""

    def _submit_answer(self, question_id: str, response: str) -> None:
        """답변 제출."""
        if self.queue:
            success = self.queue.answer(question_id, response)
            if success:
                self.notify(f"답변 완료: {response}", severity="information")
                self._refresh_questions()
                # 선택 인덱스 조정
                if self._selected_idx >= len(self._question_cards):
                    self._selected_idx = max(0, len(self._question_cards) - 1)
                self._update_selection()
            else:
                self.notify("답변 실패", severity="error")

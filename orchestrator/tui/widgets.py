"""Custom widgets for the TUI dashboard."""

from textual.widgets import Static
from textual.reactive import reactive

from ..queue.models import Question, QuestionStatus, QuestionType


# 질문 타입별 아이콘
TYPE_ICONS = {
    QuestionType.PERMISSION: "[bold yellow]PERM[/]",
    QuestionType.CHECKPOINT: "[bold cyan]CHKP[/]",
    QuestionType.ERROR: "[bold red]ERR [/]",
    QuestionType.DECISION: "[bold green]DCSN[/]",
}

# 질문 상태별 표시
STATUS_DISPLAY = {
    QuestionStatus.PENDING: "[yellow]대기중[/]",
    QuestionStatus.ANSWERED: "[green]완료[/]",
    QuestionStatus.EXPIRED: "[red]만료[/]",
    QuestionStatus.CANCELLED: "[dim]취소[/]",
}


class QuestionCard(Static):
    """질문 하나를 표시하는 위젯."""

    selected = reactive(False)

    def __init__(self, question: Question, **kwargs):
        super().__init__(**kwargs)
        self.question = question

    def render(self) -> str:
        q = self.question
        icon = TYPE_ICONS.get(q.type, "[dim]????[/]")
        status = STATUS_DISPLAY.get(q.status, "")
        prefix = ">" if self.selected else " "

        elapsed = ""
        if q.created_at:
            from datetime import datetime
            try:
                created = datetime.fromisoformat(q.created_at)
                delta = datetime.now() - created
                secs = int(delta.total_seconds())
                if secs < 60:
                    elapsed = f"{secs}s"
                elif secs < 3600:
                    elapsed = f"{secs // 60}m"
                else:
                    elapsed = f"{secs // 3600}h"
            except (ValueError, TypeError):
                pass

        return (
            f"{prefix} {icon} {q.title}\n"
            f"  [{q.source}] {status}  {elapsed}"
        )

    def watch_selected(self, value: bool) -> None:
        self.set_class(value, "selected")


class StatusPanel(Static):
    """파이프라인 상태 패널."""

    phase = reactive("대기 중")
    task_id = reactive("")

    def render(self) -> str:
        lines = ["[bold]파이프라인 상태[/]", ""]
        if self.task_id:
            lines.append(f"태스크: {self.task_id}")
        lines.append(f"단계: {self.phase}")
        return "\n".join(lines)


class QuestionDetail(Static):
    """선택된 질문의 상세 정보를 표시하는 위젯."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._question = None

    def set_question(self, question: Question) -> None:
        self._question = question
        self.refresh()

    def clear_question(self) -> None:
        self._question = None
        self.refresh()

    def render(self) -> str:
        if not self._question:
            return "[dim]질문을 선택하세요[/]"

        q = self._question
        icon = TYPE_ICONS.get(q.type, "")
        lines = [
            f"{icon} [bold]{q.title}[/]",
            f"출처: {q.source} | 단계: {q.phase}",
            "",
            q.detail,
        ]

        if q.options:
            lines.append("")
            lines.append("[bold]선택지:[/]")
            for i, opt in enumerate(q.options, 1):
                lines.append(f"  {i}. {opt}")

        if q.default:
            lines.append(f"\n기본값: {q.default}")

        return "\n".join(lines)

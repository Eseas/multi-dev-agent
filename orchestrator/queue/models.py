"""Data models for the question queue system."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List
from datetime import datetime
import uuid


class QuestionType(Enum):
    """질문 유형."""
    PERMISSION = "permission"
    CHECKPOINT = "checkpoint"
    ERROR = "error"
    DECISION = "decision"


class QuestionStatus(Enum):
    """질문 상태."""
    PENDING = "pending"
    ANSWERED = "answered"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass
class Question:
    """큐에 저장되는 질문.

    Attributes:
        type: 질문 유형 (permission, checkpoint, error, decision)
        source: 질문 출처 ("orchestrator", "impl-1", "reviewer-2" 등)
        phase: 파이프라인 단계 ("phase1", "phase2", "checkpoint" 등)
        title: 짧은 제목 (TUI 목록에 표시)
        detail: 상세 내용 (TUI 상세 패널에 표시)
        options: 선택지 목록 (비어있으면 자유 텍스트 입력)
        default: 타임아웃 시 사용할 기본값
        timeout: 대기 제한 시간 (초)
        id: 고유 식별자
        status: 현재 상태
        created_at: 생성 시각 (ISO 형식)
        answer: 사용자 답변
        answered_at: 답변 시각 (ISO 형식)
    """
    type: QuestionType
    source: str
    phase: str
    title: str
    detail: str
    options: List[str] = field(default_factory=list)
    default: Optional[str] = None
    timeout: float = 3600.0
    id: str = field(default_factory=lambda: f"q-{uuid.uuid4().hex[:8]}")
    status: QuestionStatus = QuestionStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    answer: Optional[str] = None
    answered_at: Optional[str] = None

    def to_dict(self) -> dict:
        """직렬화용 딕셔너리 변환."""
        return {
            'id': self.id,
            'type': self.type.value,
            'source': self.source,
            'phase': self.phase,
            'title': self.title,
            'detail': self.detail,
            'options': self.options,
            'default': self.default,
            'timeout': self.timeout,
            'status': self.status.value,
            'created_at': self.created_at,
            'answer': self.answer,
            'answered_at': self.answered_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Question':
        """딕셔너리에서 Question 인스턴스 생성."""
        return cls(
            id=data['id'],
            type=QuestionType(data['type']),
            source=data['source'],
            phase=data['phase'],
            title=data['title'],
            detail=data.get('detail', ''),
            options=data.get('options', []),
            default=data.get('default'),
            timeout=data.get('timeout', 3600.0),
            status=QuestionStatus(data.get('status', 'pending')),
            created_at=data.get('created_at', ''),
            answer=data.get('answer'),
            answered_at=data.get('answered_at'),
        )


@dataclass
class Answer:
    """질문에 대한 답변.

    Attributes:
        question_id: 대상 질문 ID
        response: 사용자 응답
        timestamp: 답변 시각 (ISO 형식)
    """
    question_id: str
    response: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

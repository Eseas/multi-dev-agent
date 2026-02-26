"""기획서(planning-spec.md) 파서.

순수 마크다운 기획서를 파싱하여 구조화된 데이터로 변환한다.
YAML 프론트매터 없이 마크다운 본문에서 구현 방법 개수(N), 기술 스택 등을 추출한다.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import logging


logger = logging.getLogger(__name__)


@dataclass
class MethodSpec:
    """구현 방법 하나의 스펙."""
    name: str
    description: str = ""
    tech_stack: List[str] = field(default_factory=list)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    concern: str = ""  # 통합 모드: "frontend", "backend" 등


@dataclass
class PlanningSpec:
    """파싱된 기획서 데이터."""
    title: str
    raw_content: str
    num_approaches: int
    methods: List[MethodSpec] = field(default_factory=list)
    mode: str = "alternative"  # "alternative" (대안 비교) | "concern" (통합)


def parse_planning_spec(spec_path: Path) -> PlanningSpec:
    """기획서를 파싱하여 PlanningSpec으로 변환한다.

    Args:
        spec_path: planning-spec.md 파일 경로

    Returns:
        파싱된 PlanningSpec

    Raises:
        FileNotFoundError: 파일이 존재하지 않을 때
        ValueError: 파싱에 실패했을 때
    """
    if not spec_path.exists():
        raise FileNotFoundError(f"기획서 파일 없음: {spec_path}")

    content = spec_path.read_text(encoding='utf-8')
    return _parse_content(content)


def _parse_content(content: str) -> PlanningSpec:
    """마크다운 텍스트를 파싱한다."""
    title = _extract_title(content)
    mode = _extract_pipeline_mode(content)
    methods = _extract_methods(content)
    declared_n = _extract_declared_n(content)

    # N 결정: 선언된 N > 메서드 카운트 > 기본값 1
    if declared_n is not None:
        num_approaches = declared_n
    elif methods:
        num_approaches = len(methods)
    else:
        num_approaches = 1

    # N=1인데 방법 섹션 없으면, 구현 방법 섹션 전체를 하나의 방법으로 처리
    if num_approaches == 1 and not methods:
        method_content = _extract_method_section_content(content)
        if method_content:
            methods = [MethodSpec(
                name="기본 구현",
                description=method_content,
                tech_stack=_extract_tech_from_text(method_content)
            )]

    return PlanningSpec(
        title=title,
        raw_content=content,
        num_approaches=num_approaches,
        methods=methods,
        mode=mode,
    )


def _extract_title(content: str) -> str:
    """H1 제목을 추출한다."""
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "제목 없음"


def _extract_pipeline_mode(content: str) -> str:
    """파이프라인 모드를 추출한다.

    다음 패턴을 인식:
    - "## 구현 방법 (N개 통합)" → "concern"
    - "파이프라인 모드: 통합" → "concern"
    - 그 외 → "alternative" (기본값, 하위 호환)
    """
    # 패턴 1: 헤딩에서 추출 "## 구현 방법 (N개 통합)"
    if re.search(r'##\s+구현\s*방법\s*\(\d+개\s*통합\)', content):
        return "concern"

    # 패턴 2: 명시적 선언 "파이프라인 모드: 통합"
    if re.search(r'파이프라인\s*모드\s*:\s*통합', content):
        return "concern"

    return "alternative"


def _extract_declared_n(content: str) -> Optional[int]:
    """선언된 구현 방법 개수를 추출한다.

    다음 패턴을 인식:
    - "## 구현 방법 (2개 비교)"
    - "탐색할 방법 개수: 2개"
    - "탐색할 방법 개수: 자동" → None (자동 판단)
    """
    # 패턴 1: 헤딩에서 추출 "## 구현 방법 (N개 비교)"
    match = re.search(r'##\s+구현\s*방법\s*\((\d+)개\s*비교\)', content)
    if match:
        return int(match.group(1))

    # 패턴 2: 명시적 선언 "탐색할 방법 개수: N개"
    match = re.search(r'탐색할\s*방법\s*개수\s*:\s*(\d+)\s*개', content)
    if match:
        return int(match.group(1))

    # 패턴 3: "자동" → None으로 반환 (호출자가 메서드 카운트 사용)
    match = re.search(r'탐색할\s*방법\s*개수\s*:\s*자동', content)
    if match:
        return None

    return None


def _extract_methods(content: str) -> List[MethodSpec]:
    """### 방법 N 섹션들을 추출한다."""
    methods = []

    # "### 방법 N: 이름" 패턴 매칭
    pattern = r'###\s+방법\s*(\d+)\s*[:\s]*(.+?)(?=\n)'
    matches = list(re.finditer(pattern, content))

    if not matches:
        return methods

    for i, match in enumerate(matches):
        method_name = match.group(2).strip()
        start = match.end()

        # 다음 ### 또는 ## 까지의 내용 추출
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            # 다음 ## 헤딩 찾기
            next_h2 = re.search(r'\n##\s+', content[start:])
            end = start + next_h2.start() if next_h2 else len(content)

        section_content = content[start:end].strip()

        # 관심사(concern) 추출 (통합 모드용)
        concern = ""
        concern_match = re.search(r'관심사\s*[:\*]*\s*[:：]\s*(.+)', section_content)
        if not concern_match:
            concern_match = re.search(r'\*\*관심사\*\*\s*[:：]\s*(.+)', section_content)
        if concern_match:
            concern = concern_match.group(1).strip()

        methods.append(MethodSpec(
            name=method_name,
            description=section_content,
            tech_stack=_extract_tech_from_text(section_content),
            pros=_extract_list_items(section_content, '예상 장점'),
            cons=_extract_list_items(section_content, '예상 단점'),
            concern=concern,
        ))

    return methods


def _extract_method_section_content(content: str) -> str:
    """'## 구현 방법' 섹션의 본문 텍스트를 추출한다 (N=1, ### 방법 없는 경우)."""
    match = re.search(r'##\s+구현\s*방법.*?\n(.*?)(?=\n##\s+|\Z)', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ""


def _extract_tech_from_text(text: str) -> List[str]:
    """텍스트에서 기술 스택 키워드를 추출한다.

    - "라이브러리: X, Y" 패턴
    - "기술 스택: X, Y" 패턴
    """
    techs = []

    # "라이브러리:" 또는 "기술 스택:" 뒤의 내용
    patterns = [
        r'라이브러리\s*:\s*(.+)',
        r'기술\s*스택\s*:\s*(.+)',
        r'기술\s*스택\s*제안\s*:\s*(.+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            items = match.group(1).strip()
            # 쉼표 또는 ", " 로 분리
            techs.extend([t.strip() for t in re.split(r'[,、]', items) if t.strip()])

    return techs


def _extract_list_items(text: str, label: str) -> List[str]:
    """특정 레이블 아래의 리스트 항목들을 추출한다.

    예: "예상 장점:" 아래의 "- 항목1", "- 항목2"
    """
    items = []

    # "레이블:" 다음의 내용 찾기
    pattern = rf'{re.escape(label)}\s*:\s*(.+?)(?=\n\s*\*\*|\n###|\n##|\Z)'
    match = re.search(pattern, text, re.DOTALL)
    if match:
        block = match.group(1)
        # "- 항목" 패턴 추출
        for item_match in re.finditer(r'[-•]\s*(.+)', block):
            items.append(item_match.group(1).strip())

    return items

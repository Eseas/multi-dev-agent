"""기획서 유효성 검증기.

Phase 0 완료 후, Phase 1 시작 전에 실행되는 규칙 기반 검증.
AI를 사용하지 않으므로 비용이 발생하지 않으며, 밀리초 단위로 완료된다.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List
from datetime import datetime
import logging

from .atomic_write import atomic_write


logger = logging.getLogger(__name__)

# 최소 기획서 길이 (문자 수)
MIN_SPEC_LENGTH = 50


@dataclass
class ValidationResult:
    """검증 결과."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def validate_spec(spec_path: Path) -> ValidationResult:
    """기획서를 검증한다.

    3단계 검증: 구조 → 내용 → 일관성

    Args:
        spec_path: planning-spec.md 파일 경로

    Returns:
        ValidationResult
    """
    errors = []
    warnings = []

    # === 1단계: 구조 검증 ===
    if not spec_path.exists():
        errors.append("기획서 파일이 존재하지 않습니다.")
        return ValidationResult(valid=False, errors=errors)

    try:
        content = spec_path.read_text(encoding='utf-8')
    except Exception as e:
        errors.append(f"기획서 파일을 읽을 수 없습니다: {e}")
        return ValidationResult(valid=False, errors=errors)

    if len(content.strip()) < MIN_SPEC_LENGTH:
        errors.append(
            f"기획서 내용이 너무 짧습니다 ({len(content.strip())}자). "
            "구현할 내용을 구체적으로 작성해주세요."
        )
        return ValidationResult(valid=False, errors=errors)

    # H1 제목 확인
    if not re.search(r'^#\s+.+', content, re.MULTILINE):
        warnings.append("H1 제목(# 제목)이 없습니다. 기획서에 제목을 추가하는 것을 권장합니다.")

    # === 2단계: 내용 검증 ===
    # 구현 방법 섹션 존재 여부
    has_method_section = bool(re.search(
        r'##\s+구현\s*방법', content, re.MULTILINE
    ))
    if not has_method_section:
        errors.append(
            "구현 방법 섹션이 없습니다. "
            "'## 구현 방법' 섹션을 추가해주세요."
        )

    # 기술 스택 명시 여부 (최소 하나의 구체적 기술명)
    tech_patterns = [
        r'라이브러리\s*:',
        r'기술\s*스택\s*:',
        r'기술\s*스택\s*제안\s*:',
    ]
    has_tech = any(re.search(p, content) for p in tech_patterns)

    # 패턴 매칭 실패해도, 알려진 기술명이 본문에 있으면 OK
    if not has_tech:
        known_techs = [
            'React', 'Vue', 'Angular', 'Svelte', 'Next.js', 'Nuxt',
            'Express', 'Fastify', 'Django', 'Flask', 'FastAPI', 'Spring',
            'Node.js', 'Python', 'TypeScript', 'Go', 'Rust', 'Java',
            'PostgreSQL', 'MySQL', 'MongoDB', 'Redis', 'SQLite',
            'Docker', 'Kubernetes', 'AWS', 'GCP', 'Azure',
            'JWT', 'OAuth', 'GraphQL', 'REST', 'gRPC',
            'Click', 'Rich', 'Typer', 'Commander',
            'pytest', 'jest', 'vitest', 'mocha',
        ]
        has_tech = any(tech.lower() in content.lower() for tech in known_techs)

    if not has_tech:
        warnings.append(
            "기술 스택이 명시되지 않았습니다. "
            "사용할 기술을 구체적으로 적어주세요."
        )

    # === 3단계: 일관성 검증 ===
    # 헤딩에 선언된 N과 실제 ### 방법 개수 비교
    declared_n_match = re.search(
        r'##\s+구현\s*방법\s*\((\d+)개\s*비교\)', content
    )
    method_headings = re.findall(r'###\s+방법\s*\d+', content)

    if declared_n_match and method_headings:
        declared_n = int(declared_n_match.group(1))
        actual_n = len(method_headings)
        if declared_n != actual_n:
            errors.append(
                f"구현 방법 개수 불일치: "
                f"헤딩에는 {declared_n}개라 했지만 실제 방법은 {actual_n}개입니다."
            )

    # N≥2일 때 방법명 중복 확인
    if len(method_headings) >= 2:
        method_names = []
        for m in re.finditer(r'###\s+방법\s*\d+\s*[:\s]*(.+)', content):
            method_names.append(m.group(1).strip())
        seen = set()
        for name in method_names:
            if name in seen:
                errors.append(
                    f"방법명 '{name}'이 중복됩니다. "
                    "각 방법은 서로 다른 접근법이어야 합니다."
                )
            seen.add(name)

    valid = len(errors) == 0
    return ValidationResult(valid=valid, errors=errors, warnings=warnings)


def write_validation_errors(result: ValidationResult, output_dir: Path) -> Path:
    """검증 실패 보고서를 작성한다.

    Args:
        result: ValidationResult
        output_dir: 보고서를 저장할 디렉토리

    Returns:
        생성된 validation-errors.md 경로
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / 'validation-errors.md'

    lines = [
        "# 기획서 검증 실패",
        "",
        f"## 검증 일시",
        f"{datetime.now().isoformat()}",
        "",
    ]

    if result.errors:
        lines.append("## 실패 항목")
        lines.append("")
        for error in result.errors:
            lines.append(f"### ❌ {error}")
            lines.append("")

    if result.warnings:
        lines.append("## 경고 항목")
        lines.append("")
        for warning in result.warnings:
            lines.append(f"### ⚠️ {warning}")
            lines.append("")

    content = '\n'.join(lines)
    atomic_write(output_path, content)

    logger.info(f"검증 실패 보고서 작성: {output_path}")
    return output_path

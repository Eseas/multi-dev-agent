#!/usr/bin/env python3
"""
execution-plan.json → execution-plan.md 변환 스크립트
사용법: python3 execution_plan_to_md.py <input.json> <output.md>
"""

import json
import sys
from pathlib import Path


COMPLEXITY_LABEL = {
    "simple":  "🟢 Simple",
    "medium":  "🟡 Medium",
    "complex": "🔴 Complex"
}

MODE_LABEL = {
    "alternative": "Alternative (독립 대안 비교)",
    "concern":     "Concern (관심사별 분할 통합)"
}

STRATEGY_LABEL = {
    "unit":        "단위 테스트",
    "integration": "통합 테스트",
    "e2e":         "E2E 테스트",
    "mixed":       "혼합 (단위 + 통합)"
}


def json_to_md(json_path: str, output_path: str):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    lines = []
    pipeline = data['pipeline']
    stages = data['stages']

    # ── 헤더 ──────────────────────────────────────────
    lines.append("# 실행 계획서")
    lines.append("")
    lines.append(f"> **Task ID**: `{data['task_id']}`  ")
    lines.append(f"> **작성일시**: {data['created_at']}  ")
    lines.append(f"> **요구사항 참조**: `{data['requirements_ref']}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 파이프라인 설정 ───────────────────────────────
    lines.append("## 파이프라인 설정")
    lines.append("")
    lines.append("| 항목 | 값 |")
    lines.append("|------|-----|")
    lines.append(f"| 모드 | {MODE_LABEL.get(pipeline['mode'], pipeline['mode'])} |")
    lines.append(f"| 구현 개수 (N) | **{pipeline['num_approaches']}** |")
    lines.append(f"| 복잡도 | {COMPLEXITY_LABEL.get(pipeline['complexity'], pipeline['complexity'])} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 실행 단계 ─────────────────────────────────────
    lines.append("## 실행 단계")
    lines.append("")

    stage_order = [
        ("architect",    "Architect (설계)"),
        ("implementer",  "Implementer (구현)"),
        ("reviewer",     "Reviewer (리뷰)"),
        ("tester",       "Tester (테스트)"),
        ("comparator",   "Comparator (비교)"),
        ("integrator",   "Integrator (통합)"),
        ("simplifier",   "Simplifier (정리)"),
    ]

    lines.append("| 단계 | 상태 | 비고 |")
    lines.append("|------|------|------|")

    for key, label in stage_order:
        stage = stages.get(key, {})
        enabled = stage.get('enabled', False)
        status = "✅ 실행" if enabled else "⏭️ 스킵"
        notes = _stage_notes(key, stage)
        lines.append(f"| {label} | {status} | {notes} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 관심사 (concern 모드) ─────────────────────────
    concerns = data.get('concerns', [])
    if concerns:
        lines.append("## 관심사 분할")
        lines.append("")
        for i, c in enumerate(concerns, 1):
            lines.append(f"### Concern {i}: {c['name']}")
            lines.append(f"- **범위**: {c['scope']}")
            lines.append("")
        lines.append("---")
        lines.append("")

    # ── 리스크 ────────────────────────────────────────
    risk_notes = data.get('risk_notes', [])
    if risk_notes:
        lines.append("## 리스크 및 주의사항")
        lines.append("")
        for note in risk_notes:
            lines.append(f"- ⚠️ {note}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # ── 요약 ──────────────────────────────────────────
    lines.append("## 요약")
    lines.append("")
    lines.append(data.get('summary', ''))
    lines.append("")

    # ── 푸터 ──────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("> ⚠️ 이 문서는 `execution-plan.json`으로부터 자동 생성되었습니다.  ")
    lines.append("> 직접 수정하지 마세요. 변경이 필요하면 JSON을 수정 후 재생성하세요.")
    lines.append("")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✓ MD 생성 완료: {output_path}")


def _stage_notes(key: str, stage: dict) -> str:
    """단계별 부가 정보 추출"""
    parts = []

    if key == "architect" and stage.get("focus"):
        parts.append(f"포커스: {stage['focus']}")
    elif key == "implementer" and stage.get("guidelines"):
        parts.append(f"가이드라인 {len(stage['guidelines'])}건")
    elif key == "reviewer" and stage.get("focus_areas"):
        parts.append(", ".join(stage['focus_areas']))
    elif key == "tester" and stage.get("test_strategy"):
        parts.append(STRATEGY_LABEL.get(stage['test_strategy'], stage['test_strategy']))
    elif key == "comparator" and stage.get("criteria"):
        parts.append(", ".join(stage['criteria'][:3]))

    return " / ".join(parts) if parts else ""


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python3 execution_plan_to_md.py <input.json> <output.md>")
        sys.exit(1)

    json_path = sys.argv[1]
    output_path = sys.argv[2]

    if not Path(json_path).exists():
        print(f"오류: {json_path} 파일을 찾을 수 없습니다")
        sys.exit(1)

    json_to_md(json_path, output_path)

#!/usr/bin/env python3
"""
requirements.json → requirements.md 변환 스크립트
사용법: python3 json_to_md.py <input.json> <output.md>
"""

import json
import sys
from pathlib import Path
from datetime import datetime


PRIORITY_LABEL = {
    "must":   "🔴 Must",
    "should": "🟡 Should",
    "could":  "🟢 Could"
}


def json_to_md(json_path: str, output_path: str):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    lines = []

    # ── 헤더 ──────────────────────────────────────────
    lines.append("# 요구사항 명세서")
    lines.append("")
    lines.append(f"> **Task ID**: `{data['task_id']}`  ")
    lines.append(f"> **작성일시**: {data['created_at']}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── 유저 스토리 ───────────────────────────────────
    lines.append("## 유저 스토리")
    lines.append("")

    for us in data['user_stories']:
        priority = PRIORITY_LABEL.get(us.get('priority', 'should'), us.get('priority', ''))
        lines.append(f"### [{us['id']}] {us['i_want']}  `{priority}`")
        lines.append("")
        lines.append(f"| 항목 | 내용 |")
        lines.append(f"|------|------|")
        lines.append(f"| As a | {us['as_a']} |")
        lines.append(f"| I want | {us['i_want']} |")
        lines.append(f"| So that | {us['so_that']} |")
        lines.append("")
        lines.append("**Acceptance Criteria**")
        lines.append("")
        for ac in us['acceptance_criteria']:
            lines.append(f"- [ ] {ac}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # ── 범위 정의 ─────────────────────────────────────
    lines.append("## 범위 정의")
    lines.append("")
    lines.append("### ✅ In-Scope")
    lines.append("")
    for item in data['scope']['in']:
        lines.append(f"- {item}")
    lines.append("")

    lines.append("### ❌ Out-of-Scope")
    lines.append("")
    out_items = data['scope'].get('out', [])
    if out_items:
        for item in out_items:
            lines.append(f"- {item}")
    else:
        lines.append("_(없음)_")
    lines.append("")

    lines.append("---")
    lines.append("")

    # ── 보류 항목 ─────────────────────────────────────
    lines.append("## 보류 항목")
    lines.append("")
    deferred = data.get('deferred', [])
    if deferred:
        for item in deferred:
            lines.append(f"- {item}")
    else:
        lines.append("_(없음)_")
    lines.append("")

    lines.append("---")
    lines.append("")

    # ── 대화 요약 ─────────────────────────────────────
    lines.append("## 대화 요약")
    lines.append("")
    lines.append(data.get('conversation_summary', ''))
    lines.append("")

    # ── 파이프라인 힌트 (있을 때만) ───────────────────
    hint = data.get('pipeline_hint')
    if hint:
        lines.append("---")
        lines.append("")
        lines.append("## PM 참고사항")
        lines.append("")
        if 'complexity' in hint:
            lines.append(f"- **복잡도**: `{hint['complexity']}`")
        if 'requires_design' in hint:
            val = "필요" if hint['requires_design'] else "불필요"
            lines.append(f"- **설계 단계**: {val}")
        if 'notes' in hint:
            lines.append(f"- **메모**: {hint['notes']}")
        lines.append("")

    # ── 푸터 ──────────────────────────────────────────
    lines.append("---")
    lines.append("")
    lines.append("> ⚠️ 이 문서는 `requirements.json`으로부터 자동 생성되었습니다.  ")
    lines.append("> 직접 수정하지 마세요. 변경이 필요하면 JSON을 수정 후 재생성하세요.")
    lines.append("")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f"✓ MD 생성 완료: {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("사용법: python3 json_to_md.py <input.json> <output.md>")
        sys.exit(1)

    json_path = sys.argv[1]
    output_path = sys.argv[2]

    if not Path(json_path).exists():
        print(f"오류: {json_path} 파일을 찾을 수 없습니다")
        sys.exit(1)

    json_to_md(json_path, output_path)

"""Phase 간 컨텍스트 공유를 위한 요약 생성 모듈.

모든 함수는 순수 Python 문자열 처리(regex, 섹션 파싱)를 사용하며,
AI API 호출 없이 동작한다 (비용 0원).

3-Tier 요약 시스템:
  Tier 1 (Inline): 프롬프트에 직접 삽입 (~100-300 토큰)
  Tier 2 (File):   파일로 저장, 경로만 프롬프트에 포함 (~500-2,000 토큰)
  Tier 3 (Raw):    기존 파일 그대로 (conversation.txt 등), 참조하지 않음
"""

import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional


# ────────────────────────────────────────────────────────
# Transition A: Architect → Implementer
# ────────────────────────────────────────────────────────

def build_architect_inline_context(approaches_data: Dict[str, Any]) -> str:
    """approaches.json에서 Tier 1 inline context를 생성한다.

    Implementer 프롬프트에 직접 삽입되는 ~150 토큰 텍스트.
    아키텍처 제약사항, 호환성 경고, 공유 기술 결정을 추출한다.

    Args:
        approaches_data: approaches.json 파싱 결과 dict

    Returns:
        프롬프트에 삽입할 포매팅된 텍스트
    """
    approaches = approaches_data.get('approaches', [])
    if not approaches:
        return '(Architect 분석 컨텍스트 없음)'

    all_key_decisions = []
    all_trade_offs = []
    all_libraries = set()

    for approach in approaches:
        all_key_decisions.extend(approach.get('key_decisions', []))
        all_trade_offs.extend(approach.get('trade_offs', []))
        for lib in approach.get('libraries', []):
            all_libraries.add(lib)

    # 제약사항: "must", "should", "반드시", "필수" 등이 포함된 결정
    constraint_keywords = [
        'must', 'should', 'always', 'never', 'required', 'mandatory',
        '반드시', '필수', '준수', '유지', '상속', '따라',
    ]
    constraints = [
        d for d in all_key_decisions
        if any(kw in d.lower() for kw in constraint_keywords)
    ][:5]

    # 호환성 경고: 하위 호환성, 영향, 주의 등
    warning_keywords = [
        '단점', 'breaking', 'compatibility', 'backward', 'migration',
        'risk', '영향', '주의', '호환', '변경', '기존',
    ]
    warnings = [
        t for t in all_trade_offs
        if any(kw in t.lower() for kw in warning_keywords)
    ][:3]

    # 공유 기술 결정: 상위 5개 핵심 결정
    shared = all_key_decisions[:5]

    lines = []

    if constraints:
        lines.append('**아키텍처 제약사항:**')
        for c in constraints:
            lines.append(f'- {c}')
        lines.append('')

    if warnings:
        lines.append('**호환성 경고:**')
        for w in warnings:
            lines.append(f'- {w}')
        lines.append('')

    if shared and not constraints:
        lines.append('**주요 설계 결정:**')
        for s in shared:
            lines.append(f'- {s}')
        lines.append('')

    if all_libraries:
        libs = sorted(all_libraries)[:8]
        lines.append(f'**기술 스택:** {", ".join(libs)}')

    return '\n'.join(lines) if lines else '(Architect 분석 컨텍스트 없음)'


def build_architect_summary_file(approaches_data: Dict[str, Any]) -> str:
    """approaches.json에서 Tier 2 summary 마크다운을 생성한다.

    파일로 저장되어 에이전트가 Read 도구로 선택적 참조.
    ~800 토큰 분량.

    Args:
        approaches_data: approaches.json 파싱 결과 dict

    Returns:
        마크다운 형식의 요약 문자열
    """
    approaches = approaches_data.get('approaches', [])
    lines = ['# Architect 설계 요약', '']

    for i, approach in enumerate(approaches, 1):
        name = approach.get('name', f'접근법 {i}')
        lines.append(f'## 접근법 {i}: {name}')
        lines.append('')

        desc = approach.get('description', '')
        if desc:
            # 설명이 너무 길면 첫 200자만
            if len(desc) > 200:
                desc = desc[:200] + '...'
            lines.append(f'**설명**: {desc}')
            lines.append('')

        complexity = approach.get('complexity', '')
        effort = approach.get('estimated_effort', '')
        if complexity or effort:
            lines.append(f'**복잡도**: {complexity} | **예상 작업량**: {effort}')
            lines.append('')

        key_decisions = approach.get('key_decisions', [])
        if key_decisions:
            lines.append('### 주요 결정')
            for d in key_decisions:
                lines.append(f'- {d}')
            lines.append('')

        trade_offs = approach.get('trade_offs', [])
        if trade_offs:
            lines.append('### 트레이드오프')
            for t in trade_offs:
                lines.append(f'- {t}')
            lines.append('')

        libraries = approach.get('libraries', [])
        if libraries:
            lines.append(f'### 기술 스택')
            lines.append(f'{", ".join(libraries)}')
            lines.append('')

        lines.append('---')
        lines.append('')

    return '\n'.join(lines)


# ────────────────────────────────────────────────────────
# Transition B: Implementer → Reviewer/Tester
# ────────────────────────────────────────────────────────

def build_implementer_inline_context(
    impl_path: Path,
    change_summary: Dict[str, Any]
) -> str:
    """work-done.md + git 변경 요약에서 Tier 1 inline context를 생성한다.

    Reviewer/Tester 프롬프트에 직접 삽입되는 ~200 토큰 텍스트.

    Args:
        impl_path: 구현 worktree 경로
        change_summary: GitManager.get_change_summary() 결과

    Returns:
        프롬프트에 삽입할 포매팅된 텍스트
    """
    work_done_path = impl_path / 'work-done.md'

    lines = []

    if work_done_path.exists():
        content = work_done_path.read_text()

        # 구현 요약 추출
        summary = _extract_section(content, '구현 요약', max_chars=200)
        if summary:
            lines.append(f'**구현 요약**: {summary}')
            lines.append('')

        # 기술적 결정 추출
        decisions = _extract_bullet_list(content, '기술적 결정', max_items=5)
        if decisions:
            lines.append('**기술적 결정:**')
            for d in decisions:
                lines.append(f'- {d}')
            lines.append('')

        # 알려진 제한사항 추출
        limitations = _extract_bullet_list(content, '알려진 제한사항', max_items=5)
        if limitations:
            lines.append('**알려진 제한사항:**')
            for lim in limitations:
                lines.append(f'- {lim}')
            lines.append('')

    # git 변경 요약
    files_changed = change_summary.get('files_changed', 0)
    insertions = change_summary.get('insertions', 0)
    deletions = change_summary.get('deletions', 0)

    if files_changed:
        lines.append(
            f'**변경 통계**: {files_changed}개 파일 변경 '
            f'(+{insertions} -{deletions})'
        )

    new_files = change_summary.get('new_files', [])
    if new_files:
        display_files = new_files[:8]
        lines.append(f'**새 파일**: {", ".join(display_files)}')
        if len(new_files) > 8:
            lines.append(f'  외 {len(new_files) - 8}개')

    return '\n'.join(lines) if lines else '(구현 컨텍스트 없음)'


# ────────────────────────────────────────────────────────
# Transition C: Reviewer/Tester → Comparator
# ────────────────────────────────────────────────────────

def build_review_metrics(review_workspace: Path) -> Dict[str, Any]:
    """review.md에서 구조화된 리뷰 메트릭을 추출한다.

    regex 기반 파싱으로 AI 비용 없이 동작.

    Args:
        review_workspace: 리뷰 워크스페이스 디렉토리 (review.md 포함)

    Returns:
        추출된 메트릭 dict. 파싱 실패 시 available=False.
    """
    review_path = _find_file(review_workspace, ['review.md', 'code-review.md'])

    if not review_path:
        return {'available': False}

    content = review_path.read_text()

    metrics: Dict[str, Any] = {'available': True}

    # 종합 점수: "종합 점수: X/5점" 또는 "**종합 점수**: X/5점"
    score_match = re.search(
        r'종합\s*점수[:\s]*(\d+(?:\.\d+)?)\s*/\s*5', content
    )
    metrics['overall_score'] = float(score_match.group(1)) if score_match else None

    # 추천 여부
    if '✅' in content and '추천' in content:
        metrics['recommendation'] = 'recommended'
    elif '⚠️' in content:
        metrics['recommendation'] = 'conditional'
    elif '❌' in content and ('비추천' in content or '추천' in content):
        metrics['recommendation'] = 'not_recommended'
    else:
        metrics['recommendation'] = 'unknown'

    # 이슈 개수 (Critical/Major/Minor)
    metrics['critical_issues'] = len(
        re.findall(r'\[Critical\]', content, re.IGNORECASE)
    )
    metrics['major_issues'] = len(
        re.findall(r'\[Major\]', content, re.IGNORECASE)
    )
    metrics['minor_issues'] = len(
        re.findall(r'\[Minor\]', content, re.IGNORECASE)
    )

    # 관점별 점수 테이블: "| 코드 품질 | X/5 |"
    aspect_scores = {}
    for match in re.finditer(
        r'\|\s*([^|]+?)\s*\|\s*(\d+(?:\.\d+)?)\s*/\s*5',
        content
    ):
        aspect_name = match.group(1).strip()
        # 테이블 헤더 행은 건너뛰기
        if aspect_name in ('관점', '구현', '점수', '---', '기준'):
            continue
        aspect_scores[aspect_name] = float(match.group(2))
    if aspect_scores:
        metrics['aspect_scores'] = aspect_scores

    # 장점 (상위 3개)
    strengths = _extract_bold_items_after(content, '장점', max_items=3)
    if strengths:
        metrics['strengths'] = strengths

    # 약점/이슈 제목 (상위 3개)
    weaknesses = _extract_issue_titles(content, max_items=3)
    if weaknesses:
        metrics['weaknesses'] = weaknesses

    return metrics


def build_test_metrics(test_workspace: Path) -> Dict[str, Any]:
    """테스트 결과에서 구조화된 메트릭을 추출한다.

    Args:
        test_workspace: 테스트 워크스페이스 디렉토리

    Returns:
        추출된 테스트 메트릭 dict. 파싱 실패 시 available=False.
    """
    metrics: Dict[str, Any] = {'available': False}

    # test_results.json 확인
    results_path = _find_file(
        test_workspace,
        ['test_results.json', 'test-results.json']
    )
    if results_path:
        try:
            data = json.loads(results_path.read_text())
            metrics['available'] = True
            metrics['status'] = data.get('status', 'unknown')
        except (json.JSONDecodeError, OSError):
            pass

    # test_output.log 또는 test-results.md에서 추가 메트릭 추출
    for log_name in ['test_output.log', 'test-results.md']:
        log_path = test_workspace / log_name
        if log_path.exists():
            content = log_path.read_text()
            _extract_test_numbers(content, metrics)
            metrics['available'] = True
            break

    return metrics


def build_phase3_summary(
    impl_results: List[Dict[str, Any]],
    task_dir: Path
) -> Dict[str, Any]:
    """Phase 3 결과를 하나의 통합 summary로 생성한다.

    Comparator에 전달할 정규화된 메트릭.

    Args:
        impl_results: Phase 2 결과 리스트 (review/test workspace 포함)
        task_dir: 태스크 디렉토리

    Returns:
        통합 summary dict
    """
    summary: Dict[str, Any] = {'implementations': []}

    for impl in impl_results:
        if not impl.get('success'):
            continue

        aid = impl.get('approach_id', 0)
        entry: Dict[str, Any] = {
            'approach_id': aid,
            'approach_name': impl.get('approach', {}).get('name', ''),
            'branch': impl.get('branch', ''),
        }

        # 리뷰 메트릭
        review_ws = impl.get('review_workspace', '')
        if review_ws:
            entry['review'] = build_review_metrics(Path(review_ws))

        # 테스트 메트릭
        test_ws = impl.get('test_workspace', '')
        if test_ws:
            entry['test'] = build_test_metrics(Path(test_ws))

        # 구현 요약 (간략)
        impl_path = impl.get('worktree_path', '')
        if impl_path:
            change_summary = impl.get('change_summary', {})
            files_changed = change_summary.get('files_changed', 0)
            entry['files_changed'] = files_changed

        summary['implementations'].append(entry)

    return summary


def format_phase3_inline(summary: Dict[str, Any]) -> str:
    """build_phase3_summary 결과를 Comparator 프롬프트용 Tier 1 텍스트로 변환.

    구현체당 ~250 토큰, N=2이면 ~500 토큰.

    Args:
        summary: build_phase3_summary() 반환값

    Returns:
        프롬프트에 삽입할 포매팅된 텍스트
    """
    impls = summary.get('implementations', [])
    if not impls:
        return '(Phase 3 메트릭 없음)'

    lines = []

    for entry in impls:
        aid = entry.get('approach_id', '?')
        name = entry.get('approach_name', 'N/A')
        lines.append(f'### impl-{aid}: {name}')
        lines.append('')

        # 리뷰 메트릭
        review = entry.get('review', {})
        if review.get('available'):
            score = review.get('overall_score')
            score_str = f'{score}/5' if score is not None else 'N/A'
            rec = review.get('recommendation', 'unknown')
            rec_map = {
                'recommended': '✅ 추천',
                'conditional': '⚠️ 조건부',
                'not_recommended': '❌ 비추천',
            }
            rec_str = rec_map.get(rec, rec)

            critical = review.get('critical_issues', 0)
            major = review.get('major_issues', 0)
            minor = review.get('minor_issues', 0)

            lines.append(f'**리뷰**: 점수 {score_str}, {rec_str}')
            lines.append(f'  이슈: Critical {critical}개, Major {major}개, Minor {minor}개')

            strengths = review.get('strengths', [])
            if strengths:
                lines.append(f'  장점: {"; ".join(strengths)}')

            weaknesses = review.get('weaknesses', [])
            if weaknesses:
                lines.append(f'  약점: {"; ".join(weaknesses)}')
        else:
            lines.append('**리뷰**: (없음)')

        # 테스트 메트릭
        test = entry.get('test', {})
        if test.get('available'):
            parts = []
            if 'tests_passed' in test:
                parts.append(f'통과 {test["tests_passed"]}개')
            if 'tests_failed' in test:
                parts.append(f'실패 {test["tests_failed"]}개')
            if 'coverage_percent' in test:
                parts.append(f'커버리지 {test["coverage_percent"]}%')
            status = test.get('status', '')
            if status:
                parts.append(f'상태: {status}')
            lines.append(f'**테스트**: {", ".join(parts) if parts else "완료"}')
        else:
            lines.append('**테스트**: (없음)')

        # 변경 통계
        files_changed = entry.get('files_changed', 0)
        if files_changed:
            lines.append(f'**변경**: {files_changed}개 파일')

        lines.append('')

    return '\n'.join(lines)


# ────────────────────────────────────────────────────────
# 헬퍼 함수
# ────────────────────────────────────────────────────────

def _extract_section(
    content: str,
    section_name: str,
    max_chars: int = 300
) -> str:
    """마크다운에서 특정 섹션의 본문을 추출한다.

    '## 섹션명' 또는 '### 섹션명' 아래의 텍스트를 반환.
    """
    pattern = rf'#{1,3}\s*{re.escape(section_name)}.*?\n(.*?)(?=\n#{1,3}\s|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return ''

    text = match.group(1).strip()
    # 불릿 리스트를 한 문장으로 합치기
    lines = [
        line.lstrip('- ').strip()
        for line in text.split('\n')
        if line.strip() and not line.startswith('#')
    ]
    result = ' '.join(lines)

    if len(result) > max_chars:
        result = result[:max_chars] + '...'

    return result


def _extract_bullet_list(
    content: str,
    section_name: str,
    max_items: int = 5
) -> List[str]:
    """마크다운에서 특정 섹션의 불릿 리스트를 추출한다."""
    pattern = rf'#{1,3}\s*{re.escape(section_name)}.*?\n(.*?)(?=\n#{1,3}\s|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []

    text = match.group(1)
    items = []
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped.startswith('- '):
            item = stripped[2:].strip()
            if item:
                items.append(item)
                if len(items) >= max_items:
                    break

    return items


def _extract_bold_items_after(
    content: str,
    keyword: str,
    max_items: int = 3
) -> List[str]:
    """마크다운에서 특정 키워드 이후의 볼드 항목을 추출한다.

    "### ✅ 장점" 같은 섹션 아래의 "**항목명**" 패턴을 찾는다.
    """
    # 키워드가 포함된 섹션 찾기
    pattern = rf'#{1,3}\s*[✅⚠️❌]?\s*{re.escape(keyword)}.*?\n(.*?)(?=\n#{1,3}\s|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return []

    section_text = match.group(1)
    items = []
    for bold_match in re.finditer(r'\*\*([^*]+)\*\*', section_text):
        item = bold_match.group(1).strip()
        if item and len(item) > 3:
            items.append(item)
            if len(items) >= max_items:
                break

    return items


def _extract_issue_titles(content: str, max_items: int = 3) -> List[str]:
    """review.md에서 [Critical]/[Major] 이슈 제목을 추출한다."""
    items = []
    for match in re.finditer(
        r'\[(?:Critical|Major)\]\s*(.+?)(?:\n|$)', content, re.IGNORECASE
    ):
        title = match.group(1).strip()
        if title:
            items.append(title)
            if len(items) >= max_items:
                break
    return items


def _find_file(directory: Path, candidates: List[str]) -> Optional[Path]:
    """디렉토리에서 후보 파일명 목록 중 존재하는 첫 번째를 반환한다."""
    if not directory or not Path(directory).exists():
        return None
    for name in candidates:
        path = Path(directory) / name
        if path.exists():
            return path
    return None


def _extract_test_numbers(content: str, metrics: Dict[str, Any]) -> None:
    """테스트 출력에서 통과/실패 수, 커버리지를 추출한다."""
    # 통과: "X passed", "X개 통과", "X tests passed"
    passed_match = re.search(
        r'(\d+)\s*(?:passed|tests?\s+passed|개\s*통과)', content, re.IGNORECASE
    )
    if passed_match:
        metrics['tests_passed'] = int(passed_match.group(1))

    # 실패: "X failed", "X개 실패"
    failed_match = re.search(
        r'(\d+)\s*(?:failed|tests?\s+failed|개\s*실패)', content, re.IGNORECASE
    )
    if failed_match:
        metrics['tests_failed'] = int(failed_match.group(1))

    # 커버리지: "XX%" (전체 커버리지 행에서)
    coverage_match = re.search(
        r'(?:coverage|커버리지)[:\s]*(\d+(?:\.\d+)?)\s*%', content, re.IGNORECASE
    )
    if coverage_match:
        metrics['coverage_percent'] = float(coverage_match.group(1))

# 새 프로젝트 시작하기

## 1분 요약

1. 폴더 만들기
2. STEP 1 프롬프트로 청사진 작성
3. STEP 2 프롬프트로 개발 문서 작성
4. Gemini에 두 문서 붙여넣어 리뷰받기
5. STEP 4 프롬프트로 병렬 개발 계획 작성
6. 각 Agent에게 계획 배분

---

## 실제 시작 방법

### Step 0: 폴더 생성

```bash
mkdir -p workspaces/{서비스명}/planning/in-progress
mkdir -p workspaces/{서비스명}/work
```

### Step 1: 청사진 작성

Claude Code에게:
```
prompts/new-project/01-blueprint.md 파일을 읽고,
아래 내용으로 청사진을 작성해줘:

프로젝트명: [이름]
설명: [설명]
기능:
- [기능1]
- [기능2]
```

### Step 2: 개발 문서 작성

Claude Code에게:
```
prompts/new-project/02-dev-spec.md 파일을 읽고,
방금 작성한 blueprint.md를 기반으로 dev-spec.md를 작성해줘.
```

### Step 3: Gemini 리뷰

1. `prompts/new-project/03-gemini-review-prompt.md` 열기
2. 프롬프트 + blueprint.md + dev-spec.md를 Gemini에 붙여넣기
3. 피드백을 `gemini-feedback.md`에 정리

### Step 4: 개발 계획 수립

Claude Code에게:
```
prompts/new-project/04-dev-plan-parallel.md 파일을 읽고,
dev-spec.md와 gemini-feedback.md를 기반으로 병렬 개발 계획을 작성해줘.
```

### Step 5: 구현 시작

개발 계획의 Phase 0부터 순서대로 진행.
Phase 1부터는 병렬로 Agent 배분.

---

## 파일 체크리스트

```
workspaces/{서비스명}/planning/in-progress/
├── blueprint.md          ✅ (Step 1)
├── dev-spec.md           ✅ (Step 2)
├── gemini-feedback.md    ✅ (Step 3, 사람이 정리)
└── dev-plan.md           ✅ (Step 4)
```

모든 파일이 완성되면 `planning/completed/`로 이동 후 구현 시작.

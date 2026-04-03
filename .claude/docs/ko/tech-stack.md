# tech-stack.md — 서비스 기술 스택 정의

## 개요

**서비스 단위로 작성하는 기술 환경 기준서**. `workspaces/{서비스}/tech-stack.md`에 위치.
해당 서비스의 모든 기획서와 구현 에이전트의 기술 기준이 된다.

---

## 관리 규칙

1. **에이전트 필수 확인**: 구현 에이전트는 코드 작성 전 반드시 이 문서 확인
2. **선행 업데이트**: 기획서에 이 문서에 없는 새 기술 등장 시, 구현 시작 전 이 문서 먼저 수정
3. **버전 명시**: 모든 주요 의존성은 사용 버전 명시
4. **변경 이력**: 새 기술 도입 시 하단 변경 이력에 기록

---

## 템플릿

`workspaces/{서비스}/tech-stack.md`로 복사하여 작성:

```markdown
# {서비스} - 기술 스택 및 환경 정의

- **서비스명**: {서비스}
- **최초 작성일**: {YYYY-MM-DD}
- **최종 수정일**: {YYYY-MM-DD}

---

## Root Project 구성

| 폴더 | 레포 URL | 역할 |
|------|----------|------|
| `{서비스}-BE/` | https://github.com/.../... | 메인 API 서버 |
| `{서비스}-FE/` | https://github.com/.../... | 웹 클라이언트 (선택) |

---

## 기술 스택

### 백엔드 ({서비스}-BE)

- **언어 및 런타임**: {예: Java 21 / Node.js 20}
- **프레임워크**: {예: Spring Boot 3.3 / Express 4}
- **빌드 도구**: {예: Gradle 8 / npm}
- **데이터베이스**: {예: MySQL 8.0 / PostgreSQL 15}
- **ORM / 쿼리**: {예: Spring Data JPA + QueryDSL / Prisma 5}
- **캐시**: {예: Redis 7 / 없음}
- **메시지 큐**: {예: Kafka / 없음}
- **인증**: {예: JWT (JJWT 0.12) / Spring Security Session}
- **테스트**: {예: JUnit 5 + Mockito / Jest}

### 프론트엔드 ({서비스}-FE)

- **언어**: {예: TypeScript 5}
- **프레임워크**: {예: Next.js 14 / React 18}
- **상태관리**: {예: Zustand / Redux Toolkit}
- **스타일**: {예: TailwindCSS 3}
- **HTTP 클라이언트**: {예: axios 1.6 / fetch}
- **테스트**: {예: Vitest / Jest + RTL}
- **E2E 테스트**: {예: Playwright / 없음}

### 인프라

- **클라우드**: {예: AWS / 없음}
- **컨테이너**: {예: Docker / 없음}
- **CI/CD**: {예: GitHub Actions / 없음}
- **배포 대상**: {예: EC2 / Vercel / 로컬}

---

## 주요 의존성

### 백엔드

| 패키지 | 버전 | 용도 |
|--------|------|------|
| spring-boot-starter-web | 3.3.x | REST API |
| {패키지} | {버전} | {용도} |

### 프론트엔드

| 패키지 | 버전 | 용도 |
|--------|------|------|
| next | 14.x | 프레임워크 |
| {패키지} | {버전} | {용도} |

---

## 코딩 컨벤션

### API 응답 형식

\`\`\`json
{ "data": { ... }, "error": null }
{ "data": null, "error": { "message": "...", "code": "ERROR_CODE" } }
\`\`\`

### 인증 방식
{예: Authorization: Bearer {JWT}. 토큰 만료 1시간, 리프레시 토큰 7일}

### 브랜치 전략
{예: main(배포) / develop(통합) / feature/{기능명}}

---

## 변경 이력

| 날짜 | 변경 내용 | 관련 기획서 |
|------|-----------|------------|
| {YYYY-MM-DD} | 최초 작성 | - |
```

---

## 주의사항

- 버전 반드시 명시: "Spring Boot 최신" 대신 "Spring Boot 3.3.x"
- 없는 항목은 "없음" 명시 — 빈 칸 금지
- 기획서 실행 전 이 문서와 충돌 여부 확인
- 구현 후 새 의존성은 변경 이력에 기록

# tech-stack.md — 서비스 기술 스택 정의 문서

## 개요

이 문서는 **서비스 단위로 작성하는 기술 환경 기준서**다.
각 서비스의 워크스페이스 루트(`workspaces/{서비스명}/tech-stack.md`)에 위치한다.

해당 서비스에서 실행되는 모든 기획서와 구현 에이전트의 기술 기준이 된다.

---

## 관리 규칙

1. **에이전트 필수 확인**: 구현 에이전트는 코드 작성 전 반드시 이 문서를 확인한다
2. **선행 업데이트**: 기획서에 이 문서에 없는 새 기술이 등장하면, 구현 시작 전에 이 문서를 먼저 수정한다
3. **버전 명시**: 모든 주요 의존성은 사용 버전을 명시한다
4. **변경 이력 기록**: 새 기술 도입 시 하단 변경 이력에 기록한다

---

## 문서 템플릿

아래 템플릿을 복사하여 `workspaces/{서비스명}/tech-stack.md`로 저장하고 작성한다.

---

```markdown
# {서비스명} - 기술 스택 및 환경 정의

- **서비스명**: {서비스명}
- **최초 작성일**: {YYYY-MM-DD}
- **최종 수정일**: {YYYY-MM-DD}

---

## Root Project 구성

| 폴더 | 레포 URL | 역할 |
|------|----------|------|
| `{서비스명}-BE/` | https://github.com/.../...  | 메인 API 서버 |
| `{서비스명}-FE/` | https://github.com/.../... | 웹 클라이언트 (있는 경우) |

---

## 기술 스택

### 백엔드 ({서비스명}-BE)

- **언어 및 런타임**: {예: Java 21 / Node.js 20}
- **프레임워크**: {예: Spring Boot 3.3 / Express 4}
- **빌드 도구**: {예: Gradle 8 / Maven / npm}
- **데이터베이스**: {예: MySQL 8.0 / PostgreSQL 15}
- **ORM / 쿼리**: {예: Spring Data JPA + QueryDSL / Prisma 5}
- **캐시**: {예: Redis 7 / 없음}
- **메시지 큐**: {예: RabbitMQ / Kafka / 없음}
- **인증**: {예: JWT (JJWT 0.12) / Spring Security Session}
- **테스트**: {예: JUnit 5 + Mockito / Jest}

### 프론트엔드 ({서비스명}-FE)

- **언어**: {예: TypeScript 5}
- **프레임워크**: {예: Next.js 14 / React 18 / Vue 3}
- **상태관리**: {예: Zustand / Redux Toolkit / Pinia}
- **스타일**: {예: TailwindCSS 3 / styled-components}
- **HTTP 클라이언트**: {예: axios 1.6 / fetch}
- **테스트**: {예: Vitest / Jest + React Testing Library}
- **E2E 테스트**: {예: Playwright / 없음}

### 인프라

- **클라우드**: {예: AWS / GCP / 없음}
- **컨테이너**: {예: Docker / 없음}
- **CI/CD**: {예: GitHub Actions / 없음}
- **배포 대상**: {예: EC2 / Vercel / 로컬}

---

## 주요 의존성

### 백엔드

| 패키지 | 버전 | 용도 |
|--------|------|------|
| spring-boot-starter-web | 3.3.x | REST API |
| spring-boot-starter-security | 3.3.x | 인증/인가 |
| spring-boot-starter-data-jpa | 3.3.x | ORM |
| jjwt-api | 0.12.x | JWT 생성/검증 |
| querydsl-jpa | 5.x | 복잡한 쿼리 |
| {패키지명} | {버전} | {용도} |

### 프론트엔드

| 패키지 | 버전 | 용도 |
|--------|------|------|
| next | 14.x | 프레임워크 |
| react | 18.x | UI |
| axios | 1.6.x | HTTP 클라이언트 |
| zustand | 4.x | 상태관리 |
| {패키지명} | {버전} | {용도} |

---

## 코딩 컨벤션

### API 응답 형식

```json
// 성공
{ "data": { ... }, "error": null }

// 실패
{ "data": null, "error": { "message": "에러 메시지", "code": "ERROR_CODE" } }
```

### 에러 코드 체계

| 범위 | 의미 |
|------|------|
| 1000~1999 | 인증/인가 오류 |
| 2000~2999 | 입력값 유효성 오류 |
| 3000~3999 | 비즈니스 로직 오류 |
| 9000~9999 | 서버 내부 오류 |

### 인증 방식

{예: Authorization: Bearer {JWT} 헤더 방식. 토큰 만료 시간 1시간, 리프레시 토큰 7일}

### 로깅

{예: SLF4J + Logback. 요청/응답 로깅은 MDC로 correlation ID 포함}

### 브랜치 전략

{예: main(배포) / develop(통합) / feature/{기능명}(기능 개발)}

---

## 환경변수 목록

| 변수명 | 용도 | 예시값 |
|--------|------|--------|
| `DB_URL` | 데이터베이스 접속 URL | `jdbc:mysql://localhost:3306/dbname` |
| `DB_USERNAME` | DB 사용자명 | `app_user` |
| `DB_PASSWORD` | DB 비밀번호 | (시크릿 관리) |
| `JWT_SECRET` | JWT 서명 키 | (시크릿 관리) |
| `REDIS_HOST` | Redis 호스트 | `localhost` |
| {변수명} | {용도} | {예시} |

---

## 변경 이력

| 날짜 | 변경 내용 | 관련 기획서 |
|------|-----------|------------|
| {YYYY-MM-DD} | 최초 작성 | - |
| {YYYY-MM-DD} | {변경 내용} | {기획서 경로} |
```

---

## 작성 시 주의사항

- **버전을 반드시 명시**: "Spring Boot 최신" 대신 "Spring Boot 3.3.x"
- **없는 항목은 "없음" 명시**: 빈 칸으로 두지 않음
- **기획서 실행 전 확인**: 새 기획서가 이 문서와 충돌하지 않는지 확인
- **구현 후 업데이트**: 새 의존성이 추가되면 변경 이력에 기록

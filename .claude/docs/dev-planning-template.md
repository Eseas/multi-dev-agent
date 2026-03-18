# 개발 기획 문서 템플릿

개발 기획 문서는 다음 5개 섹션으로 구성된다.
각 기획 단위(기능/작업)마다 이 형식을 따른다.

> **AI 에이전트 필수 사전 작업**:
> 1. 이 문서를 읽고 코드를 구현하기 **전에**, 해당 서비스의 `tech-stack.md`를 먼저 확인한다.
> 2. 이 기획 문서에서 `tech-stack.md`에 없는 새로운 기술 스펙(라이브러리, 도구, 컨벤션 등)이 등장하면, **구현 시작 전에 `tech-stack.md`를 먼저 수정**한다.
> 3. 모호한 표현 없이 모든 세부 사항을 명시하세요.

---

## 문서 구조

```
1. 프로젝트 이름
2. 달성 목표
3. 개발 진행 과정 순서    ← API 스펙 + 데이터 모델 포함
4. 개별 테스트 내용       ← 시나리오 목록 → 실제 테스트 코드
5. 전체 테스트 내용       ← Playwright E2E
```

> 기술 스택 및 환경 정보는 `tech-stack.md`에서 관리한다. (위치: `workspaces/{서비스명}/tech-stack.md`)

---

## 0. 환경 및 기술 스택

AI 에이전트가 코드를 생성할 환경을 명확히 정의한다.

```markdown
### 기술 스택
- **백엔드**: {언어 + 버전} / {프레임워크 + 버전} / {데이터베이스}
- **프론트엔드**: {언어 + 버전} / {프레임워크 + 버전}
- **인프라**: {클라우드/서버 환경}

### 대상 Root Project
- {서비스명}-BE: {경로 또는 레포 URL}
- {서비스명}-FE: {경로 또는 레포 URL}

### 주요 의존성 (핵심만)
- {라이브러리}: {버전} - {용도}
```

---

## 1. 프로젝트 이름

해당 작업이 속하는 서비스/프로젝트명과 기능명을 명시한다.

```
{서비스명} - {기능명}
```

**예시:** `Dailyword - 관리자 대시보드 생성`

---

## 2. 달성 목표

이 작업이 완료되었을 때 달성해야 하는 상태를 구체적으로 기술한다.

작성 원칙:
- 측정 가능한 기준 사용
- "~할 수 있다" 형태의 완료 조건
- 기술적 요구사항과 비즈니스 요구사항 분리

```markdown
### 비즈니스 목표
- 관리자가 웹 브라우저에서 사용자 통계를 조회할 수 있다
- 관리자가 콘텐츠를 CRUD 할 수 있다

### 기술적 목표
- API 응답 시간 < 500ms
- 관리자 인증/인가 적용
```

---

## 3. 개발 진행 과정 순서

목표 달성을 위한 구현 단계를 순서대로 나열한다.
각 단계는 독립적으로 완료 확인이 가능해야 한다.

작성 원칙:
- 단계 간 의존성 명시
- 각 단계의 산출물 명시
- 대상 root project 표기 (FE/BE 등)
- **데이터 모델 변경이 있는 경우 스키마를 명시**
- **API를 생성하는 경우 스펙을 명시** (full OpenAPI 불필요, 핵심 정보만)

```markdown
### Step 1: {단계명}
- **대상**: {root project} (예: Dailyword-BE)
- **작업 내용**:
  - 구체적 구현 항목 1
  - 구체적 구현 항목 2
- **데이터 모델** (변경 있을 경우):
  ```sql
  -- 변경/추가되는 테이블 스키마
  ALTER TABLE users ADD COLUMN role ENUM('user', 'admin') DEFAULT 'user';
  ```
- **API 스펙** (API 생성 시):
  ```
  POST /admin/login
  Request:  { email: string, password: string }
  Response: { token: string, expiresIn: number }
  Error:    401 { message: "Invalid credentials" }
  ```
- **산출물**: {파일/API/화면 등}
- **의존성**: 없음 / Step N 완료 후

### Step 2: {단계명}
- **대상**: {root project}
- **작업 내용**:
  - ...
- **API 스펙**:
  ```
  GET /admin/stats/users?period={daily|weekly|monthly}
  Headers: Authorization: Bearer {token}
  Response: { totalUsers: number, activeUsers: number, ... }
  Error:    403 { message: "Forbidden" }
  ```
- **산출물**: ...
- **의존성**: Step 1
```

---

## 4. 개별 테스트 내용

각 Step에 대응하는 단위/통합 테스트 코드를 기술한다.
실제 실행 가능한 테스트 코드가 들어가는 섹션이다.

작성 원칙:
- Step 번호와 매핑
- 테스트 프레임워크 명시 (pytest, Jest, JUnit 등)
- **시나리오 목록을 먼저 나열한 후, 테스트 코드 작성**
- Given-When-Then 구조

```markdown
### Step 1 테스트: {테스트 대상}

**프레임워크**: {pytest / Jest / JUnit 등}

**테스트 시나리오**:
- [정상] 유효한 관리자 계정으로 로그인 시 JWT 토큰 반환
- [이상] 잘못된 비밀번호로 로그인 시 401 반환
- [이상] 관리자 권한 없는 계정으로 관리자 API 접근 시 403 반환
- [엣지] 만료된 토큰으로 접근 시 401 반환

\`\`\`{language}
describe('관리자 인증 API', () => {
  test('유효한 관리자 토큰으로 접근 시 200 반환', async () => {
    // Given
    const token = await getAdminToken();

    // When
    const res = await request(app).get('/admin/dashboard').set('Authorization', `Bearer ${token}`);

    // Then
    expect(res.status).toBe(200);
  });

  test('일반 사용자 토큰으로 접근 시 403 반환', async () => {
    // Given
    const token = await getUserToken();

    // When
    const res = await request(app).get('/admin/dashboard').set('Authorization', `Bearer ${token}`);

    // Then
    expect(res.status).toBe(403);
  });
});
\`\`\`

### Step 2 테스트: {테스트 대상}
...
```

---

## 5. 전체 테스트 내용

모든 Step이 통합된 상태에서의 E2E 테스트를 기술한다.
**Playwright**를 사용하여 실제 사용자 시나리오를 검증한다.

작성 원칙:
- 사용자 관점의 시나리오 기반
- 핵심 플로우(Happy Path) 우선
- 실패 시나리오 포함
- 테스트 데이터 셋업/정리 포함
- `data-testid` 속성 사용 권장 (FE 구현과 연동)

```markdown
### E2E 시나리오 1: {시나리오명}

**사전 조건**: {필요한 상태/데이터}
**테스트 데이터**: { adminEmail: 'admin@test.com', adminPassword: 'test1234' }

\`\`\`typescript
import { test, expect } from '@playwright/test';

test.describe('관리자 대시보드 전체 흐름', () => {
  test.beforeEach(async ({ page }) => {
    // 관리자 로그인
    await page.goto('/admin/login');
    await page.fill('[name="email"]', 'admin@example.com');
    await page.fill('[name="password"]', 'admin-password');
    await page.click('button[type="submit"]');
    await page.waitForURL('/admin/dashboard');
  });

  test('대시보드에서 사용자 통계를 확인하고 콘텐츠를 생성한다', async ({ page }) => {
    // 통계 확인
    await expect(page.locator('[data-testid="user-count"]')).toBeVisible();
    await expect(page.locator('[data-testid="daily-active"]')).toBeVisible();

    // 콘텐츠 생성
    await page.click('[data-testid="create-content"]');
    await page.fill('[name="title"]', '새 콘텐츠');
    await page.fill('[name="body"]', '콘텐츠 내용');
    await page.click('button[type="submit"]');

    // 생성 확인
    await expect(page.locator('text=새 콘텐츠')).toBeVisible();
  });

  test('권한 없는 페이지 접근 시 리다이렉트된다', async ({ page }) => {
    // 로그아웃
    await page.click('[data-testid="logout"]');

    // 대시보드 직접 접근 시도
    await page.goto('/admin/dashboard');

    // 로그인 페이지로 리다이렉트
    await expect(page).toHaveURL('/admin/login');
  });
});
\`\`\`

### E2E 시나리오 2: {시나리오명}
...
```

---

## 예시: 완성된 기획 문서

```markdown
# Dailyword - 관리자 대시보드 생성

> **tech-stack.md 참조**: workspaces/dailyword/tech-stack.md
> **신규 스펙**: recharts ^2.0.0 (차트 컴포넌트) → tech-stack.md에 추가 필요

## 1. 프로젝트 이름
Dailyword - 관리자 대시보드 생성

## 2. 달성 목표
### 비즈니스 목표
- 관리자가 일별/주별/월별 사용자 활동 통계를 조회할 수 있다
- 관리자가 단어 콘텐츠를 추가/수정/삭제할 수 있다

### 기술적 목표
- 관리자 전용 인증 (role-based)
- 대시보드 초기 로드 < 2초
- 통계 데이터 캐싱 (5분)

## 3. 개발 진행 과정 순서

### Step 1: 관리자 인증 API
- **대상**: Dailyword-BE
- **작업 내용**:
  - 관리자 role 추가 (User 테이블 확장)
  - 관리자 로그인 엔드포인트
  - role 기반 미들웨어
- **데이터 모델**:
  ```sql
  ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user';
  CREATE INDEX idx_users_role ON users(role);
  ```
- **API 스펙**:
  ```
  POST /admin/login
  Request:  { email: string, password: string }
  Response: { token: string, expiresIn: number }
  Error:    401 { message: "Invalid credentials" }
            403 { message: "Not an admin account" }
  ```
- **산출물**: POST /admin/login, adminAuth 미들웨어
- **의존성**: 없음

### Step 2: 통계 API
- **대상**: Dailyword-BE
- **작업 내용**:
  - 사용자 활동 집계 쿼리 (users 테이블 기반)
  - 통계 API 엔드포인트
  - Redis 캐싱 (TTL: 300초)
- **API 스펙**:
  ```
  GET /admin/stats/users?period=daily
  Headers: Authorization: Bearer {token}
  Response: { totalUsers: number, newUsers: number, activeUsers: number }
  Error:    403 { message: "Forbidden" }
  ```
- **산출물**: GET /admin/stats/users, GET /admin/stats/content
- **의존성**: Step 1

## 4. 개별 테스트 내용
### Step 1 테스트: 관리자 인증

**프레임워크**: Jest + supertest

**테스트 시나리오**:
- [정상] 관리자 계정 로그인 성공 → 200 + JWT 반환
- [이상] 잘못된 비밀번호 → 401
- [이상] 일반 유저가 관리자 API 접근 → 403
- [엣지] 만료 토큰 접근 → 401

...테스트 코드...

## 5. 전체 테스트 내용
### E2E 시나리오 1: 관리자 로그인 → 통계 확인 → 콘텐츠 생성
**테스트 데이터**: { email: 'admin@test.com', password: 'admin1234' }

...Playwright 테스트 코드...
```

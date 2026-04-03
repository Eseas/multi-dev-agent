# tech-stack.md — Service Tech Stack Definition

## Overview

A **per-service tech environment reference** located at `workspaces/{service}/tech-stack.md`.
All specs and implementation agents within that service use this as the technical baseline.

---

## Management Rules

1. **Agent pre-check**: Implementer must read this before writing any code
2. **Update first**: If a spec introduces tech not listed here, update this doc before implementation
3. **Version explicit**: All major dependencies must specify versions
4. **Changelog**: Record new tech additions in the changelog section

---

## Template

Copy to `workspaces/{service}/tech-stack.md`:

```markdown
# {service} - Tech Stack & Environment

- **Service**: {service}
- **Created**: {YYYY-MM-DD}
- **Updated**: {YYYY-MM-DD}

---

## Root Projects

| Folder | Repo URL | Role |
|--------|----------|------|
| `{service}-BE/` | https://github.com/.../... | Main API server |
| `{service}-FE/` | https://github.com/.../... | Web client (optional) |

---

## Tech Stack

### Backend ({service}-BE)

- **Language & Runtime**: {e.g. Java 21 / Node.js 20}
- **Framework**: {e.g. Spring Boot 3.3 / Express 4}
- **Build Tool**: {e.g. Gradle 8 / npm}
- **Database**: {e.g. MySQL 8.0 / PostgreSQL 15}
- **ORM / Query**: {e.g. Spring Data JPA + QueryDSL / Prisma 5}
- **Cache**: {e.g. Redis 7 / none}
- **Message Queue**: {e.g. Kafka / none}
- **Auth**: {e.g. JWT (JJWT 0.12) / Spring Security Session}
- **Test**: {e.g. JUnit 5 + Mockito / Jest}

### Frontend ({service}-FE)

- **Language**: {e.g. TypeScript 5}
- **Framework**: {e.g. Next.js 14 / React 18}
- **State Management**: {e.g. Zustand / Redux Toolkit}
- **Styling**: {e.g. TailwindCSS 3}
- **HTTP Client**: {e.g. axios 1.6 / fetch}
- **Test**: {e.g. Vitest / Jest + RTL}
- **E2E**: {e.g. Playwright / none}

### Infra

- **Cloud**: {e.g. AWS / none}
- **Container**: {e.g. Docker / none}
- **CI/CD**: {e.g. GitHub Actions / none}
- **Deploy**: {e.g. EC2 / Vercel / local}

---

## Key Dependencies

### Backend

| Package | Version | Purpose |
|---------|---------|---------|
| spring-boot-starter-web | 3.3.x | REST API |
| {package} | {version} | {purpose} |

### Frontend

| Package | Version | Purpose |
|---------|---------|---------|
| next | 14.x | Framework |
| {package} | {version} | {purpose} |

---

## Coding Conventions

### API Response Format

\`\`\`json
{ "data": { ... }, "error": null }
{ "data": null, "error": { "message": "...", "code": "ERROR_CODE" } }
\`\`\`

### Auth Method
{e.g. Authorization: Bearer {JWT}. Token TTL 1h, refresh token 7d}

### Branch Strategy
{e.g. main (deploy) / develop (integration) / feature/{name}}

---

## Changelog

| Date | Change | Related Spec |
|------|--------|--------------|
| {YYYY-MM-DD} | Initial creation | - |
```

---

## Guidelines

- Specify exact versions: "Spring Boot 3.3.x" not "latest"
- Mark absent items as "none" — no blank cells
- Check before running a spec — ensure no conflicts with this doc
- Update after implementation — record new dependencies in changelog

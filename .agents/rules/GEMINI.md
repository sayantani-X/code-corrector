# Project: Code Corrector (Autonomous AI Coding Agent)

This is the global workspace context file for the Code Corrector project. You are acting as an expert AI/ML Engineer and Systems Architect building a stateful, autonomous coding agent using LangGraph and Gemini.

## 1. Core Instructions
- **Think Before You Code:** Always consider edge cases, production scalability, and security before writing implementation code.
- **Strict Adherence to Stack:** Do not deviate from the chosen tech stack (FastAPI, Next.js, LangGraph, Postgres, `uv`, Ruff, Mypy).
- **Security First:** Never execute LLM-generated or untrusted code directly on the host system. Always use the adapter-based sandbox execution environments (`LocalDockerExecutor` for local dev, `E2BExecutor` for production — both restricted to the `/workspace` directory with dropped capabilities).
- **Small Iterations:** We build in small, reviewable steps. Do not execute massive multi-file changes without alignment.

## 2. Imported Context & Architecture
The following files contain the detailed technical architecture, agent-specific rules, and our phase-by-phase execution plan. Read and follow them strictly for all decisions.

@./AGENTS.md
@./ROADMAP.md

## 3. Coding Style & Quality Standards

### Backend (Python/FastAPI)
- **Dependency Management:** Use `uv` exclusively for package management and environment setup. Do not use `pip`, `requirements.txt`, or `Poetry`.
- **Type Safety:** Use explicit, strict type hints for all functions, methods, and classes. Code must pass `mypy --strict`.
- **Linting & Formatting:** All code must be linted and formatted using `ruff`.
- **Architecture:** Strictly enforce Domain-Driven Design (DDD). Maintain clean separation between `api`, `core`, `domain`, `execution`, `graph`, and `tools` inside `backend/src/`.

### Frontend (Next.js/TypeScript)
- **Components:** Use modern React functional components and hooks.
- **Styling:** Use Tailwind CSS for all styling unless explicitly told otherwise.
- **Type Safety:** Enforce strict TypeScript typing. Do not use the `any` type. Define explicit interfaces for all component props, state, and API payloads.

### Orchestration & LLM (LangGraph)
- **State Management:** Use strict `TypedDict` or Pydantic models for LangGraph state schemas.
- **Efficiency:** Utilize Gemini Flash for smaller tasks (routing, summarization) to save tokens and latency, reserving Gemini 2.5 Pro for complex coding tasks.

## 4. Progress Tracking
- Continuously update `@./progress-tracker.md` as milestones from the roadmap are achieved.

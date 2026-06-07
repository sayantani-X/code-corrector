# AI Agent Instructions for Code Corrector

This document provides core instructions and context for AI coding agents working in the `code-corrector` workspace.

## Reference Documentation
- **Architecture & Roadmap:** Please refer to the [ROADMAP.md](ROADMAP.md) for the end-to-end plan, tech stack, and phase-by-phase deliverables.

## Tech Stack & Tooling Guidelines
When generating code or proposing solutions, strictly adhere to the following stack:
- **Backend/API:** Python (`>= 3.12`) with FastAPI.
- **Frontend:** TypeScript with Next.js and Tailwind CSS. Node.js `>= 20`.
- **AI/Orchestration:** LangGraph, LangSmith, and Vertex AI via the `google-genai` SDK (Gemini 3.1 Pro / 3.5 Flash / 3.1 Flash Lite).
- **Execution Environment:** Adapter Pattern — `BaseExecutor` interface with `LocalDockerExecutor` (Docker SDK) for local dev and `CloudRunJobExecutor` (GCP Cloud Run Jobs) for production.
- **Database:** PostgreSQL (with `pgvector`).
- **Dependency Management:** Use `uv` (do NOT use `Poetry` or `pip` + `requirements.txt`).
- **Code Quality:** Ensure all Python code is formatted/linted with `ruff` and strictly typed for `mypy`.

## Architectural Rules (DDD)
- **Separation of Concerns:** Keep the frontend in `frontend/` and backend in `backend/`.
- **Backend Structure:** Follow Domain-Driven Design (DDD). Group code logically into `api/`, `core/`, `domain/`, `execution/`, `graph/`, and `tools/` within `backend/src/`.
- **Sandbox Boundary:** When creating tools that manipulate files, strictly constrain all file reads and writes to the `workspace/` directory. The agent must never modify the host machine outside of this sandbox.

## Test & Execution Commands
*(To be populated as the project layout is scaffolded — typically `pytest` for backend and `npm run dev` for frontend).*
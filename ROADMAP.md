# Autonomous AI Software Engineer: Production Implementation Roadmap

**Project Objective:** Build a stateful, autonomous coding agent using LangGraph and Gemini 3.1 Pro capable of iteratively writing code, executing tests in an isolated sandbox, and self-correcting based on traceback logs. Designed specifically to demonstrate enterprise-grade engineering practices for top-tier AI/ML Engineer roles.

**Cloud Platform:** Google Cloud Platform (GCP) — Free Trial ($300 credits). All managed services are selected to stay within GCP's ecosystem and free-tier/trial limits where possible.

---

## 1. Tech Stack & Architecture

*   **Backend / API:** FastAPI (Python). Fast, async, built-in standard for modern Python APIs.
*   **Frontend:** Next.js (TypeScript/React). Demonstrates modern decoupled web architecture.
*   **Orchestration & Observability:** LangGraph + LangSmith.
*   **Code Execution:** Adapter Pattern. `BaseExecutor` interface with `LocalDockerExecutor` (Docker SDK) for local development and `CloudRunJobExecutor` (GCP Cloud Run Jobs) for production.
*   **Database:** PostgreSQL with `pgvector`.
    *   *Local Dev:* Docker container via `docker-compose`.
    *   *Production:* Cloud SQL for PostgreSQL (GCP).
*   **LLM Engine:** Vertex AI via the `google-genai` SDK (`google-genai` Python package).
    *   *Coding:* Gemini 3.1 Pro (`gemini-3.1-pro-preview`).
    *   *Routing / Summarization:* Gemini 3.5 Flash (`gemini-3.5-flash`) or Gemini 3.1 Flash Lite (`gemini-3.1-flash-lite-preview`).
*   **Caching:**
    *   *Local Dev:* Redis via `docker-compose`.
    *   *Production:* Memorystore for Redis (GCP).
*   **Container Registry:** Artifact Registry (GCP) — stores Docker images for the sandbox executor and backend API.
*   **Deployment:** Cloud Run (GCP) — serves the FastAPI backend and Next.js frontend as containerized services.
*   **Secrets Management:** Secret Manager (GCP) — stores API keys, DB credentials, and other sensitive config.

---

## 2. Production-Grade Infrastructure

*   **Dependency Management:** `uv` (No `pip`/`requirements.txt` or `Poetry`).
*   **Code Quality:** `Ruff` for linting/formatting, `Mypy` for strict static type checking.
*   **Testing:**
    *   *Unit Tests:* `pytest` with mocked LLM calls and Docker executions.
    *   *Integration Tests:* Real agent runs on trivial tasks.
    *   *LLM Evals:* LangSmith Evals to measure hallucination rates and fix accuracy.
*   **CI/CD:** GitHub Actions (blocking merges if Ruff, Mypy, or Pytest fails). Deploys to Cloud Run on merge to `main`.

---

## 3. MNC-Ready Complexity Enhancements

*   **Context Window Management:** `LogSummarizer` node (using Gemini 3.5 Flash via Vertex AI) to condense massive 10,000-line stack traces before passing them back to the Coder node.
*   **Resiliency:** Wrap AI calls in `Tenacity` (exponential backoff) to natively handle 429 Rate Limits and Vertex AI quota errors.
*   **Multi-Agent Design:** Implement a `Security Reviewer` (runs `bandit`) and `Code Reviewer` between the Coder and Executor nodes.
*   **Semantic Caching:** Redis / Memorystore layer to skip LLM calls for identical or semantically similar prompts.
*   **Docker Security Defaults:** For the local `LocalDockerExecutor`, ensure you plan to run containers with dropped capabilities, no root access, and a read-only filesystem (except for the `/workspace` mount) to simulate the strict security environment of a production sandbox.

---

## 4. GCP Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                      Google Cloud Platform                  │
│                                                             │
│  ┌──────────────┐   SSE    ┌───────────────────────┐        │
│  │  Cloud Run   │◄────────►│     Cloud Run          │       │
│  │  (Frontend)  │          │     (FastAPI Backend)   │       │
│  └──────────────┘          └──────┬───────┬──────────┘       │
│                                   │       │                  │
│                    ┌──────────────┘       └──────────┐       │
│                    ▼                                 ▼       │
│  ┌──────────────────────┐          ┌────────────────────┐   │
│  │  Cloud SQL           │          │  Vertex AI          │   │
│  │  (PostgreSQL+pgvec)  │          │  (Gemini 2.5 Pro/   │   │
│  │                      │          │   Flash)             │   │
│  └──────────────────────┘          └────────────────────┘   │
│                                                             │
│  ┌──────────────────────┐          ┌────────────────────┐   │
│  │  Memorystore         │          │  Cloud Run Jobs     │   │
│  │  (Redis Cache)       │          │  (Sandbox Executor) │   │
│  └──────────────────────┘          └────────────────────┘   │
│                                                             │
│  ┌──────────────────────┐          ┌────────────────────┐   │
│  │  Artifact Registry   │          │  Secret Manager     │   │
│  │  (Docker Images)     │          │  (Keys & Creds)     │   │
│  └──────────────────────┘          └────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Phase-by-Phase Execution Plan

### Repository Structure (DDD Design)
```text
project-root/
├── .github/workflows/       # CI/CD pipelines (lint, test, deploy to Cloud Run)
├── backend/
│   ├── pyproject.toml       # uv dependencies
│   ├── Dockerfile           # Backend container image
│   ├── src/
│   │   ├── api/             # FastAPI routes & endpoints
│   │   ├── core/            # Config, security, logging setup
│   │   ├── domain/          # Pydantic schemas, state TypedDicts
│   │   ├── execution/       # Docker / Cloud Run Jobs sandbox adapters
│   │   ├── graph/           # LangGraph nodes, edges, conditional logic
│   │   └── tools/           # Custom @tools for the agents
│   └── tests/               # pytest suite and LLM evals
├── frontend/                # Next.js application
│   └── Dockerfile           # Frontend container image
├── workspace/               # Local mount dir for Docker sandbox
├── docker-compose.yml       # Local Postgres, Redis & Backend setup
├── .pre-commit-config.yaml  # Pre-commit hooks for Ruff/Mypy
├── GEMINI.md                # Workspace context for Gemini CLI
├── CLAUDE.md                # Behavioral guidelines for Claude
├── AGENTS.md                # Agent-specific rules & stack constraints
├── progress-tracker.md      # Milestone tracking
└── README.md
```

### Sprint 1: Infrastructure & Foundation (Week 1)
*   **Goal:** Establish CI/CD, dependency management, GCP project setup, and core interfaces.
*   **Tasks:**
    *   Initialize backend dependencies with `uv`, configure `ruff.toml`, and set up pre-commits.
    *   Set up GCP project: enable Vertex AI API, Cloud Run API, Cloud SQL Admin API, Artifact Registry API, and Secret Manager API.
    *   Configure `google-genai` SDK with Vertex AI backend (project ID, region).
    *   Write GitHub Actions for CI (lint + test) and CD (build & push to Artifact Registry, deploy to Cloud Run).
    *   Implement the `execution` module using the Adapter Pattern (`BaseExecutor` → `LocalDockerExecutor`).
*   **Benchmark:** The execution module can run a Python script in an isolated container and return `stdout/stderr` natively, fully covered by `pytest`. Vertex AI Gemini calls work end-to-end.

### Sprint 2: State, Tools, and The Graph (Week 2)
*   **Goal:** Build the LangGraph state machine.
*   **Tasks:**
    *   Define Domain State (`TypedDict`).
    *   Implement local `read_file`/`write_file` tools (restricted to `./workspace`).
    *   Implement graph nodes and conditional looping edges for errors:
        *   **`Planner`:** The strategic brain of the agent. Translates an ambiguous, high-level user request into a concrete, ordered sequence of engineering tasks. Sets scope and establishes the source of truth for global graph state so downstream nodes never lose context.
        *   **`Coder`:** Generates or patches code based on the plan and current state. Powered by Gemini 3.1 Pro (`gemini-3.1-pro-preview`) via Vertex AI.
        *   **`Reviewer`:** Runs static analysis (`ruff`, `bandit`) and validates code quality before execution.
        *   **`Executor`:** Runs code in the sandboxed environment and captures `stdout`/`stderr`.
    *   Enforce a **max retry budget** (e.g., 5 iterations) and a **per-run timeout** on the self-correction loop to prevent infinite cycling on unsolvable problems. On exhaustion, the graph must gracefully exit and surface the final error to the user.
*   **Benchmark:** A CLI script where the graph takes a prompt, writes code, fails, patches it, and succeeds within the retry budget, with full traces visible in LangSmith.

### Sprint 3: Persistence, Telemetry & Complexity (Week 3)
*   **Goal:** Add memory, checkpointing, and token management.
*   **Tasks:**
    *   Spin up Postgres via `docker-compose` (local) or connect to Cloud SQL (prod). Implement `langgraph-checkpoint-postgres`.
    *   Implement the `LogSummarizer` for massive tracebacks (using Gemini 3.5 Flash / 3.1 Flash Lite via Vertex AI).
    *   Implement Human-in-the-Loop (HITL) interrupts.
    *   Set up semantic caching with Redis (local `docker-compose` / Memorystore in prod).
*   **Benchmark:** Pause an execution, kill the terminal, restart the script, and resume from Postgres state seamlessly.

### Sprint 4: API, UI, and Deployment (Week 4)
*   **Goal:** Decouple the system into a microservice architecture and deploy to GCP.
*   **Tasks:**
    *   Wrap the LangGraph invocation in a FastAPI endpoint (`POST /agent/task`, etc.).
    *   Implement **API authentication** (API key or JWT-based) on all endpoints.
    *   Use **Server-Sent Events (SSE)** to stream LangGraph node events, tool calls, and logs to the frontend in real-time.
    *   Build a Next.js frontend with a split pane: Chat (left) and live file/terminal diff (right), consuming the SSE stream.
    *   Implement the `CloudRunJobExecutor` adapter for production sandboxed code execution.
    *   Containerize backend and frontend, push images to Artifact Registry, and deploy to Cloud Run.
    *   Store all secrets (Vertex AI service account key, DB credentials, LangSmith API key) in Secret Manager.
*   **Benchmark:** Complete End-to-End automated debugging loop triggered and monitored via the Web UI, running on Cloud Run, with authenticated access and real-time streaming output.
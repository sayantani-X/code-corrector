from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from src.core.config import settings
from src.core.db import get_db_pool
from src.domain.state import AgentState
from src.graph.nodes import coder_node, executor_node, planner_node, reviewer_node
from src.graph.summarizer import summarizer_node


def hitl_planner_node(state: AgentState) -> dict[str, Any]:
    """Node that conditionally interrupts the graph after planning."""
    if not state.get("auto_approve_planner") and settings.enable_hitl_planner:
        response = interrupt("Review planner output?")
        if isinstance(response, dict) and response.get("action") == "reject":
            raise ValueError("Planner output was rejected by the user.")
    return {}


def hitl_executor_node(state: AgentState) -> dict[str, Any]:
    """Node that conditionally interrupts the graph before executing code."""
    if not state.get("auto_approve_executor") and settings.enable_hitl_executor:
        response = interrupt("Review execution?")
        if isinstance(response, dict) and response.get("action") == "reject":
            raise ValueError("Execution was rejected by the user.")
    return {}


def route_start(state: AgentState) -> str:
    """Routes to planner or directly to coder based on bypass_planner toggle."""
    if state.get("bypass_planner"):
        print("--- [Start] Bypassing Planner (Direct-to-Coder toggle active) ---")
        return "coder"
    return "planner"

# Define the conditional routing logic after the Reviewer Node
def route_after_review(state: AgentState) -> str:
    """
    Decides where to transition after the Reviewer checks the code.
    - If there are issues and we have retries left: route to Summarizer to condense logs.
    - If there are issues but we are out of retry budget: exit gracefully.
    - If there are no issues: route to the Executor to run the code.
    """
    if state.get("review_comments"):
        if state["retry_count"] >= state["max_retries"]:
            print(
                "--- [Reviewer] Quality issues found, but max retry budget "
                f"({state['max_retries']}) exhausted. Exiting. ---"
            )
            return END
        print("--- [Reviewer] Quality issues found. Routing to LogSummarizer... ---")
        return "summarizer"

    print("--- [Reviewer] Quality checks passed. Routing to Executor... ---")
    return "hitl_executor"


# Define the conditional routing logic after the Executor Node
def route_after_execution(state: AgentState) -> str:
    """
    Decides where to transition after the sandboxed code runs.
    - If execution failed and we have retries left: route to Summarizer to condense logs.
    - If execution failed and we are out of retry budget: exit.
    - If execution succeeded and there are remaining steps in the plan: route to Coder.
    - If execution succeeded and we completed the plan: exit.
    """
    if state["exit_code"] != 0:
        if state["retry_count"] >= state["max_retries"]:
            print(
                "--- [Executor] Execution failed, but max retry budget "
                f"({state['max_retries']}) exhausted. Exiting. ---"
            )
            return END
        print("--- [Executor] Execution failed. Routing to LogSummarizer... ---")
        return "summarizer"

    # Execution succeeded (exit_code == 0). Check if there are remaining steps in the plan.
    current_idx = state["current_step_index"]
    plan_len = len(state["plan"])

    if current_idx < plan_len - 1:
        print(
            f"--- [Executor] Step {current_idx + 1}/{plan_len} completed "
            "successfully. Routing to Coder for next step... ---"
        )
        return "coder"

    print("--- [Executor] All plan steps completed successfully. Workflow finished. ---")
    return END


# Create the LangGraph StateGraph initialized with our AgentState structure
workflow = StateGraph(AgentState)

# Register the nodes in the state machine
workflow.add_node("planner", planner_node)
workflow.add_node("hitl_planner", hitl_planner_node)
workflow.add_node("coder", coder_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("hitl_executor", hitl_executor_node)
workflow.add_node("executor", executor_node)
workflow.add_node("summarizer", summarizer_node)

# Set up the static transitions
workflow.add_conditional_edges(START, route_start, {"planner": "planner", "coder": "coder"})
workflow.add_edge("planner", "hitl_planner")
workflow.add_edge("hitl_planner", "coder")
workflow.add_edge("coder", "reviewer")
workflow.add_edge("summarizer", "coder")  # After summarizing errors, route back to coder to patch
workflow.add_edge("hitl_executor", "executor")

# Set up the conditional routing edges
workflow.add_conditional_edges(
    "reviewer", route_after_review, {"summarizer": "summarizer", "hitl_executor": "hitl_executor", END: END}
)

workflow.add_conditional_edges(
    "executor", route_after_execution, {"summarizer": "summarizer", "coder": "coder", END: END}
)


_app_instance = None

async def get_app() -> Any:
    """
    Asynchronously compiles and returns the executable graph.
    Configures the PostgreSQL checkpointer for state persistence and configures
    the Human-In-The-Loop (HITL) manual breakpoints.
    The compiled app is cached globally to prevent concurrent database setup conflicts.
    """
    global _app_instance
    if _app_instance is not None:
        return _app_instance

    # Get the global asynchronous database connection pool
    pool = await get_db_pool()

    # Initialize the LangGraph Postgres Saver for persistence
    checkpointer = AsyncPostgresSaver(pool)

    # Ensure the required schema tables exist
    await checkpointer.setup()

    # Compile the workflow graph (interrupts handled natively inside nodes now)
    app = workflow.compile(
        checkpointer=checkpointer,
    )

    _app_instance = app
    return _app_instance

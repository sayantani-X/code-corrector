from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from typing import Any
from langgraph.graph import END, START, StateGraph

from src.core.config import settings
from src.core.db import get_db_pool
from src.domain.state import AgentState
from src.graph.nodes import coder_node, executor_node, planner_node, reviewer_node
from src.graph.summarizer import summarizer_node


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
    return "executor"


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
workflow.add_node("coder", coder_node)
workflow.add_node("reviewer", reviewer_node)
workflow.add_node("executor", executor_node)
workflow.add_node("summarizer", summarizer_node)

# Set up the static transitions
workflow.add_edge(START, "planner")
workflow.add_edge("planner", "coder")
workflow.add_edge("coder", "reviewer")
workflow.add_edge("summarizer", "coder")  # After summarizing errors, route back to coder to patch

# Set up the conditional routing edges
workflow.add_conditional_edges(
    "reviewer", route_after_review, {"summarizer": "summarizer", "executor": "executor", END: END}
)

workflow.add_conditional_edges(
    "executor", route_after_execution, {"summarizer": "summarizer", "coder": "coder", END: END}
)


async def get_app() -> Any:
    """
    Asynchronously compiles and returns the executable graph.
    Configures the PostgreSQL checkpointer for state persistence and configures
    the Human-In-The-Loop (HITL) manual breakpoints.
    """
    # Get the global asynchronous database connection pool
    pool = await get_db_pool()

    # Initialize the LangGraph Postgres Saver for persistence
    checkpointer = AsyncPostgresSaver(pool)

    # Ensure the required schema tables exist
    await checkpointer.setup()

    # Configure Human-in-the-Loop Interrupts based on settings
    interrupt_before = []
    interrupt_after = []

    if settings.enable_hitl_executor:
        interrupt_before.append("executor")

    if settings.enable_hitl_planner:
        interrupt_after.append("planner")

    # Compile the workflow graph
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=interrupt_before if interrupt_before else None,
        interrupt_after=interrupt_after if interrupt_after else None,
    )

    return app

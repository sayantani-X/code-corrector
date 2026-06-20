from langgraph.graph import END, START, StateGraph

from src.domain.state import AgentState
from src.graph.nodes import coder_node, executor_node, planner_node, reviewer_node


# Define the conditional routing logic after the Reviewer Node
def route_after_review(state: AgentState) -> str:
    """
    Decides where to transition after the Reviewer checks the code.
    - If there are ruff/bandit issues and we have retries left: route back to the Coder to fix.
    - If there are issues but we are out of retry budget: exit gracefully.
    - If there are no issues: route to the Executor to run the code.
    """
    if state.get("review_comments"):
        # If code quality checks failed, check if we have remaining budget
        if state["retry_count"] >= state["max_retries"]:
            print(
                "--- [Reviewer] Quality issues found, but max retry budget "
                f"({state['max_retries']}) exhausted. Exiting. ---"
            )
            return END
        print("--- [Reviewer] Quality issues found. Routing back to Coder to fix... ---")
        return "coder"

    print("--- [Reviewer] Quality checks passed. Routing to Executor... ---")
    return "executor"


# Define the conditional routing logic after the Executor Node
def route_after_execution(state: AgentState) -> str:
    """
    Decides where to transition after the sandboxed code runs.
    - If execution failed (exit_code != 0) and we have retries left: route to Coder to patch.
    - If execution failed and we are out of retry budget: exit.
    - If execution succeeded and there are remaining steps in the plan:
      route to Coder for the next step.
    - If execution succeeded and we completed the plan: exit.
    """
    if state["exit_code"] != 0:
        if state["retry_count"] >= state["max_retries"]:
            print(
                "--- [Executor] Execution failed, but max retry budget "
                f"({state['max_retries']}) exhausted. Exiting. ---"
            )
            return END
        print("--- [Executor] Execution failed. Routing back to Coder for self-correction... ---")
        return "coder"

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

# Set up the static transitions
workflow.add_edge(START, "planner")
workflow.add_edge("planner", "coder")
workflow.add_edge("coder", "reviewer")

# Set up the conditional routing edges
workflow.add_conditional_edges(
    "reviewer", route_after_review, {"coder": "coder", "executor": "executor", END: END}
)

workflow.add_conditional_edges("executor", route_after_execution, {"coder": "coder", END: END})

# Compile the workflow graph into an executable application
app = workflow.compile()

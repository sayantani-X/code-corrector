import shutil
import sys
from typing import Any

from src.domain.state import AgentState
from src.graph.graph import app
from src.tools.file_tools import get_resolved_workspace_dir


def _clean_workspace_dir() -> None:
    """
    Cleans the workspace directory to ensure run isolation.
    """
    workspace_dir = get_resolved_workspace_dir()
    if workspace_dir.exists():
        for item in workspace_dir.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as e:
                print(f"[Warning] Failed to delete workspace item '{item.name}': {e}")
    workspace_dir.mkdir(parents=True, exist_ok=True)


def _print_node_log(node_name: str, node_state: dict[str, Any]) -> None:
    """
    Prints descriptive progress logs for the finished node.
    """
    print(f"\n>>> [Node: {node_name}] finished execution.")

    if node_name == "planner":
        print(f"  Plan generated: {node_state.get('plan')}")
        print(f"  Entry Point: {node_state.get('entry_point')}")
    elif node_name == "coder":
        files_written = list(node_state.get("files", {}).keys())
        print(f"  Coder updated workspace. Current files: {files_written}")
    elif node_name == "reviewer":
        comments = node_state.get("review_comments")
        if comments:
            print(f"  Reviewer issues found:\n{comments}")
        else:
            print("  Reviewer: Code passed checks (0 warnings/errors).")
    elif node_name == "executor":
        print(f"  Executor Exit Code: {node_state.get('exit_code')}")
        stdout = node_state.get("stdout", "").strip()
        stderr = node_state.get("stderr", "").strip()
        if stdout:
            print(f"  [Stdout]:\n{stdout}")
        if stderr:
            print(f"  [Stderr/Traceback]:\n{stderr}")


def run_agent(task: str, max_retries: int = 5) -> dict[str, Any]:
    """
    Executes the autonomous agent graph for the given task.
    Streams progress logs from each node.
    """
    # 1. Clean workspace directory
    _clean_workspace_dir()

    # 2. Define the initial state of the agent workflow
    # Explicitly typed to AgentState so that mypy matches pregel.stream input type correctly
    initial_state: AgentState = {
        "task": task,
        "plan": [],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "main.py",
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "review_comments": "",
        "retry_count": 0,
        "max_retries": max_retries,
    }

    print("=" * 65)
    print("Starting Autonomous Coding Agent")
    print(f"Task: {task}")
    print(f"Max Retries Budget: {max_retries}")
    print("=" * 65)

    final_state = {}

    # 3. Stream the graph execution node-by-node
    for event in app.stream(initial_state):
        for node_name, node_state in event.items():
            _print_node_log(node_name, node_state)
            final_state = node_state

    print("\n" + "=" * 65)
    print("Agent Execution Completed")
    print("=" * 65)
    return final_state


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m src.graph.cli "<task_description>" [max_retries]')
        sys.exit(1)

    task_description = sys.argv[1]
    max_retries_budget = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    run_agent(task_description, max_retries_budget)

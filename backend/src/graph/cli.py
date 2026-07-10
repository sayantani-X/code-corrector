import asyncio
import shutil
import sys
import uuid
from typing import Any

from src.core.db import close_db
from src.domain.state import AgentState
from src.graph.graph import get_app
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
    elif node_name == "summarizer":
        stderr_sum = node_state.get("stderr_summary", "").strip()
        review_sum = node_state.get("review_summary", "").strip()
        if stderr_sum:
            print(f"  [Traceback Summary]:\n{stderr_sum}")
        if review_sum:
            print(f"  [Review Summary]:\n{review_sum}")


async def run_agent(task: str, max_retries: int = 5) -> dict[str, Any]:
    """
    Executes the autonomous agent graph for the given task asynchronously.
    Streams progress logs from each node, saves persistence checkpoints,
    and supports Human-In-The-Loop (HITL) interrupt requests.
    """
    # 1. Clean workspace directory
    _clean_workspace_dir()

    # 2. Define the initial state of the agent workflow
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
        "stderr_summary": "",
        "review_summary": "",
    }

    print("=" * 65)
    print("Starting Autonomous Coding Agent")
    print(f"Task: {task}")
    print(f"Max Retries Budget: {max_retries}")
    print("=" * 65)

    try:
        # Retrieve the asynchronously compiled LangGraph app
        app = await get_app()

        # We need a unique thread_id to allow Postgres to track checkpoints correctly
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        final_state = {}

        # 3. Stream the graph execution node-by-node (first run)
        async for event in app.astream(initial_state, config):
            for node_name, node_state in event.items():
                _print_node_log(node_name, node_state)
                final_state = node_state

        # 4. Handle HITL Interrupts (if graph pauses instead of terminating)
        while True:
            # Check the current status of the graph using aget_state
            graph_state = await app.aget_state(config)

            # If there is no 'next' node, the execution reached END successfully.
            if not graph_state.next:
                break

            next_node = graph_state.next[0]
            print(f"\n[HITL INTERRUPT] Graph execution paused before entering node: '{next_node}'.")

            # Contextual manual review prompts based on where we are
            if next_node == "planner":
                # We paused AFTER planner generated the plan
                print("Do you approve the generated plan and wish to continue to the Coder? [y/N]")
            elif next_node == "executor":
                # We paused BEFORE the sandbox executes the untrusted code
                print("Do you approve running the generated code in the Docker sandbox? [y/N]")
            else:
                print(f"Do you wish to continue into {next_node}? [y/N]")

            user_input = input("Decision > ").strip().lower()

            if user_input in ["y", "yes"]:
                print("Continuing execution...")
                # Resume execution by passing None for initial state and providing the config
                async for event in app.astream(None, config):
                    for node_name, node_state in event.items():
                        _print_node_log(node_name, node_state)
                        final_state = node_state
            else:
                print("Execution rejected by user. Terminating process.")
                break

        print("\n" + "=" * 65)
        print("Agent Execution Completed")
        print("=" * 65)
        return final_state

    finally:
        # Ensure database connections are gracefully released
        await close_db()


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python -m src.graph.cli "<task_description>" [max_retries]')
        sys.exit(1)

    task_description = sys.argv[1]
    max_retries_budget = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    # Fix for psycopg async connection pool on Windows (requires SelectorEventLoop)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Run the asynchronous main function natively
    asyncio.run(run_agent(task_description, max_retries_budget))


if __name__ == "__main__":
    main()

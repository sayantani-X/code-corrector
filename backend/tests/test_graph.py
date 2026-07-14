import shutil
from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from src.domain.state import AgentState
from src.graph.graph import route_after_execution, route_after_review
from src.graph.nodes import planner_node, reviewer_node
from src.tools.file_tools import get_resolved_workspace_dir, list_files, read_file, write_file


def _clear_workspace() -> None:
    """
    Helper function to delete files and folders inside the workspace.
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
                print(f"[Fixture Warning] Failed to delete '{item.name}': {e}")


@pytest.fixture(autouse=True)
def clean_workspace_fixture() -> Generator[None, None, None]:
    """
    Autouse fixture that runs before and after each test case.
    It cleans out all files inside the workspace to ensure test isolation.
    """
    _clear_workspace()
    get_resolved_workspace_dir().mkdir(parents=True, exist_ok=True)
    yield
    _clear_workspace()


def test_file_tools_path_traversal() -> None:
    """
    Verifies that the path validation function raises ValueError
    when trying to read or write files outside the workspace root.
    """
    # 1. Test directory traversal escape in write_file
    with pytest.raises(ValueError) as excinfo:
        write_file("../escaping_file.py", "print('Should fail')")
    assert "Access Denied" in str(excinfo.value)

    # 2. Test directory traversal escape in read_file
    with pytest.raises(ValueError) as excinfo:
        read_file("../escaping_file.py")
    assert "Access Denied" in str(excinfo.value)


def test_file_tools_success() -> None:
    """
    Verifies successful file write, read, and list operations within the workspace sandbox.
    """
    filename = "subdir/test_script.py"
    content = "print('Hello Test!')"

    # Write file
    write_msg = write_file(filename, content)
    assert "Successfully wrote file" in write_msg

    # Read file
    read_content = read_file(filename)
    assert read_content == content

    # List files
    files = list_files()
    assert "subdir/test_script.py" in files


def test_reviewer_node_clean_code() -> None:
    """
    Verifies that the Reviewer node returns no comments and does not increment
    retry count when checking clean, lint-free python code.
    """
    # Write a perfectly compliant Python function
    write_file("clean.py", "def add_numbers(a: int, b: int) -> int:\n    return a + b\n")

    state: AgentState = {
        "task": "Review clean file",
        "plan": [],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "clean.py",
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "review_comments": "",
        "retry_count": 0,
        "max_retries": 5,
    }

    result = reviewer_node(state)
    assert result["review_comments"] == ""
    assert result["retry_count"] == 0


def test_reviewer_node_with_issues() -> None:
    """
    Verifies that the Reviewer node detects lint issues (e.g. unused import)
    and increments the retry count to trigger self-correction.
    """
    # Write a file with an unused import (Ruff check violation)
    write_file("dirty.py", "import os\n\ndef my_func() -> None:\n    pass\n")

    state: AgentState = {
        "task": "Review dirty file",
        "plan": [],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "dirty.py",
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "review_comments": "",
        "retry_count": 0,
        "max_retries": 5,
    }

    result = reviewer_node(state)
    assert "dirty.py" in result["review_comments"]
    assert "Ruff Linting issues" in result["review_comments"]
    # Retry count should be incremented since checks failed
    assert result["retry_count"] == 1


@patch("src.core.llm.generate_content_with_retry_async", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_planner_node_mocked(mock_generate: AsyncMock) -> None:
    """
    Verifies that the Planner node generates the step-by-step plan and entry point
    by parsing Gemini's structured JSON response.
    """
    # Mock the return values of the Google GenAI SDK Client
    mock_generate.return_value = (
        '{"steps": ["Step 1: Write main.py", "Step 2: Run main.py"], "entry_point": "main.py"}'
    )

    state: AgentState = {
        "task": "Write basic script",
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
        "max_retries": 5,
    }

    result = await planner_node(state)
    assert result["plan"] == ["Step 1: Write main.py", "Step 2: Run main.py"]
    assert result["entry_point"] == "main.py"
    assert result["current_step_index"] == 0
    assert result["retry_count"] == 0


def test_route_after_review() -> None:
    """
    Tests the routing decisions after code quality review.
    """
    # 1. No comments -> route to executor
    state_ok: AgentState = {
        "task": "",
        "plan": [],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "",
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "review_comments": "",
        "retry_count": 0,
        "max_retries": 5,
    }
    assert route_after_review(state_ok) == "executor"

    # 2. Comments present, retries left -> route back to coder
    state_err: AgentState = {
        "task": "",
        "plan": [],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "",
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "review_comments": "SyntaxError",
        "retry_count": 1,
        "max_retries": 5,
    }
    assert route_after_review(state_err) == "summarizer"

    # 3. Comments present, retries exhausted -> route to END
    state_exhausted: AgentState = {
        "task": "",
        "plan": [],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "",
        "stdout": "",
        "stderr": "",
        "exit_code": 0,
        "review_comments": "SyntaxError",
        "retry_count": 5,
        "max_retries": 5,
    }
    assert route_after_review(state_exhausted) == "__end__"


def test_route_after_execution() -> None:
    """
    Tests the routing decisions after sandboxed execution.
    """
    # 1. Failed execution, retries left -> route to coder
    state_fail: AgentState = {
        "task": "",
        "plan": ["Write code"],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "",
        "stdout": "",
        "stderr": "ZeroDivisionError",
        "exit_code": 1,
        "review_comments": "",
        "retry_count": 1,
        "max_retries": 5,
    }
    assert route_after_execution(state_fail) == "summarizer"

    # 2. Failed execution, retries exhausted -> route to END
    state_fail_exhausted: AgentState = {
        "task": "",
        "plan": ["Write code"],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "",
        "stdout": "",
        "stderr": "ZeroDivisionError",
        "exit_code": 1,
        "review_comments": "",
        "retry_count": 5,
        "max_retries": 5,
    }
    assert route_after_execution(state_fail_exhausted) == "__end__"

    # 3. Successful execution, steps remaining in plan -> route to coder
    state_next_step: AgentState = {
        "task": "",
        "plan": ["Step 1", "Step 2"],
        "current_step_index": 0,
        "code": "",
        "files": {},
        "entry_point": "",
        "stdout": "Done",
        "stderr": "",
        "exit_code": 0,
        "review_comments": "",
        "retry_count": 0,
        "max_retries": 5,
    }
    assert route_after_execution(state_next_step) == "coder"

    # 4. Successful execution, plan completed -> route to END
    state_success_end: AgentState = {
        "task": "",
        "plan": ["Step 1", "Step 2"],
        "current_step_index": 1,
        "code": "",
        "files": {},
        "entry_point": "",
        "stdout": "Done",
        "stderr": "",
        "exit_code": 0,
        "review_comments": "",
        "retry_count": 0,
        "max_retries": 5,
    }
    assert route_after_execution(state_success_end) == "__end__"

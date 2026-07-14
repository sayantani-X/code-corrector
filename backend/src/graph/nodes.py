import json
import subprocess
from typing import Any

from google.genai import types
from pydantic import BaseModel, Field

from src.core.config import settings
from src.core.llm import get_client
from src.domain.state import AgentState
from src.execution.local_docker import LocalDockerExecutor
from src.tools.file_tools import get_resolved_workspace_dir, list_files, read_file, write_file


# Define the structured output format for the Planner using Pydantic.
# The Google GenAI SDK converts this to a JSON schema for Gemini.
class Plan(BaseModel):
    steps: list[str] = Field(
        description="An ordered list of logical engineering steps to solve the user request."
    )
    entry_point: str = Field(
        description=(
            "The primary Python filename that contains the main code or test runner "
            "(e.g., 'main.py')."
        )
    )


async def planner_node(state: AgentState) -> dict[str, Any]:
    """
    Planner Node:
    Translates an ambiguous high-level user request into a concrete, ordered sequence
    of engineering steps, and establishes the entry point filename.
    """
    client = get_client()

    # Construct a helpful prompt for the Planner
    prompt = (
        f'Analyze this user request:\n\n"{state["task"]}"\n\n'
        "Design a step-by-step engineering plan to solve it. "
        "Provide the ordered steps and the primary entry point file."
    )

    # Call Gemini Flash (optimal for routing/planning tasks) with structured JSON output
    # We use the async caching-aware LLM function
    from src.core.llm import generate_content_with_retry_async

    response_text = await generate_content_with_retry_async(
        client=client,
        model=settings.gemini_flash_model,
        prompt=prompt,
        use_cache=True,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Plan,
            system_instruction=(
                "You are an expert software architect. Break down the user task into "
                "clear, logical steps. Specify the main python file to run "
                "(e.g. 'main.py' or 'solution.py')."
            ),
        ),
    )

    try:
        # Parse the structured JSON output from the model
        plan_data = json.loads(response_text)
        steps = plan_data.get("steps", ["Write code in main.py"])
        entry_point = plan_data.get("entry_point", "main.py")
    except Exception:
        # Fallback if parsing fails
        steps = [f"Implement the solution in {state.get('entry_point', 'main.py')}"]
        entry_point = "main.py"

    return {
        "plan": steps,
        "entry_point": entry_point,
        "current_step_index": 0,
        "retry_count": 0,
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "review_comments": "",
    }


async def coder_node(state: AgentState) -> dict[str, Any]:
    """
    Coder Node:
    Generates or patches code in the workspace based on the plan and current state.
    Uses Gemini 3.1 Pro via Vertex AI and binds file tools to perform edits.
    """
    client = get_client()

    # Determine which plan step we should run
    current_idx = state["current_step_index"]

    # If the previous node run was successful (exit_code == 0) and we produced stdout,
    # it means the current step was successfully implemented. We can advance to the next step.
    if state.get("exit_code") == 0 and state.get("stdout") and current_idx < len(state["plan"]) - 1:
        current_idx += 1

    current_step = state["plan"][current_idx]

    # Read the current files in the workspace to give the LLM context of what exists
    workspace_files = list_files()
    files_info = []
    for f in workspace_files:
        try:
            content = read_file(f)
            files_info.append(f"File: {f}\n```python\n{content}\n```")
        except Exception:
            pass

    files_context = "\n\n".join(files_info) if files_info else "No files in the workspace yet."

    # Build steps overview string
    steps_formatted = []
    for i, step in enumerate(state["plan"]):
        status = "x" if i < current_idx else " "
        steps_formatted.append(f"- [ {status} ] {step}")
    steps_str = "\n".join(steps_formatted)

    # Build a comprehensive prompt showing the current progress and errors to fix
    prompt = f"""Original User Task: {state["task"]}

Current Engineering Plan:
{steps_str}

We are currently working on step: "{current_step}"
The entry point file to run is set to: "{state["entry_point"]}"

Current Files in Workspace:
{files_context}
"""

    # Add error details if a previous execution failed
    if state.get("exit_code") != 0 and state.get("stderr"):
        error_info = state.get("stderr_summary") or state.get("stderr", "")
        prompt += (
            f"\n\n[WARNING] Previous execution failed with exit code {state['exit_code']}!\n"
            f"Traceback/Error logs:\n{error_info}\n"
            "Please debug and patch the code files to resolve this error."
        )

    # Add reviewer feedback if code quality checks failed
    if state.get("review_comments"):
        review_info = state.get("review_summary") or state.get("review_comments", "")
        prompt += (
            f"\n\n[WARNING] Previous run failed code quality review!\n"
            f"Reviewer Feedback:\n{review_info}\n"
            "Please modify the files to resolve these linting and security issues."
        )

    prompt += "\n\nPlease write, update, or read files to implement the current step."

    system_instruction = (
        "You are an expert autonomous software engineer agent.\n"
        "You must solve the user's request by writing, reading, and managing "
        "Python files inside the `./workspace` directory.\n"
        "You have access to the file system tools (write_file, read_file, list_files).\n"
        "Always write complete, correct, syntactically valid code. Avoid placeholder code.\n"
        "After using tools to save your files, output a concise explanation of what you did."
    )

    # Call Gemini with tools. The google-genai SDK handles tool call executions locally.
    # We use client.aio for async but skip caching here because tools perform I/O side effects
    coder_model = settings.gemini_model if state.get("use_heavy_model") else settings.gemini_flash_model
    
    # We use client.aio.chats to utilize automatic_function_calling
    chat = client.aio.chats.create(
        model=coder_model,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=[read_file, write_file, list_files],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=False,
                maximum_remote_calls=5
            ),
            temperature=0.1,
        )
    )
    
    await chat.send_message(prompt)

    # Synchronize the state's files and code after the tool calls complete
    updated_files = list_files()
    files_state = {}
    for filename in updated_files:
        try:
            files_state[filename] = read_file(filename)
        except Exception:
            pass

    # Save the main code content to the state for visualization/checkpointing
    main_code = files_state.get(state["entry_point"], "")

    return {
        "current_step_index": current_idx,
        "files": files_state,
        "code": main_code,
        # Clear errors now that code was updated/regenerated
        "exit_code": 0,
        "stdout": "",
        "stderr": "",
        "review_comments": "",
    }


def reviewer_node(state: AgentState) -> dict[str, Any]:
    """
    Reviewer Node:
    Runs static analysis (ruff for formatting/linting and bandit for security checks)
    on the files in the workspace on the host machine.
    """
    workspace_files = list_files()
    python_files = [f for f in workspace_files if f.endswith(".py")]

    # If no python files are found, there is nothing to review.
    if not python_files:
        return {"review_comments": "", "retry_count": state["retry_count"]}

    comments = []
    workspace_dir = get_resolved_workspace_dir()

    # Check each python file in the workspace
    for py_file in python_files:
        file_path = workspace_dir / py_file

        # 1. Run Ruff for style and syntax checks
        # We run it as a subprocess targeting the specific file.
        res_ruff = subprocess.run(["ruff", "check", str(file_path)], capture_output=True, text=True)
        if res_ruff.returncode != 0:
            comments.append(
                f"Ruff Linting issues in {py_file}:\n{res_ruff.stdout or res_ruff.stderr}"
            )

        # 2. Run Bandit for security vulnerability checks
        # -q runs quiet mode.
        res_bandit = subprocess.run(
            ["bandit", "-q", str(file_path)], capture_output=True, text=True
        )
        if res_bandit.returncode != 0:
            comments.append(
                f"Bandit Security issues in {py_file}:\n{res_bandit.stdout or res_bandit.stderr}"
            )

    review_comments = "\n\n".join(comments)
    new_retry_count = state["retry_count"]

    # If there are quality/security warnings, increment the retry count (consumes correction budget)
    if review_comments:
        new_retry_count += 1

    return {"review_comments": review_comments, "retry_count": new_retry_count}


def executor_node(state: AgentState) -> dict[str, Any]:
    """
    Executor Node:
    Runs the entry point script in the sandboxed LocalDockerExecutor environment.
    Captures and records stdout, stderr, and exit codes.
    """
    executor = LocalDockerExecutor()
    entry = state.get("entry_point", "main.py").strip()

    # Construct a runner script that safely invokes the entry point script via runpy.
    # It catches SystemExit to preserve the correct exit code inside the container.
    runner_code = f"""import runpy
import sys
try:
    runpy.run_path('/workspace/{entry}', run_name='__main__')
except SystemExit as e:
    sys.exit(e.code)
"""

    # Execute the runner code block in the isolated Docker container
    exit_code, stdout, stderr = executor.execute(runner_code)

    new_retry_count = state["retry_count"]
    if exit_code != 0:
        new_retry_count += 1

    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "retry_count": new_retry_count,
    }

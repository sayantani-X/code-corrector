import os
from pathlib import Path

from src.core.config import settings


def get_resolved_workspace_dir() -> Path:
    """
    Returns the absolute, resolved path of the workspace directory.
    This acts as the root boundary for our sandbox file operations.
    """
    return Path(settings.workspace_dir).resolve()


def _validate_path(filename: str) -> Path:
    """
    Helper function to validate that a file path remains strictly inside the workspace.
    This prevents path traversal attacks, such as trying to read "../../etc/passwd".

    Args:
        filename (str): The relative path of the file.

    Returns:
        Path: The absolute path of the file inside the workspace.

    Raises:
        ValueError: If the path escapes the workspace directory.
    """
    workspace_dir = get_resolved_workspace_dir()

    # Resolve the combined path to its absolute physical path, resolving any ".." or symlinks.
    target_path = Path(workspace_dir, filename).resolve()

    # Check if the target_path is relative to (or sub-path of) the workspace directory.
    # is_relative_to checks if target_path starts with workspace_dir.
    if not target_path.is_relative_to(workspace_dir):
        raise ValueError(
            f"Access Denied: Path '{filename}' attempts to escape the sandbox "
            f"directory '{workspace_dir}'."
        )

    return target_path


def write_file(filename: str, content: str) -> str:
    """
    Writes content to a file inside the workspace.
    If the file or its parent directories do not exist, they are created automatically.

    Args:
        filename (str): The path to the file relative to the workspace.
        content (str): The text content to write.

    Returns:
        str: A success message.
    """
    target_path = _validate_path(filename)

    # Ensure the user isn't trying to overwrite the workspace directory itself.
    if target_path == get_resolved_workspace_dir():
        raise ValueError("Cannot write content directly to the workspace directory path.")

    # Create any missing parent directories inside the workspace (e.g., if writing "src/main.py").
    target_path.parent.mkdir(parents=True, exist_ok=True)

    # Write the content to the file using UTF-8 encoding.
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(content)

    return f"Successfully wrote file: {filename}"


def read_file(filename: str) -> str:
    """
    Reads the content of a file inside the workspace.

    Args:
        filename (str): The path of the file relative to the workspace.

    Returns:
        str: The content of the file.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    target_path = _validate_path(filename)

    # Verify that the target is an actual file and exists.
    if not target_path.is_file():
        raise FileNotFoundError(f"File not found in workspace: {filename}")

    # Read and return the file content.
    with open(target_path, encoding="utf-8") as f:
        return f.read()


def list_files() -> list[str]:
    """
    Lists all files recursively inside the workspace directory.
    This helps the agent inspect the workspace structure.

    Returns:
        list[str]: A list of relative file paths (with Unix-style slashes).
    """
    workspace_dir = get_resolved_workspace_dir()

    # Ensure the workspace directory exists before listing.
    workspace_dir.mkdir(parents=True, exist_ok=True)

    files = []
    # Recursively traverse all directories and files.
    for root, _, filenames in os.walk(workspace_dir):
        for name in filenames:
            full_path = Path(root, name)
            # Convert to relative path from workspace root for cleaner representation.
            rel_path = full_path.relative_to(workspace_dir)
            # Use forward slashes for cross-platform consistency.
            files.append(str(rel_path).replace("\\", "/"))

    return files

import os
import tempfile
from pathlib import Path

import docker
import docker.errors

from src.core.config import settings

from .base import BaseExecutor


class LocalDockerExecutor(BaseExecutor):
    """
    Executes code in a local Docker container for local development.
    Maps a local workspace directory to /workspace in the container.
    """

    def __init__(
        self,
        image: str = "python:3.12-slim",
        workspace_dir: str | None = None,
        host_workspace_dir: str | None = None,
    ):
        self.client = docker.from_env()
        self.image = image

        # Use settings if not overridden
        self.workspace_dir = os.path.abspath(workspace_dir or settings.workspace_dir)
        self.host_workspace_dir = (
            host_workspace_dir or settings.docker_host_workspace_path or self.workspace_dir
        )

        # Ensure workspace exists locally
        os.makedirs(self.workspace_dir, exist_ok=True)

        # Pull image if not exists
        try:
            self.client.images.get(self.image)
        except docker.errors.ImageNotFound:
            self.client.images.pull(self.image)

    def execute(self, code: str) -> tuple[int, str, str]:
        with tempfile.NamedTemporaryFile(dir=self.workspace_dir, suffix=".py", delete=False) as f:
            f.write(code.encode("utf-8"))
            temp_path = Path(f.name)
            filename = temp_path.name

        try:
            container = self.client.containers.run(
                self.image,
                command=["python", f"/workspace/{filename}"],
                volumes={self.host_workspace_dir: {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                network_mode="none",
                detach=True,
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
            )

            try:
                # Wait with a 10-second timeout limit to prevent hanging/infinite loops.
                result = container.wait(timeout=10)
                exit_code = result["StatusCode"]
                stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
                stderr = container.logs(stdout=False, stderr=True).decode("utf-8")
            except Exception:
                # If a timeout occurs, stop/kill the container.
                try:
                    container.kill()
                except Exception:
                    pass
                exit_code = 124  # Standard CLI exit code for command timeouts
                stdout = ""
                stderr = "TimeoutError: Container execution exceeded the 10-second timeout limit."
            finally:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

            return exit_code, stdout, stderr
        finally:
            if temp_path.exists():
                temp_path.unlink()

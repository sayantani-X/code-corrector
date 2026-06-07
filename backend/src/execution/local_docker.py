import os
import tempfile
from pathlib import Path

import docker
import docker.errors

from .base import BaseExecutor


class LocalDockerExecutor(BaseExecutor):
    """
    Executes code in a local Docker container for local development.
    Maps a local workspace directory to /workspace in the container.
    """

    def __init__(self, image: str = "python:3.12-slim", workspace_dir: str = "./workspace"):
        self.client = docker.from_env()
        self.image = image
        # Resolve to absolute path, assume current working directory is the root
        self.workspace_dir = os.path.abspath(workspace_dir)

        # Ensure workspace exists
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
                volumes={self.workspace_dir: {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                network_mode="none",
                detach=True,
                security_opt=["no-new-privileges:true"],
                cap_drop=["ALL"],
            )

            result = container.wait()
            exit_code = result["StatusCode"]

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8")

            container.remove()

            return exit_code, stdout, stderr
        finally:
            if temp_path.exists():
                temp_path.unlink()

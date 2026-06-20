import docker
import pytest

from src.execution.local_docker import LocalDockerExecutor


def is_docker_available() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not is_docker_available(), reason="Docker daemon not available")
def test_local_docker_executor() -> None:
    executor = LocalDockerExecutor()

    # Test valid python code
    code = "print('Hello, Sandboxed World!')\nimport sys\nprint('Error log', file=sys.stderr)"
    exit_code, stdout, stderr = executor.execute(code)

    assert exit_code == 0
    assert "Hello, Sandboxed World!" in stdout
    assert "Error log" in stderr


@pytest.mark.skipif(not is_docker_available(), reason="Docker daemon not available")
def test_local_docker_executor_syntax_error() -> None:
    executor = LocalDockerExecutor()

    code = "print('Missing parenthesis'"
    exit_code, stdout, stderr = executor.execute(code)

    assert exit_code != 0
    assert "SyntaxError" in stderr


@pytest.mark.skipif(not is_docker_available(), reason="Docker daemon not available")
def test_local_docker_executor_timeout() -> None:
    executor = LocalDockerExecutor()

    # Sleep for 15 seconds, which exceeds the 10-second container timeout limit
    code = "import time\ntime.sleep(15)"
    exit_code, stdout, stderr = executor.execute(code)

    assert exit_code == 124
    assert "TimeoutError" in stderr

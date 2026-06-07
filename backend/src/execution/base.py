from abc import ABC, abstractmethod


class BaseExecutor(ABC):
    """
    Abstract base class for all code executors.
    """

    @abstractmethod
    def execute(self, code: str) -> tuple[int, str, str]:
        """
        Executes the provided python code.

        Args:
            code (str): The Python code to execute.

        Returns:
            tuple[int, str, str]: Exit code, stdout, and stderr.
        """
        pass

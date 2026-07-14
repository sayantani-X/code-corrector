import asyncio
import sys
import uuid

# Force selector event loop on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from src.core.db import close_db
from src.graph.graph import get_app


async def main():
    try:
        app = await get_app()
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}
        initial_state = {
            "task": "Direct test persistence",
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
            "max_retries": 1,
            "stderr_summary": "",
            "review_summary": "",
        }

        checkpointer = app.checkpointer
        assert checkpointer is not None, "Checkpointer is not configured"

        # Save
        await checkpointer.aput(config, None, "test_version_1", initial_state)

        # Retrieve
        retrieved_state_tuple = await checkpointer.aget_tuple(config)
        assert retrieved_state_tuple is not None, "Failed to retrieve"

        channel_values = retrieved_state_tuple.checkpoint["channel_values"]
        assert channel_values["task"] == "Direct test persistence", "Task mismatch"
        print("Integration test passed successfully!")

    finally:
        await close_db()

if __name__ == "__main__":
    asyncio.run(main())

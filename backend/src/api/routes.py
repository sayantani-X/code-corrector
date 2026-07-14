import json
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import APIRouter, Request
from langgraph.types import Command
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.graph.graph import get_app

router = APIRouter()

class TaskRequest(BaseModel):
    task: str
    bypass_planner: bool = False
    use_heavy_model: bool = False
    auto_approve_planner: bool = False
    auto_approve_executor: bool = False

# We use an in-memory dictionary to hold initial state or resume commands for threads
_pending_threads = {}

@router.post("/agent/task")
async def start_task(request: TaskRequest):
    """
    Initializes a new LangGraph thread with the user's task.
    Returns a thread_id that the frontend can use to subscribe to SSE.
    """
    thread_id = str(uuid.uuid4())

    # Store the initial payload to be picked up by the stream endpoint
    _pending_threads[thread_id] = {
        "type": "start",
        "data": {
            "task": request.task,
            "bypass_planner": request.bypass_planner,
            "use_heavy_model": request.use_heavy_model,
            "auto_approve_planner": request.auto_approve_planner,
            "auto_approve_executor": request.auto_approve_executor,
            "plan": [request.task] if request.bypass_planner else [],
            "current_step_index": 0,
            "code": "",
            "files": {},
            "entry_point": "main.py",
            "stdout": "",
            "stderr": "",
            "exit_code": 0,
            "review_comments": "",
            "retry_count": 0,
            "max_retries": 5
        }
    }

    return {"thread_id": thread_id, "status": "initialized"}

@router.post("/agent/resume/{thread_id}")
async def resume_task(thread_id: str, payload: dict):
    """
    Resumes a paused graph execution after an interrupt.
    The frontend calls this, then reconnects to the stream endpoint.
    """
    # payload can contain user feedback or just a resume signal
    _pending_threads[thread_id] = {
        "type": "resume",
        "data": payload
    }
    return {"thread_id": thread_id, "status": "resuming"}

@router.get("/agent/stream/{thread_id}")
async def stream_agent(thread_id: str, request: Request):
    """
    Connects to the graph execution for a specific thread_id and streams events via SSE.
    """
    app = await get_app()
    config = {"configurable": {"thread_id": thread_id}}

    async def event_generator() -> AsyncGenerator[dict[str, Any], None]:
        try:
            input_val = None

            # Check if there is a pending action for this thread
            if thread_id in _pending_threads:
                action = _pending_threads.pop(thread_id)
                if action["type"] == "start":
                    input_val = action["data"]
                elif action["type"] == "resume":
                    # In LangGraph, to resume after interrupt, you pass Command(resume=value)
                    input_val = Command(resume=action["data"])

            # Run the graph and stream updates
            async for event in app.astream(input_val, config=config, stream_mode="updates"):
                if await request.is_disconnected():
                    break

                if "__interrupt__" in event:
                    # In LangGraph, event["__interrupt__"] contains Interrupt objects which are not JSON serializable.
                    interrupt_val = event["__interrupt__"][0].value if event["__interrupt__"] and hasattr(event["__interrupt__"][0], "value") else str(event["__interrupt__"])
                    yield {
                        "event": "interrupt",
                        "data": json.dumps({"interrupt": interrupt_val})
                    }
                    continue

                for node, update in event.items():
                    yield {
                        "event": "node_update",
                        "data": json.dumps({
                            "node": node,
                            "update": update
                        })
                    }

            # After astream finishes, check if the graph is paused on an interrupt
            state = await app.aget_state(config)
            if state.tasks and any(task.interrupts for task in state.tasks):
                interrupts = [i.value for t in state.tasks for i in t.interrupts]
                yield {
                    "event": "interrupt",
                    "data": json.dumps({"interrupt": interrupts[0] if interrupts else "Action Required"})
                }
            elif not state.next:
                yield {
                    "event": "node_update",
                    "data": json.dumps({"node": "system", "update": "Workflow finished."})
                }

        except Exception as e:
            yield {
                "event": "agent_error",
                "data": json.dumps({"detail": str(e)})
            }

    return EventSourceResponse(event_generator())

import os
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI

from config.settings import settings


_checkpointer: Any = None


def _should_use_memory() -> bool:
    if getattr(settings, "use_memory_checkpointer", False):
        return True
    if os.getenv("USE_MEMORY_CHECKPOINTER", "").lower() in {"1", "true", "yes"}:
        return True
    if settings.db_uri.startswith("memory://"):
        return True
    return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _checkpointer

    if _should_use_memory():
        from langgraph.checkpoint.memory import InMemorySaver

        _checkpointer = InMemorySaver()
        try:
            yield
        finally:
            _checkpointer = None
        return

    from langgraph.checkpoint.postgres import PostgresSaver

    conn_string = settings.db_uri

    try:
        async with PostgresSaver.from_conn_string(conn_string) as checkpointer:
            _checkpointer = checkpointer
            await _checkpointer.setup()

            from api.feedback import create_feedback_table
            try:
                await create_feedback_table()
            except Exception as e:
                print(f"Warning: Could not initialize feedback table: {e}")

            yield
    except Exception as e:
        print(f"CRITICAL: Database connection failed: {e}")
        raise


def get_checkpointer():
    if _checkpointer is None:
        raise RuntimeError(
            "Checkpointer not initialized. Make sure lifespan is running and DB / "
            "USE_MEMORY_CHECKPOINTER is configured."
        )
    return _checkpointer


CheckpointerDep = Annotated[Any, Depends(get_checkpointer)]

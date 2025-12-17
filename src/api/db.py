import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi import Depends
from typing import Annotated

from langgraph.checkpoint.postgres import PostgresSaver
from config.settings import settings

# Global checkpointer instance
_checkpointer: PostgresSaver | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _checkpointer
    # Use settings.db_uri which comes from env or default
    conn_string = settings.db_uri
    
    # If using a real postgres is not possible in this environment without docker, 
    # we might need to handle connection errors gracefully or mock it for 'dev' run if intended for just checking logic.
    # But for now, we assume the user has postgres or will set it up.
    
    try:
        # Note: PostgresSaver requires a valid connection string.
        # If the server is not up, this will fail.
        # For 'langgraph dev' verification without a real DB, we might want to check if we can use InMemory for dev?
        # But the request is to verify it works.
        
        async with PostgresSaver.from_conn_string(conn_string) as checkpointer:
            _checkpointer = checkpointer
            await _checkpointer.setup()

            # Initialize feedback table
            from api.feedback import create_feedback_table
            try:
                await create_feedback_table()
            except Exception as e:
                print(f"Warning: Could not initialize feedback table: {e}")

            yield
            
    except Exception as e:
        print(f"CRITICAL: Database connection failed: {e}")
        # For development/demo purposes without a DB, we might want to allow startup but fail on chat?
        # Or better, just fail loudly so the user knows they need the DB.
        raise e

def get_checkpointer() -> PostgresSaver:
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized. Make sure lifespan is running and DB is accessible.")
    return _checkpointer

CheckpointerDep = Annotated[PostgresSaver, Depends(get_checkpointer)]

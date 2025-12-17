from datetime import timedelta

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from fever_routing.agent import make_graph
from api.auth import (
    authenticate_admin,
    create_access_token,
    verify_api_key,
    LoginRequest,
    TokenResponse
)
from api.db import CheckpointerDep, lifespan
from api.feedback import (
    FeedbackSubmission,
    FeedbackResponse,
    FeedbackStatsResponse,
    FeedbackListResponse,
    create_feedback_table,
    insert_feedback,
    get_all_feedback,
    get_feedback_stats
)
from config.settings import settings

app = FastAPI(
    title="Fever Routing API",
    description="Medical triage chatbot with secure API access",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica tu dominio de Angular
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    """Root endpoint - basic info"""
    return {
        "name": "Fever Routing API - miauuuu",
        "version": "1.0.0",
        "status": "running",
        "environment": settings.environment
    }


@app.get("/health")
def health_check():
    """Health check endpoint - no authentication required"""
    return {"status": "healthy as possible"}


@app.post("/api/admin/login", response_model=TokenResponse)
async def admin_login(credentials: LoginRequest):
    """
    Admin login endpoint.
    Returns a JWT token valid for 7 days and the API key for chat access.
    """
    if not authenticate_admin(credentials.username, credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    access_token = create_access_token(
        data={"sub": credentials.username, "type": "admin"}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_days * 24 * 60 * 60,  # Convert to seconds
        api_key=settings.api_key.get_secret_value()
    )


class Message(BaseModel):
    message: str


@app.post("/chat/{chat_id}", dependencies=[Depends(verify_api_key)])
async def chat(chat_id: str, item: Message, checkpointer: CheckpointerDep):
    """
    Chat endpoint - requires API key authentication.
    Process a single message and return the response.
    """
    config = {
        "configurable": {
            "thread_id": chat_id
        }
    }
    human_message = HumanMessage(content=item.message)
    agent = make_graph(config={"checkpoint": checkpointer})
    response = await agent.ainvoke({"messages": [human_message]}, config=config)
    last_message = response["messages"][-1]
    return {"response": last_message.content}


@app.post("/chat/{chat_id}/stream", dependencies=[Depends(verify_api_key)])
async def stream(chat_id: str, message: Message, checkpointer: CheckpointerDep):
    """
    Streaming chat endpoint - requires API key authentication.
    Stream responses as they are generated.
    """
    config = {
        "configurable": {
            "thread_id": chat_id
        }
    }
    agent = make_graph(config={"checkpoint": checkpointer})
    human_message = HumanMessage(content=message.message)

    async def generate_response():
        async for message_chunk, metadata in agent.astream(
            {"messages": [human_message]},
            stream_mode="messages",
            config=config
        ):
            if message_chunk.content:
                yield f"data: {message_chunk.content}\n\n"

    return StreamingResponse(generate_response(), media_type="text/event-stream")


@app.post("/submit-feedback", response_model=FeedbackResponse, dependencies=[Depends(verify_api_key)])
async def submit_feedback(feedback: FeedbackSubmission):
    """
    Submit user feedback - requires API key authentication.
    Stores feedback in PostgreSQL database.
    """
    try:
        feedback_id = insert_feedback(feedback)
        return FeedbackResponse(
            success=True,
            message=f"Feedback submitted successfully",
            feedback_id=feedback_id
        )
    except Exception as e:
        print(f"Error submitting feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to submit feedback: {str(e)}"
        )


@app.get("/feedback", response_model=FeedbackListResponse, dependencies=[Depends(verify_api_key)])
async def get_feedback():
    """
    Get all feedback records - requires API key authentication.
    Returns all feedback ordered by timestamp (newest first).
    """
    try:
        feedback_list = get_all_feedback()
        return FeedbackListResponse(
            success=True,
            total=len(feedback_list),
            feedback=feedback_list
        )
    except Exception as e:
        print(f"Error retrieving feedback: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve feedback: {str(e)}"
        )


@app.get("/feedback/stats", response_model=FeedbackStatsResponse, dependencies=[Depends(verify_api_key)])
async def get_stats():
    """
    Get feedback statistics - requires API key authentication.
    Returns aggregated statistics for all feedback fields.
    """
    try:
        stats = get_feedback_stats()
        return FeedbackStatsResponse(
            success=True,
            stats=stats
        )
    except Exception as e:
        print(f"Error calculating feedback stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate feedback statistics: {str(e)}"
        )

"""
main.py
-------
FastAPI server. Exposes GET /health and POST /chat as required by the assignment spec.
Run with: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator

from agent import chat

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── App setup ─────────────────────────────────────────────────────────────────
app = FastAPI(
    title="SHL Assessment Recommender",
    description="Conversational agent for SHL assessment selection",
    version="1.0.0"
)

# Allow all origins (fine for an assignment — tighten in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Request / Response models ─────────────────────────────────────────────────
class Message(BaseModel):
    role: str        # "user" or "assistant"
    content: str

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: str) -> str:
        if v not in ("user", "assistant"):
            raise ValueError("role must be 'user' or 'assistant'")
        return v

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty")
        return v


class ChatRequest(BaseModel):
    messages: list[Message]

    @field_validator("messages")
    @classmethod
    def messages_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("messages list must not be empty")
        # Assignment spec caps at 8 turns total
        if len(v) > 8:
            raise ValueError("Conversation exceeds the 8-turn limit")
        return v


class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str


class ChatResponse(BaseModel):
    reply: str
    recommendations: list[Recommendation]
    end_of_conversation: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
def health_check():
    """
    Readiness endpoint.
    Returns HTTP 200 with {"status": "ok"} when the service is up.
    """
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint.
    Receives full conversation history, returns agent reply + recommendations.
    The service is stateless — caller must send all previous messages every time.
    """
    # Convert Pydantic models to plain dicts for the agent
    messages = [{"role": m.role, "content": m.content} for m in request.messages]

    try:
        result = chat(messages)
    except Exception as e:
        # Never let an unhandled exception reach the client
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")

    # Ensure the response always matches the required schema
    return ChatResponse(
        reply=result.get("reply", "Sorry, I could not generate a response."),
        recommendations=[
            Recommendation(**r) for r in result.get("recommendations", [])
        ],
        end_of_conversation=result.get("end_of_conversation", False)
    )


# ── Dev server entry point ────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
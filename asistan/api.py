import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from asistan.agent import Agent, AgentReply
from asistan.config import settings
from asistan.llm import ChatModel, OpenAICompatibleModel
from asistan.stok_client import make_stok_client

app = FastAPI(title="Stok Asistanı", description="Natural-language assistant for the Stok API.", version="1.0.0")

# One agent per conversation, kept in memory. Fine for a single-shop demo; a real deployment would persist this.
_sessions: dict[str, Agent] = {}


def make_agent() -> Agent:
    model: ChatModel = OpenAICompatibleModel(settings.llm_base_url, settings.llm_api_key, settings.llm_model)
    return Agent(model, make_stok_client(settings), settings.max_steps)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None


class DecisionIn(BaseModel):
    approve: bool


class ChatOut(BaseModel):
    session_id: str
    reply: str | None
    pending_action: str | None
    tools_used: list[str]


def _out(session_id: str, reply: AgentReply) -> ChatOut:
    return ChatOut(
        session_id=session_id,
        reply=reply.text,
        pending_action=reply.pending.describe() if reply.pending else None,
        tools_used=reply.tool_log,
    )


@app.post("/chat", response_model=ChatOut)
def chat(data: ChatIn):
    session_id = data.session_id or uuid.uuid4().hex
    agent = _sessions.get(session_id)
    if agent is None:
        agent = _sessions[session_id] = make_agent()
    return _out(session_id, agent.ask(data.message))


@app.post("/chat/{session_id}/decision", response_model=ChatOut)
def decide(session_id: str, data: DecisionIn):
    agent = _sessions.get(session_id)
    if agent is None:
        raise HTTPException(404, "Session not found")
    return _out(session_id, agent.resolve(data.approve))

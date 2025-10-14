"""FastAPI service exposing chat endpoint for the Pokémon chatbot."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple, Union

from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

try:  # pragma: no cover - optional dependency
    from transformers import (  # type: ignore
        AutoModelForCausalLM,
        AutoTokenizer,
        TextIteratorStreamer,
    )
except ImportError:  # pragma: no cover - optional dependency
    AutoModelForCausalLM = None  # type: ignore
    AutoTokenizer = None  # type: ignore
    TextIteratorStreamer = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class MemoryMessage:
    """Represents a single message in the conversation history."""

    role: str
    content: str
    citations: List[str] = field(default_factory=list)


@dataclass
class ToolResult:
    """Value returned by retrieval tools."""

    content: str
    citations: List[str] = field(default_factory=list)


ToolFunction = Callable[[str, Sequence[MemoryMessage], str], Optional[ToolResult]]


class LLMBackend(Protocol):
    """Protocol describing the interface expected from language models."""

    def generate(self, prompt: str, *, stream: bool = False) -> Union[str, Iterable[str]]:
        """Generate a response for the provided prompt."""


class EchoBackend:
    """Fallback backend used when a transformers model is unavailable."""

    def generate(self, prompt: str, *, stream: bool = False) -> Union[str, Iterable[str]]:
        reply = "I am unable to answer that right now."
        return reply


class TransformersBackend:
    """Hugging Face Transformers backend for causal language models."""

    def __init__(
        self,
        model_name: str = "google/gemma-2-9b-it",
        *,
        device: str = "cpu",
        max_new_tokens: int = 512,
        dtype: Optional[str] = None,
        **model_kwargs,
    ) -> None:
        if AutoModelForCausalLM is None or AutoTokenizer is None:
            raise RuntimeError(
                "transformers must be installed to use TransformersBackend"
            )

        tokenizer_kwargs = {"padding_side": "left", "truncation_side": "left"}
        tokenizer_kwargs.update(model_kwargs.pop("tokenizer_kwargs", {}))

        self.tokenizer = AutoTokenizer.from_pretrained(model_name, **tokenizer_kwargs)
        self.model = AutoModelForCausalLM.from_pretrained(model_name, **model_kwargs)
        if dtype:
            try:
                import torch

                self.model = self.model.to(dtype=getattr(torch, dtype))
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Unable to set dtype %s: %s", dtype, exc)
        self.model = self.model.to(device)
        self.device = device
        self.max_new_tokens = max_new_tokens

    def generate(self, prompt: str, *, stream: bool = False) -> Union[str, Iterable[str]]:
        import torch

        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        generation_kwargs = {
            "max_new_tokens": self.max_new_tokens,
            "pad_token_id": self.tokenizer.eos_token_id,
        }
        generation_kwargs.update(inputs)

        if stream:
            if TextIteratorStreamer is None:
                raise RuntimeError("Streaming requires transformers>=4.28 with TextIteratorStreamer")
            streamer = TextIteratorStreamer(
                self.tokenizer, skip_special_tokens=True, skip_prompt=True
            )
            thread = threading.Thread(target=self.model.generate, kwargs={"streamer": streamer, **generation_kwargs})
            thread.start()
            return self._stream_tokens(streamer, thread)

        with torch.no_grad():
            output = self.model.generate(**generation_kwargs)
        text = self.tokenizer.decode(output[0], skip_special_tokens=True)
        return text

    @staticmethod
    def _stream_tokens(streamer: Iterable[str], thread: threading.Thread) -> Iterable[str]:
        for token in streamer:
            yield token
        thread.join()


class ConversationMemory:
    """Thread-safe in-memory store for conversation history."""

    def __init__(self, max_messages: int = 40) -> None:
        self.max_messages = max_messages
        self._messages: Dict[str, List[MemoryMessage]] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> List[MemoryMessage]:
        with self._lock:
            return list(self._messages.get(session_id, ()))

    def append(self, session_id: str, message: MemoryMessage) -> None:
        with self._lock:
            history = self._messages.setdefault(session_id, [])
            history.append(message)
            excess = len(history) - self.max_messages
            if excess > 0:
                del history[:excess]

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._messages.pop(session_id, None)


class ConversationManager:
    """Coordinates retrieval, memory and the LLM to produce replies."""

    def __init__(
        self,
        *,
        llm_backend: LLMBackend,
        memory: Optional[ConversationMemory] = None,
    ) -> None:
        self.llm_backend = llm_backend
        self.memory = memory or ConversationMemory()
        self._tools: Dict[str, ToolFunction] = {}

    def register_tool(self, name: str, tool: ToolFunction) -> None:
        self._tools[name] = tool

    def generate_reply(self, session_id: str, message: str) -> Tuple[str, List[str]]:
        if not message.strip():
            raise ValueError("message must not be empty")

        history = self.memory.get(session_id)
        tool_contexts: List[str] = []
        citations: List[str] = []
        for name, tool in self._tools.items():
            try:
                result = tool(session_id, history, message)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Tool '%s' failed: %s", name, exc)
                continue
            if result:
                tool_contexts.append(result.content)
                for citation in result.citations:
                    if citation not in citations:
                        citations.append(citation)

        prompt = self._build_prompt(history, message, tool_contexts)
        response = self.llm_backend.generate(prompt, stream=False)
        if isinstance(response, str):
            reply_text = response
        else:
            reply_text = "".join(response)

        formatted_reply = reply_text
        if citations:
            formatted_reply = f"{reply_text}\n\nSources: {', '.join(citations)}"

        self.memory.append(session_id, MemoryMessage(role="user", content=message))
        self.memory.append(
            session_id,
            MemoryMessage(role="assistant", content=reply_text, citations=citations.copy()),
        )
        return formatted_reply, citations

    @staticmethod
    def _build_prompt(
        history: Sequence[MemoryMessage], message: str, tool_contexts: Sequence[str]
    ) -> str:
        sections: List[str] = []
        for item in history:
            sections.append(f"{item.role.capitalize()}: {item.content}")
        if tool_contexts:
            sections.append("Relevant context:\n" + "\n".join(tool_contexts))
        sections.append(f"User: {message}\nAssistant:")
        return "\n".join(sections)


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Identifier for the conversation session")
    message: str = Field(..., description="User message to send to the assistant")


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    citations: List[str] = Field(default_factory=list)


app = FastAPI(title="Pokémon Games Chatbot Service")


def _build_default_manager() -> ConversationManager:
    backend: LLMBackend
    if AutoModelForCausalLM is not None and AutoTokenizer is not None:
        try:
            backend = TransformersBackend()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Falling back to echo backend: %s", exc)
            backend = EchoBackend()
    else:
        backend = EchoBackend()
    return ConversationManager(llm_backend=backend)


def get_conversation_manager() -> ConversationManager:
    manager = getattr(app.state, "conversation_manager", None)
    if manager is None:
        manager = _build_default_manager()
        app.state.conversation_manager = manager
    return manager


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="message must not be empty")

    manager = get_conversation_manager()
    reply, citations = await run_in_threadpool(
        manager.generate_reply, request.session_id, request.message
    )
    return ChatResponse(session_id=request.session_id, reply=reply, citations=citations)


__all__ = [
    "app",
    "ChatRequest",
    "ChatResponse",
    "ConversationManager",
    "ConversationMemory",
    "MemoryMessage",
    "EchoBackend",
    "LLMBackend",
    "ToolResult",
    "TransformersBackend",
    "get_conversation_manager",
]

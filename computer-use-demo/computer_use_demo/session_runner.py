from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Any

from anthropic.types.beta import BetaContentBlockParam, BetaMessageParam

from .event_broker import EventBroker
from .loop import APIProvider, sampling_loop
from .session_manager import SessionManager
from .tools import ToolResult, ToolVersion


@dataclass(frozen=True)
class RunConfig:
    """Runtime parameters for a session run."""

    model: str
    provider: str
    system_prompt_suffix: str
    max_tokens: int
    tool_version: ToolVersion
    thinking_budget: int | None
    token_efficient_tools_beta: bool
    only_n_most_recent_images: int | None


class SessionRunner:
    """Executes the agent loop for a session and streams progress events."""

    def __init__(self, session_manager: SessionManager, event_broker: EventBroker) -> None:
        self._session_manager = session_manager
        self._event_broker = event_broker
        self._lock = asyncio.Lock()
        self._tasks: dict[str, asyncio.Task[None]] = {}

    async def start(self, session_id: str, config: RunConfig) -> bool:
        """Start a session run if one is not already active."""
        async with self._lock:
            existing = self._tasks.get(session_id)
            if existing and not existing.done():
                return False
            task = asyncio.create_task(self._run_session(session_id, config))
            self._tasks[session_id] = task
        return True

    async def _run_session(self, session_id: str, config: RunConfig) -> None:
        """Run the agent loop and emit stream events for outputs and tool results."""
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        provider = APIProvider(config.provider)

        messages = self._build_messages(session_id)
        loop = asyncio.get_running_loop()

        def publish_event(payload: dict[str, Any]) -> None:
            loop.create_task(
                self._event_broker.publish(session_id, json.dumps(payload))
            )

        def output_callback(content_block: BetaContentBlockParam) -> None:
            if isinstance(content_block, dict) and content_block.get("type") == "text":
                text = content_block.get("text", "")
                if text:
                    self._session_manager.add_message(session_id, "assistant", text)
                publish_event({"type": "assistant_text", "text": text})
                return
            publish_event({"type": "assistant_block", "block": content_block})

        def tool_output_callback(result: ToolResult, tool_use_id: str) -> None:
            text = result.output or result.error or ""
            if text:
                self._session_manager.add_message(session_id, "tool", text)
            publish_event(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "output": result.output,
                    "error": result.error,
                }
            )

        def api_response_callback(request, response, error) -> None:
            if error is not None:
                publish_event({"type": "api_error", "error": str(error)})
            else:
                publish_event({"type": "api_response", "status": "ok"})

        try:
            await sampling_loop(
                model=config.model,
                provider=provider,
                system_prompt_suffix=config.system_prompt_suffix,
                messages=messages,
                output_callback=output_callback,
                tool_output_callback=tool_output_callback,
                api_response_callback=api_response_callback,
                api_key=api_key,
                only_n_most_recent_images=config.only_n_most_recent_images,
                max_tokens=config.max_tokens,
                tool_version=config.tool_version,
                thinking_budget=config.thinking_budget,
                token_efficient_tools_beta=config.token_efficient_tools_beta,
            )
        except Exception as exc:  # noqa: BLE001
            publish_event({"type": "run_error", "error": str(exc)})

    def _build_messages(self, session_id: str) -> list[BetaMessageParam]:
        """Build Claude message history from stored chat records."""
        history = self._session_manager.list_messages(session_id)
        messages: list[BetaMessageParam] = []
        for item in history:
            role = item["role"]
            if role not in ("user", "assistant"):
                continue
            messages.append(
                {
                    "role": role,
                    "content": [{"type": "text", "text": item["content"]}],
                }
            )
        return messages

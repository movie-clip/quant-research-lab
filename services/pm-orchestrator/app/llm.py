from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .agents import AGENT_REGISTRY
from .config import settings


class LLMClient(Protocol):
    def generate(self, agent_key: str, input_text: str, memory_summary: str) -> tuple[str, dict[str, Any]]: ...


class DelegatedChildTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    title: str
    input: str


class DelegateAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern="^delegate$")
    summary: str
    children: list[DelegatedChildTask]


class FinalAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern="^final$")
    message: str


class AskUserAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str = Field(pattern="^ask_user$")
    summary: str
    question: str


def validate_agent_output(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    if action == "delegate":
        model = DelegateAction.model_validate(payload)
        if not model.children:
            raise ValueError("delegate action must include at least one child task")
        return model.model_dump()
    if action == "final":
        return FinalAction.model_validate(payload).model_dump()
    if action == "ask_user":
        return AskUserAction.model_validate(payload).model_dump()
    raise ValueError(f"Unsupported action: {action!r}")


def build_llm_client() -> LLMClient:
    if settings.llm_provider == "openai" and settings.llm_api_key:
        return OpenAIResponsesClient(
            api_key=settings.llm_api_key,
            api_base=settings.llm_api_base,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return FakeLLMClient()


def _serialize_validated_payload(payload: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    validated = validate_agent_output(payload)
    return json.dumps(validated, indent=2), validated


class FakeLLMClient:
    def generate(self, agent_key: str, input_text: str, memory_summary: str) -> tuple[str, dict[str, Any]]:
        lower = input_text.lower()
        if agent_key == "pm":
            payload = self._pm_response(input_text, lower)
        elif agent_key == "producer":
            payload = self._producer_response(input_text, lower)
        elif agent_key == "quant_scientist":
            payload = self._scientist_response(input_text)
        elif agent_key == "quant_platform_engineer":
            payload = self._platform_response(input_text)
        elif agent_key == "desktop_engineer":
            payload = self._desktop_response(input_text)
        elif agent_key == "ux_engineer":
            payload = self._ux_response(input_text)
        else:
            payload = {"action": "final", "message": f"No fake adapter behavior defined for {agent_key}."}
        return _serialize_validated_payload(payload)

    def _pm_response(self, input_text: str, lower: str) -> dict[str, Any]:
        if input_text.startswith("SYNTHESIZE\n"):
            return {
                "action": "final",
                "message": "PM synthesis complete. The delegated specialist chain finished and returned a merged plan.\n\n" + input_text,
            }
        if "user_response\n" in lower:
            return {
                "action": "final",
                "message": "PM resumed after user input and can continue with the run.\n\n" + input_text,
            }
        if "need key" in lower or "secret" in lower:
            return {
                "action": "ask_user",
                "summary": "PM is blocked on a missing secret.",
                "question": "Please provide the required secret or API key so the run can continue.",
            }
        return {
            "action": "delegate",
            "summary": "PM routes the request to Producer first.",
            "children": [
                {
                    "agent": "producer",
                    "title": "Producer routing",
                    "input": input_text,
                }
            ],
        }

    def _producer_response(self, input_text: str, lower: str) -> dict[str, Any]:
        if input_text.startswith("SYNTHESIZE\n"):
            return {
                "action": "final",
                "message": "Producer merged the specialist outputs into one execution direction.\n\n" + input_text,
            }
        if "ranking" in lower or "backend" in lower or "portfolio" in lower:
            return {
                "action": "delegate",
                "summary": "Producer wants scientist, platform, desktop, and UX inputs.",
                "children": [
                    {
                        "agent": "quant_scientist",
                        "title": "Lock methodology semantics",
                        "input": "Produce a narrow scientist spec for the request: " + input_text,
                    },
                    {
                        "agent": "quant_platform_engineer",
                        "title": "Backend contract and engine plan",
                        "input": "Produce a backend implementation brief for the request: " + input_text,
                    },
                    {
                        "agent": "desktop_engineer",
                        "title": "Desktop integration plan",
                        "input": "Produce a desktop integration brief for the request: " + input_text,
                    },
                    {
                        "agent": "ux_engineer",
                        "title": "UX review brief",
                        "input": "Produce a UX brief for the request: " + input_text,
                    },
                ],
            }
        return {
            "action": "final",
            "message": "Producer does not need specialist delegation for this request. It can be answered directly.",
        }

    def _scientist_response(self, input_text: str) -> dict[str, Any]:
        return {
            "action": "final",
            "message": "Scientist output: locked methodology semantics, exclusion rules, tie-breaks, and factor definitions for the active request.\n\nSource input:\n" + input_text,
        }

    def _platform_response(self, input_text: str) -> dict[str, Any]:
        return {
            "action": "final",
            "message": "Platform output: backend contract, deterministic service placement, route wiring, and test matrix.\n\nSource input:\n" + input_text,
        }

    def _desktop_response(self, input_text: str) -> dict[str, Any]:
        return {
            "action": "final",
            "message": "Desktop output: app-state wiring, artifact persistence, replay handoff boundaries, and test coverage.\n\nSource input:\n" + input_text,
        }

    def _ux_response(self, input_text: str) -> dict[str, Any]:
        return {
            "action": "final",
            "message": "UX output: ranked review layout, copy guardrails, and explicit user-choice step before replay.\n\nSource input:\n" + input_text,
        }


@dataclass
class OpenAIResponsesClient:
    api_key: str
    api_base: str
    model: str
    timeout_seconds: float

    def generate(self, agent_key: str, input_text: str, memory_summary: str) -> tuple[str, dict[str, Any]]:
        agent = AGENT_REGISTRY[agent_key]
        system_prompt = self._build_system_prompt(agent.system_prompt, memory_summary)
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(
                f"{self.api_base.rstrip('/')}/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": input_text},
                    ],
                    "text": {"format": {"type": "json_object"}},
                },
            )
            response.raise_for_status()
            payload = response.json()
        output_text = self._extract_text(payload)
        structured = json.loads(output_text)
        return _serialize_validated_payload(structured)

    def _build_system_prompt(self, system_prompt: str, memory_summary: str) -> str:
        memory_block = memory_summary.strip() or "No prior memory summary."
        return (
            f"{system_prompt}\n\n"
            "You must return valid JSON only.\n"
            "Allowed actions: delegate, final, ask_user.\n"
            "For delegate, return children as objects with agent, title, and input.\n"
            "For ask_user, include a question.\n"
            "For final, include a message.\n\n"
            f"Session memory summary:\n{memory_block}"
        )

    def _extract_text(self, payload: dict[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str):
            return payload["output_text"]
        outputs = payload.get("output") or []
        chunks: list[str] = []
        for item in outputs:
            for content in item.get("content", []):
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text)
        if chunks:
            return "\n".join(chunks)
        raise ValueError("Provider response did not contain output text")

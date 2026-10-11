"""Thin LLM layer: LM Studio via its OpenAI-compatible API, plus a scripted mock.

Both classes expose the same two methods and record every call in `self.calls`
(kind, node, latency, tokens, error) so runs can be inspected afterwards.
"""
from __future__ import annotations

import json
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from openai import OpenAI
from pydantic import BaseModel

import prompts
from config import PLACEHOLDER_MODEL, Settings

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def strip_think(text: str) -> str:
    return THINK_RE.sub("", text).strip()


def extract_json(text: str) -> str:
    text = strip_think(text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    return text[start:end + 1]


class LMStudioLLM:
    def __init__(self, settings: Settings):
        if not settings.model or settings.model == PLACEHOLDER_MODEL:
            raise SystemExit(
                "LM_STUDIO_MODEL is not set. Put the model id shown by LM Studio "
                f"(or `curl {settings.base_url}/models`) into the repo's .env."
            )
        self.settings = settings
        self.chat = ChatOpenAI(
            model=settings.model,
            base_url=settings.base_url,
            api_key=settings.api_key,
            temperature=settings.temperature,
            timeout=settings.timeout,
            max_retries=1,
        )
        self.calls: list[dict] = []

    def check_connection(self) -> None:
        try:
            ids = [m.id for m in OpenAI(base_url=self.settings.base_url, api_key=self.settings.api_key,
                                        timeout=5).models.list().data]
        except Exception as e:  # noqa: BLE001 - want a friendly message for any failure
            raise SystemExit(f"Cannot reach LM Studio at {self.settings.base_url}: {e}\n"
                             "Start LM Studio's local server (Developer tab) and load a model.")
        if self.settings.model not in ids:
            print(f"warning: model {self.settings.model!r} not in LM Studio's model list {ids}")

    def structured(self, schema: type[BaseModel], system: str, user: str, *, node: dict, kind: str) -> BaseModel:
        """One structured call. Raises on transport or parse failure (caller decides fallback)."""
        t0 = time.perf_counter()
        record = {"kind": kind, "node": node["id"], "method": self.settings.structured_method}
        try:
            if self.settings.structured_method == "json_schema":
                runnable = self.chat.with_structured_output(schema, method="json_schema", include_raw=True)
                out = runnable.invoke([SystemMessage(system), HumanMessage(user)])
                raw, parsed = out["raw"], out["parsed"]
                if parsed is None:
                    raise ValueError(f"parse failed: {out.get('parsing_error')}; raw={str(raw.content)[:300]!r}")
            else:
                schema_json = json.dumps(schema.model_json_schema())
                raw = self.chat.invoke([SystemMessage(system + prompts.JSON_INSTRUCTIONS.format(schema=schema_json)),
                                        HumanMessage(user)])
                parsed = schema.model_validate_json(extract_json(str(raw.content)))
            record.update(_usage(raw), ok=True)
            return parsed
        except Exception as e:
            record.update(ok=False, error=f"{type(e).__name__}: {e}"[:500])
            raise
        finally:
            record["seconds"] = round(time.perf_counter() - t0, 2)
            self.calls.append(record)

    def text(self, system: str, user: str, *, node: dict, kind: str) -> str:
        t0 = time.perf_counter()
        record = {"kind": kind, "node": node["id"]}
        try:
            msg = self.chat.invoke([SystemMessage(system), HumanMessage(user)])
            record.update(_usage(msg), ok=True)
            return strip_think(str(msg.content))
        except Exception as e:
            record.update(ok=False, error=f"{type(e).__name__}: {e}"[:500])
            raise
        finally:
            record["seconds"] = round(time.perf_counter() - t0, 2)
            self.calls.append(record)


def _usage(msg) -> dict:
    usage = getattr(msg, "usage_metadata", None) or {}
    return {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens")}


class MockLLM:
    """Deterministic fake for testing the plumbing without LM Studio. NOT a model."""

    def __init__(self):
        self.calls: list[dict] = []

    def check_connection(self) -> None:
        pass

    def structured(self, schema, system, user, *, node, kind):
        self.calls.append({"kind": kind, "node": node["id"], "ok": True, "seconds": 0.0})
        d, nid, obj = node["depth"], node["id"], node["objective"]
        if d == 0:
            return schema(reasoning="mock: root splits into dimensions", mode="WIDE",
                          children=[f"mock dimension {i} of: {obj}" for i in range(1, 6)])  # 5 > default cap
        if d == 1 and nid % 2 == 1:
            return schema(reasoning="mock: needs a dependency resolved", mode="DEEP",
                          children=[f"mock dependency of #{nid}", f"mock dependency of #{nid}"])  # duplicate
        if d == 2:
            return schema(reasoning="mock: wants to go deeper still", mode="WIDE",
                          children=[f"mock leaf A of #{nid}", f"mock leaf B of #{nid}"])
        return schema(reasoning="mock: narrow enough", mode="ATOM", children=[])

    def text(self, system, user, *, node, kind):
        self.calls.append({"kind": kind, "node": node["id"], "ok": True, "seconds": 0.0})
        return f"- mock {kind} for node #{node['id']}"

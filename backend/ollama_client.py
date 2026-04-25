from __future__ import annotations

import json
import os
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


OLLAMA_BASE = os.environ.get("MEMORYOS_OLLAMA_BASE", "http://localhost:11434")
MODEL = os.environ.get("MEMORYOS_OLLAMA_MODEL", "mistral")
TIMEOUT = int(os.environ.get("MEMORYOS_OLLAMA_TIMEOUT", "120"))


def is_ollama_running() -> bool:
    try:
        with urlopen(f"{OLLAMA_BASE}/api/tags", timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def generate(prompt: str, system: str = "", temperature: float = 0.2) -> Optional[str]:
    if not is_ollama_running():
        raise RuntimeError("Ollama is not running. Start it with: ollama serve")

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": 2048,
        },
    }

    data = json.dumps(payload).encode("utf-8")
    request = Request(
        f"{OLLAMA_BASE}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT) as response:
            body = response.read().decode("utf-8")
        return json.loads(body).get("response", "").strip()
    except TimeoutError as exc:
        raise RuntimeError(f"Ollama timed out after {TIMEOUT}s") from exc
    except (HTTPError, URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc


def extract_json(response: str) -> Optional[dict]:
    text = response.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                return None
    return None

"""Replay recorded provider responses; any unrecorded request fails the test (routing D8)."""

import json
from pathlib import Path
from typing import Any

import httpx

FIXTURES = Path(__file__).parent / "fixtures"
SECRET_PARAMS = {"api_key"}


def request_signature(request: httpx.Request) -> dict[str, Any]:
    """What identifies a request in a recording: everything except the key."""
    query = sorted((k, v) for k, v in request.url.params.multi_items() if k not in SECRET_PARAMS)
    body = json.loads(request.content) if request.content else None
    return {"method": request.method, "path": request.url.path, "query": query, "body": body}


def _key(signature: dict[str, Any]) -> str:
    return json.dumps(signature, sort_keys=True)


def replay_transport(name: str) -> httpx.MockTransport:
    recorded = json.loads((FIXTURES / f"{name}.json").read_text())
    responses = {_key(item["request"]): item["response"] for item in recorded}

    def handler(request: httpx.Request) -> httpx.Response:
        signature = request_signature(request)
        response = responses.get(_key(signature))
        if response is None:
            raise AssertionError(
                f"No recorded response in {name}.json for {signature['method']} "
                f"{signature['path']}. Re-record with tests/providers/record_fixtures.py."
            )
        return httpx.Response(response["status"], json=response["body"])

    return httpx.MockTransport(handler)


def replay_client(name: str, base_url: str) -> httpx.Client:
    return httpx.Client(base_url=base_url, transport=replay_transport(name))

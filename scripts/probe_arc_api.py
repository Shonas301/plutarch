"""probe every arc raiders api endpoint and print response shapes."""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime

import aiohttp
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://arctracker.io"
APP_KEY = os.getenv("ARC_API_KEY", "")
USER_KEY = os.getenv("ARC_USER_KEY", "")

# public endpoints (no auth)
PUBLIC_ENDPOINTS = [
    {"method": "GET", "path": "/api/items", "params": {}},
    {"method": "GET", "path": "/api/quests", "params": {}},
    {"method": "GET", "path": "/api/hideout", "params": {}},
    {"method": "GET", "path": "/api/projects", "params": {}},
    {"method": "GET", "path": "/api/projects", "params": {"season": "1"}, "label": "/api/projects?season=1"},
]

# authenticated endpoints (dual-key: app key + user key)
AUTH_ENDPOINTS = [
    {"method": "GET", "path": "/api/v2/user/profile", "params": {}},
    {
        "method": "GET",
        "path": "/api/v2/user/stash",
        "params": {"locale": "en", "page": "1", "per_page": "10", "sort": "slot"},
    },
    {"method": "GET", "path": "/api/v2/user/loadout", "params": {"locale": "en"}},
    {"method": "GET", "path": "/api/v2/user/quests", "params": {"locale": "en"}},
    {"method": "GET", "path": "/api/v2/user/quests", "params": {"locale": "en", "filter": "completed"}, "label": "/api/v2/user/quests?filter=completed"},
    {"method": "GET", "path": "/api/v2/user/hideout", "params": {"locale": "en"}},
    {"method": "GET", "path": "/api/v2/user/projects", "params": {"locale": "en"}},
    {"method": "GET", "path": "/api/v2/user/projects", "params": {"locale": "en", "season": "1"}, "label": "/api/v2/user/projects?season=1"},
]


def _shape(obj, depth=0, max_array_sample=2):
    """Recursively extract the shape/structure of a json response.

    for arrays, samples the first few elements. for objects, recurses into
    each key. scalars are represented by their type and a sample value.
    """
    if isinstance(obj, dict):
        return {k: _shape(v, depth + 1) for k, v in obj.items()}
    if isinstance(obj, list):
        if not obj:
            return ["<empty list>"]
        sampled = obj[:max_array_sample]
        shapes = [_shape(item, depth + 1) for item in sampled]
        note = f"<list of {len(obj)} items, showing {len(sampled)}>"
        return [note, *shapes]
    if isinstance(obj, str):
        preview = obj[:80] + ("..." if len(obj) > 80 else "")
        return f"<str> {preview!r}"
    if isinstance(obj, bool):
        return f"<bool> {obj}"
    if isinstance(obj, int):
        return f"<int> {obj}"
    if isinstance(obj, float):
        return f"<float> {obj}"
    if obj is None:
        return "<null>"
    return f"<{type(obj).__name__}>"


def _rate_limit_info(headers):
    """Pull rate limit headers if present."""
    info = {}
    for key in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
        val = headers.get(key)
        if val is not None:
            info[key] = val
    return info or None


async def _hit(session, endpoint, auth=False):
    """Hit a single endpoint and return result dict."""
    label = endpoint.get("label", endpoint["path"])
    url = f"{BASE_URL}{endpoint['path']}"
    headers = {}

    if auth:
        if not APP_KEY or not USER_KEY:
            return {
                "endpoint": label,
                "skipped": True,
                "reason": "missing ARC_API_KEY and/or ARC_USER_KEY env vars",
            }
        headers["X-App-Key"] = APP_KEY
        headers["Authorization"] = f"Bearer {USER_KEY}"

    try:
        async with session.get(url, params=endpoint["params"], headers=headers) as resp:
            status = resp.status
            rate_limits = _rate_limit_info(resp.headers)
            content_type = resp.headers.get("Content-Type", "")

            body = None
            shape = None
            raw_text = None

            if "application/json" in content_type:
                body = await resp.json()
                shape = _shape(body)
            else:
                raw_text = (await resp.text())[:500]

            result = {
                "endpoint": label,
                "params": endpoint["params"] or None,
                "status": status,
                "content_type": content_type,
            }
            if rate_limits:
                result["rate_limits"] = rate_limits
            if shape is not None:
                result["response_shape"] = shape
            if raw_text is not None:
                result["raw_preview"] = raw_text
            if body is not None and status >= 400:
                result["error_body"] = body

            return result

    except Exception as e:
        return {
            "endpoint": label,
            "error": f"{type(e).__name__}: {e}",
        }


async def main():
    results = {"probed_at": datetime.now(UTC).isoformat(), "public": [], "authenticated": []}

    async with aiohttp.ClientSession() as session:
        # hit public endpoints concurrently
        public_tasks = [_hit(session, ep, auth=False) for ep in PUBLIC_ENDPOINTS]
        results["public"] = await asyncio.gather(*public_tasks)

        # hit auth endpoints concurrently
        auth_tasks = [_hit(session, ep, auth=True) for ep in AUTH_ENDPOINTS]
        results["authenticated"] = await asyncio.gather(*auth_tasks)

    # print to stdout
    output = json.dumps(results, indent=2, default=str)
    print(output)

    # also write to file for reference
    out_path = os.path.join(os.path.dirname(__file__), "..", "arc_api_shapes.json")
    out_path = os.path.normpath(out_path)
    with open(out_path, "w") as f:
        f.write(output)
        f.write("\n")
    print(f"\nwritten to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())

"""
Samzy XAU/USD Assistant — web app.

Serves the dashboard UI and, on startup, launches app/mcp_server.py as a
child process and speaks MCP to it over stdio for the lifetime of the app.
Every request below calls an MCP tool directly — there's no LLM in the
loop, just plain REST endpoints backed by the MCP server:

    GET  /api/price          -> get_price tool
    GET  /api/alerts         -> list_price_alerts tool
    POST /api/alerts         -> create_price_alert tool
    DELETE /api/alerts/{id}  -> delete_price_alert tool

Run:
    uvicorn app.web_app:app --reload
"""
import asyncio
import json
import os
import sys
import time
from contextlib import asynccontextmanager

# Windows only: subprocess creation (spawning mcp_server.py below) requires
# ProactorEventLoop. Something in some environments — conda's base env,
# Jupyter/tornado tooling, uvicorn's --reload supervisor — can leave the
# SelectorEventLoop policy active instead, which raises NotImplementedError
# the moment we try to open a subprocess. Force the right one explicitly,
# before anything else touches asyncio.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

_price_cache = {"data": None, "ts": 0.0}
_PRICE_CACHE_TTL = 60  # seconds — keeps the UI's price ticker from burning API quota


class ToolError(Exception):
    pass


def _tool_blocks_to_list(result):
    """
    Parse each MCP content block's JSON text into a python object and
    return them as a list.

    This SDK version emits one content block *per list item* for
    list-returning tools (0 items -> 0 blocks, 1 item -> 1 block, 2 items
    -> 2 blocks) rather than a single block containing a JSON array — so
    callers that expect a dict (get_price, create_price_alert,
    delete_price_alert) should take element [0]; callers that expect a
    list (list_price_alerts) can use the returned list directly, and it
    behaves correctly at every length including exactly one.
    """
    if getattr(result, "isError", False):
        text = "".join(getattr(b, "text", "") for b in result.content)
        raise ToolError(text or "tool call failed")
    return [json.loads(b.text) for b in result.content if getattr(b, "text", None)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_server"],
        cwd=settings.PROJECT_ROOT,
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            app.state.mcp_session = session
            yield


app = FastAPI(title="Samzy XAU/USD Assistant", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index():
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


@app.get("/api/price")
async def api_price():
    now = time.time()
    if _price_cache["data"] is None or (now - _price_cache["ts"]) > _PRICE_CACHE_TTL:
        try:
            result = await app.state.mcp_session.call_tool("get_price", {})
            objs = _tool_blocks_to_list(result)
            _price_cache["data"] = objs[0] if objs else None
            _price_cache["ts"] = now
        except ToolError as e:
            return JSONResponse({"error": str(e)}, status_code=502)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=502)
    return _price_cache["data"]


@app.get("/api/alerts")
async def api_list_alerts(status: str = "all"):
    try:
        result = await app.state.mcp_session.call_tool("list_price_alerts", {"status": status})
        return _tool_blocks_to_list(result)
    except ToolError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/alerts")
async def api_create_alert(req: Request):
    body = await req.json()
    condition = (body.get("condition") or "").strip().lower()
    target_price = body.get("target_price")
    email = (body.get("email") or "").strip()
    note = (body.get("note") or "").strip()

    if condition not in ("above", "below"):
        return JSONResponse({"error": 'condition must be "above" or "below"'}, status_code=400)
    try:
        target_price = float(target_price)
    except (TypeError, ValueError):
        return JSONResponse({"error": "target_price must be a number"}, status_code=400)

    try:
        result = await app.state.mcp_session.call_tool(
            "create_price_alert",
            {"condition": condition, "target_price": target_price, "email": email, "note": note},
        )
        objs = _tool_blocks_to_list(result)
        return objs[0] if objs else {}
    except ToolError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@app.delete("/api/alerts/{alert_id}")
async def api_delete_alert(alert_id: str):
    try:
        result = await app.state.mcp_session.call_tool("delete_price_alert", {"alert_id": alert_id})
        objs = _tool_blocks_to_list(result)
        return objs[0] if objs else {}
    except ToolError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

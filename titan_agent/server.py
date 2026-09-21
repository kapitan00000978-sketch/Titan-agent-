import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import TitanAgent
from .config import MCP_CONFIG_FILE, WORKSPACE_DIR
from .llm_client import LLMClient
from .mcp_client import MCPManager
from .memory import MemoryManager
from .scheduler import CronScheduler
from .telegram import TelegramError, TelegramManager
from .tools import ToolRegistry

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: attempt to start MCP servers (mcp_manager is defined at module
    # load, before the app ever starts serving, so this lookup is always valid).
    asyncio.create_task(mcp_manager.start_all())
    # Startup: begin the cron scheduler loop (runs due jobs from cron/jobs.json).
    asyncio.create_task(cron_scheduler.start())
    yield
    # Shutdown
    await cron_scheduler.stop()
    await mcp_manager.stop_all()

app = FastAPI(title="Titan Agent API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
mcp_manager = MCPManager(MCP_CONFIG_FILE)
tool_registry = ToolRegistry(WORKSPACE_DIR)
memory_manager = MemoryManager()
telegram_manager = TelegramManager()
llm_client = LLMClient()
agent = TitanAgent(llm=llm_client, tools=tool_registry, mcp=mcp_manager, memory=memory_manager, telegram=telegram_manager)

async def _cron_runner(prompt: str, session_id: str, mode: str, effort: str) -> str:
    """Runner used by the cron scheduler: execute a prompt with the live agent
    and return the final answer text (errors raise so the job is marked failed)."""
    final = ""
    async for ev in agent.run_task(prompt, session_id=session_id, mode=mode, effort=effort):
        if ev.type == "final_answer":
            final = (final + "\n\n" + ev.data).strip() if final else ev.data
        elif ev.type == "error":
            raise RuntimeError(ev.data)
    return final or "(no answer produced)"

cron_scheduler = CronScheduler(runner=_cron_runner)

WEB_UI_DIR = Path(__file__).resolve().parent / "web_ui"
WEB_UI_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(WEB_UI_DIR)), name="static")

@app.get("/")
async def root():
    index_file = WEB_UI_DIR / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    return HTMLResponse("<h1>Titan Agent Web UI loading...</h1>")

class ChatRequest(BaseModel):
    message: str
    session_id: str = "web_session"
    mode: str = "fast"
    effort: str = "auto"

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    async def event_generator():
        try:
            async for ev in agent.run_task(req.message, session_id=req.session_id, mode=req.mode, effort=req.effort):
                payload = json.dumps(ev.to_dict())
                yield f"data: {payload}\n\n"
        except Exception as e:
            err_payload = json.dumps({"type": "error", "data": str(e)})
            yield f"data: {err_payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

class ToolExecuteRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)

@app.post("/api/tools/execute")
async def execute_tool_endpoint(req: ToolExecuteRequest):
    res = await agent.execute_tool_unified(req.tool_name, req.arguments)
    return {"status": "success", "tool_name": req.tool_name, "result": res}

@app.get("/api/local-models")
async def get_local_models():
    models = await LLMClient.detect_local_models()
    return models

@app.get("/api/token-usage")
async def get_token_usage():
    """Live token throughput guardrail stats (cap enforced on every LLM call)."""
    return llm_client.token_limiter.stats()

@app.get("/api/config")
async def get_config():
    return {
        "provider": llm_client.provider,
        "model": llm_client.model,
        "base_url": llm_client.base_url,
        "has_key": bool(llm_client.api_key),
        "workspace": str(WORKSPACE_DIR)
    }

class ConfigUpdateRequest(BaseModel):
    provider: str
    model: str
    api_key: str = ""
    base_url: str = ""

@app.post("/api/config")
async def update_config(req: ConfigUpdateRequest):
    llm_client.set_model(
        provider=req.provider,
        model=req.model,
        api_key=req.api_key if req.api_key else None,
        base_url=req.base_url if req.base_url else None
    )
    return {"status": "success", "provider": llm_client.provider, "model": llm_client.model}

@app.get("/api/mcp/tools")
async def get_mcp_tools():
    servers_info = {}
    for s_name, conn in mcp_manager.servers.items():
        servers_info[s_name] = {
            "connected": conn.is_connected,
            "tools_count": len(conn.tools),
            "tools": [t.get("name") for t in conn.tools]
        }
    return {
        "servers": servers_info,
        "builtin_tools": [t["function"]["name"] for t in tool_registry.get_tool_definitions()]
    }

@app.get("/api/workspace/files")
async def list_workspace_files():
    files = []
    if WORKSPACE_DIR.exists():
        for p in WORKSPACE_DIR.rglob("*"):
            if p.is_file():
                files.append({
                    "name": p.name,
                    "rel_path": str(p.relative_to(WORKSPACE_DIR)),
                    "size": p.stat().st_size
                })
    return {"files": files}

@app.get("/api/memory")
async def get_memory(query: str = "", scope: str = ""):
    if query:
        return {"knowledge": memory_manager.search_knowledge(query, scope=scope or None)}
    return {"knowledge": memory_manager.get_all_knowledge()}

@app.get("/api/memory/vault")
async def get_memory_vault(scope: str = ""):
    return {"vault": memory_manager.vault_list(scope=scope or None, limit=200)}

@app.get("/api/memory/handoffs")
async def get_handoffs(status: str = "open"):
    return {"handoffs": memory_manager.list_handoffs(status=status or None)}

# ---- Telegram account manager (consent-gated) ----
class TelegramLoginStartRequest(BaseModel):
    label: str
    phone: str

class TelegramLoginConfirmRequest(BaseModel):
    label: str
    code: str

class TelegramSendRequest(BaseModel):
    label: str
    target: str
    text: str

class TelegramLogoutRequest(BaseModel):
    label: str
    delete: bool = False

def _tg(resp_fn):
    try:
        return resp_fn()
    except TelegramError as e:
        return {"status": "error", "detail": str(e)}

@app.get("/api/telegram/status")
async def telegram_status():
    return {"status": "success", "data": telegram_manager.status()}

@app.get("/api/telegram/accounts")
async def telegram_accounts():
    return _tg(lambda: {"status": "success", "accounts": telegram_manager.list_accounts()})

@app.post("/api/telegram/login/start")
async def telegram_login_start(req: TelegramLoginStartRequest):
    return _tg(lambda: {"status": "success", "data": telegram_manager.login_start(req.label, req.phone)})

@app.post("/api/telegram/login/confirm")
async def telegram_login_confirm(req: TelegramLoginConfirmRequest):
    return _tg(lambda: {"status": "success", "data": telegram_manager.login_confirm(req.label, req.code)})

@app.post("/api/telegram/send")
async def telegram_send(req: TelegramSendRequest):
    return _tg(lambda: {"status": "success", "data": telegram_manager.send_message(req.label, req.target, req.text)})

@app.get("/api/telegram/recent")
async def telegram_recent(label: str, limit: int = 10):
    return _tg(lambda: {"status": "success", "messages": telegram_manager.recent_messages(label, limit=limit)})

@app.post("/api/telegram/logout")
async def telegram_logout(req: TelegramLogoutRequest):
    return _tg(lambda: {"status": "success", "data": telegram_manager.logout(req.label, delete=req.delete)})

class CronJobRequest(BaseModel):
    prompt: str
    name: str = "cron job"
    schedule: Dict[str, Any] = Field(default_factory=lambda: {"interval_minutes": 60})
    mode: str = "fast"
    effort: str = "auto"
    session_id: str = ""
    enabled: bool = True
    job_id: str = ""

@app.get("/api/cron/jobs")
async def cron_list():
    return {"jobs": cron_scheduler.list_jobs()}

@app.post("/api/cron/jobs")
async def cron_add(req: CronJobRequest):
    try:
        job = cron_scheduler.add_job(
            prompt=req.prompt,
            name=req.name,
            schedule=req.schedule,
            mode=req.mode,
            effort=req.effort,
            session_id=req.session_id,
            enabled=req.enabled,
            job_id=req.job_id,
        )
        return {"status": "success", "job": job}
    except ValueError as e:
        return {"status": "error", "detail": str(e)}

@app.delete("/api/cron/jobs/{job_id}")
async def cron_delete(job_id: str):
    ok = cron_scheduler.remove_job(job_id)
    return {"status": "success" if ok else "error"}

@app.post("/api/cron/jobs/{job_id}/toggle")
async def cron_toggle(job_id: str):
    job = cron_scheduler.toggle_job(job_id)
    if job is None:
        return {"status": "error", "detail": "Unknown job"}
    return {"status": "success", "job": job}

@app.post("/api/cron/jobs/{job_id}/run")
async def cron_run(job_id: str):
    try:
        job = await cron_scheduler.run_now(job_id)
        return {"status": "success", "job": job}
    except KeyError as e:
        return {"status": "error", "detail": str(e)}

import os
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse

from . import config
from .log import setup_logging, tail_log
from .runner import Runner
from .state import StateManager

BASE_DIR = Path(__file__).resolve().parents[1]
STATE_DIR = Path(os.getenv("STATE_DIR", BASE_DIR / "state"))
LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs"))
API_KEY = os.getenv("API_KEY", "").strip()
AUTO_START = os.getenv("AUTO_START", "true").lower() in {"1", "true", "yes", "on"}

log_file = setup_logging(LOG_DIR)
state_manager = StateManager(STATE_DIR)
runner = Runner(state_manager)

app = FastAPI(title="Photo Downloader Service")


def require_api_key(request: Request):
    """
    简单鉴权：如果设置了 API_KEY，则需要请求头 x-api-key 匹配。
    """
    if not API_KEY:
        return
    header_key = request.headers.get("x-api-key", "")
    if header_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


@app.on_event("startup")
async def on_startup():
    if AUTO_START:
        await runner.start()


@app.on_event("shutdown")
async def on_shutdown():
    await runner.stop()


@app.get("/api/health")
async def health():
    return {"status": "ok", "running": runner.is_running()}


@app.get("/api/status")
async def get_status():
    status_data = state_manager.load_status()
    status_data["running"] = runner.is_running()
    status_data["config"] = state_manager.load_runtime_config()
    status_data["default"] = {
        "target_url": config.TARGET_URL,
        "check_interval": config.CHECK_INTERVAL,
        "dropbox_save_path": config.DROPBOX_SAVE_PATH,
    }
    return status_data


@app.get("/api/history")
async def get_history(limit: int = 20):
    limit = max(1, min(limit, 200))
    return {"items": state_manager.load_history(limit)}


@app.get("/api/logs")
async def get_logs(tail: int = 200):
    tail = max(10, min(tail, 2000))
    lines = tail_log(log_file, tail=tail)
    return {"lines": lines}


@app.post("/api/control/start")
async def start_loop(
    payload: dict,
    _: Optional[str] = Depends(require_api_key),
):
    if runner.is_running():
        raise HTTPException(status_code=400, detail="monitor is already running")

    target_url = payload.get("target_url", "").strip()
    dropbox_path = payload.get("dropbox_save_path", "").strip()
    try:
        interval = int(payload.get("check_interval", 0))
    except (TypeError, ValueError):
        interval = 0

    if not target_url:
        raise HTTPException(status_code=400, detail="target_url is required")
    if interval <= 0:
        raise HTTPException(status_code=400, detail="check_interval must be > 0")
    if not dropbox_path:
        raise HTTPException(status_code=400, detail="dropbox_save_path is required")

    config_override = {
        "target_url": target_url,
        "check_interval": interval,
        "dropbox_save_path": dropbox_path,
    }
    started = await runner.start(config_override=config_override)
    if not started:
        return JSONResponse({"message": "already running"}, status_code=200)
    return {"message": "started", "config": config_override}


@app.post("/api/control/stop")
async def stop_loop(_: Optional[str] = Depends(require_api_key)):
    stopped = await runner.stop()
    if not stopped:
        return JSONResponse({"message": "not running"}, status_code=200)
    return {"message": "stopped"}


@app.post("/api/control/run-once")
async def run_once(
    payload: dict,
    _: Optional[str] = Depends(require_api_key),
):
    config_override = None
    if payload:
        config_override = {
            "target_url": payload.get("target_url", config.TARGET_URL),
            "check_interval": payload.get("check_interval", config.CHECK_INTERVAL),
            "dropbox_save_path": payload.get("dropbox_save_path", config.DROPBOX_SAVE_PATH),
        }
    # 避免与后台循环并发执行
    await runner.stop()
    result = await runner.run_once(config_override=config_override)
    # run_once 结束后不保存运行时配置
    runner._active_config = None
    state_manager.clear_runtime_config()
    return {"message": "completed", "result": result}


@app.get("/api/config")
async def get_config():
    return {
        "runtime": state_manager.load_runtime_config(),
        "default": {
            "target_url": config.TARGET_URL,
            "check_interval": config.CHECK_INTERVAL,
            "dropbox_save_path": config.DROPBOX_SAVE_PATH,
        },
        "constraints": {
            "editable": not runner.is_running(),  # 运行时不允许修改
        },
    }

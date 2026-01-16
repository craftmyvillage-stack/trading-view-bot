import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from the.state_manager import state_engine
from the.event_logger import EventLogger
from the.telegram_reporter import telegram_reporter
import uvicorn
import logging

logger = logging.getLogger(__name__)

app = FastAPI()
event_logger = EventLogger()

# Absolute path to index.html for reliable serving
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "index.html")

@app.get("/")
async def read_index():
    if not os.path.exists(INDEX_PATH):
        logger.error(f"DASHBOARD ERROR: index.html not found at {INDEX_PATH}")
        return {"error": f"Dashboard UI file missing at {INDEX_PATH}"}
    return FileResponse(INDEX_PATH)

@app.post("/report/send")
async def trigger_report():
    success = await telegram_reporter.send_report()
    return {"status": "SUCCESS" if success else "FAILED"}

@app.get("/status")
async def get_status():
    state = state_engine.get_state()
    wallet = state.get("wallet", {})
    return {
        "status": "ONLINE" if not state["kill_switch"]["full_system_freeze"] else "FREEZE",
        "mode": state["system_mode"],
        "active_trades": len(state["active_trades"]),
        "daily_pnl": state["daily_loss"]["current"],
        "wallet": wallet,
        "thinking": state["bot_thinking"]
    }

@app.get("/logs/recent")
async def get_recent_logs():
    return event_logger.get_recent_logs(20)

@app.get("/trades/active")
async def get_active_trades():
    return list(state_engine.get_state()["active_trades"].values())

def start_dashboard_server():
    """Explicitly start the dashboard server (Replit safe)"""
    port = int(os.environ.get("PORT", 5000))
    print(f"DASHBOARD READY → http://0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="error")

if __name__ == "__main__":
    start_dashboard_server()

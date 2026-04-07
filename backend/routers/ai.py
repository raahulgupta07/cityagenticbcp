"""AI router — insights + chat WebSocket."""
from typing import Optional
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from utils.ai_agent import morning_briefing, kpi_insight, table_insight, site_insight
from backend.routers.auth import get_current_user

router = APIRouter()


class InsightRequest(BaseModel):
    type: str  # briefing, kpi, table, site
    data: dict
    force_refresh: bool = False


@router.post("/insights")
def get_insight(req: InsightRequest, user: dict = Depends(get_current_user)):
    if req.type == "briefing":
        return {"content": morning_briefing(req.data, force_refresh=req.force_refresh)}
    elif req.type == "kpi":
        return {"content": kpi_insight(req.data, force_refresh=req.force_refresh)}
    elif req.type == "table":
        summary = req.data.get("summary", "")
        table_type = req.data.get("table_type", "sector")
        return {"content": table_insight(summary, table_type, force_refresh=req.force_refresh)}
    elif req.type == "site":
        return {"content": site_insight(req.data, force_refresh=req.force_refresh)}
    return {"content": "Unknown insight type"}


@router.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    await websocket.accept()
    history = []
    try:
        while True:
            msg = await websocket.receive_text()
            try:
                from agents.chat_agent import chat as chat_fn
                result = chat_fn(msg, history)
                response = result.get("response") or ""
                tools = result.get("tool_calls") or []
                error = result.get("error")

                if error:
                    await websocket.send_json({"type": "error", "content": error})
                else:
                    history.append({"role": "user", "content": msg})
                    history.append({"role": "assistant", "content": response})
                    await websocket.send_json({
                        "type": "message",
                        "content": response,
                        "tools": [{"tool": t["tool"], "preview": t.get("result_preview", "")[:120]} for t in tools],
                    })
            except ImportError:
                await websocket.send_json({"type": "message", "content": f"Chat agent not available. You said: {msg}", "tools": []})
            except Exception as e:
                await websocket.send_json({"type": "error", "content": str(e)})
    except WebSocketDisconnect:
        pass

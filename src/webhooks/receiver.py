"""
Webhook 接收器 — 接收外部服务回调
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/webhook", tags=["webhooks"])
logger = logging.getLogger(__name__)
EVENTS_DIR = Path("data/events")


@router.post("/{source}")
async def receive_webhook(source: str, request: Request):
    """
    接收外部 Webhook

    source: lingxing / sellersprite / dingtalk / custom
    body: JSON payload
    """
    try:
        body = await request.json()
    except Exception:
        body = {"raw": (await request.body()).decode("utf-8", errors="replace")}

    # 存入 data/events/{source}/{timestamp}.json
    source_dir = EVENTS_DIR / source
    source_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")
    filepath = source_dir / f"{ts}.json"

    payload = {
        "source": source,
        "received_at": datetime.now().isoformat(),
        "headers": dict(request.headers),
        "body": body,
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    logger.info(f"Webhook received: {source} → {filepath}")
    return {"status": "received", "source": source, "file": str(filepath)}


@router.get("/events")
async def list_events(source: str = None, limit: int = 20):
    """列出最近的 Webhook 事件"""
    events = []
    sources = [source] if source else [d.name for d in EVENTS_DIR.iterdir() if d.is_dir()]

    for src in sources:
        src_dir = EVENTS_DIR / src
        if not src_dir.exists():
            continue
        for fp in sorted(src_dir.glob("*.json"), reverse=True)[:limit]:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_file"] = fp.name
            events.append(data)

    events.sort(key=lambda x: x.get("received_at", ""), reverse=True)
    return {"events": events[:limit], "total": len(events)}

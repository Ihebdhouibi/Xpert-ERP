"""Real-time notification push — WS /notifications/ws.

Complements inbox_router.py's REST polling: create_app_notification()
publishes to a per-user Redis channel, and this route forwards whatever
arrives on that channel straight to the browser. The bell's REST polling
(TopBar.tsx) is kept as a long-interval fallback in case a socket drops,
so this is additive, not a replacement for the REST endpoints.

Browsers can't set custom headers on a WebSocket handshake, so the access
token travels as a query param instead of the usual Authorization header
(no less exposed than a header once the connection is wss://).
"""
from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from jwt.exceptions import PyJWTError as JWTError

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.modules.auth.service import decode_token, is_token_denied
from app.modules.notification.inbox_router import notification_channel

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = get_logger("notification.ws_router")


@router.websocket("/ws")
async def notifications_ws(websocket: WebSocket, token: str = Query(...)) -> None:
    redis = get_redis()

    try:
        payload = decode_token(token, expected_type="access")
        jti = payload.get("jti", "")
        if jti and await is_token_denied(redis, jti):
            raise JWTError("Token has been revoked")
    except JWTError:
        # Reject before accept() — the client sees a failed handshake, same
        # shape as any other auth failure, rather than an open-then-closed socket.
        await websocket.close(code=4401)
        return

    garage_id: int = payload["gid"]
    user_id: int = payload.get("uid", 0)
    channel = notification_channel(garage_id, user_id)

    await websocket.accept()
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    try:
        async for message in pubsub.listen():
            if message.get("type") != "message":
                continue
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 — never crash the worker over one bad socket
        logger.warning("notification_ws_error", error=str(exc), user_id=user_id)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()

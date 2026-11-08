"""Watch-together server: rooms, names, host controls, chat, synced playback.

Run:  uvicorn main:app --reload
Open: http://localhost:8000/?room=movie-night
"""
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

app = FastAPI()
rooms: dict[str, dict] = {}
CONTROL = {"load", "play", "pause", "seek"}


def new_room() -> dict:
    return {
        "users": {},          # id -> {"ws", "name"}; insertion order = join order
        "host": None,
        "open": False,        # True = everyone may control playback
        "controllers": set(), # ids the host has allowed to control
        "state": {"url": "", "playing": False, "time": 0.0, "ts": time.time()},
    }


def can_control(room: dict, uid: str) -> bool:
    return uid == room["host"] or room["open"] or uid in room["controllers"]


def snapshot(state: dict) -> dict:
    elapsed = time.time() - state["ts"] if state["playing"] else 0
    return {"type": "state", "url": state["url"], "playing": state["playing"],
            "time": state["time"] + elapsed}


def roster(room: dict) -> dict:
    return {
        "type": "roster",
        "host": room["host"],
        "open": room["open"],
        "users": [{"id": i, "name": u["name"], "canControl": can_control(room, i)}
                  for i, u in room["users"].items()],
    }


async def broadcast(room: dict, message: dict, skip: str | None = None):
    for uid, user in list(room["users"].items()):
        if uid != skip:
            try:
                await user["ws"].send_json(message)
            except Exception:
                pass


def clean_name(raw) -> str:
    name = str(raw or "").strip()[:24]
    return name or f"Guest-{uuid.uuid4().hex[:4]}"


def num(value) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "index.html")


async def handle(room: dict, uid: str, msg: dict):
    user, state, kind = room["users"][uid], room["state"], msg.get("type")

    if kind == "chat":
        text = str(msg.get("text", "")).strip()[:500]
        if text:
            await broadcast(room, {"type": "chat", "id": uid, "name": user["name"], "text": text})

    elif kind in CONTROL:
        if not can_control(room, uid):  # not allowed: snap this viewer back to the room state
            await user["ws"].send_json(snapshot(state))
            return
        if kind == "load":
            state.update(url=str(msg.get("url", "")), playing=False, time=0.0)
        elif kind == "play":
            state.update(playing=True, time=num(msg.get("time")))
        elif kind == "pause":
            state.update(playing=False, time=num(msg.get("time")))
        else:
            state["time"] = num(msg.get("time"))
        state["ts"] = time.time()
        await broadcast(room, snapshot(state), skip=uid)

    elif uid == room["host"]:
        if kind == "set_open":
            room["open"] = bool(msg.get("open"))
            await broadcast(room, {"type": "notice", "text":
                "Everyone can control playback" if room["open"] else "Only the host and approved viewers can control playback"})
            await broadcast(room, roster(room))
        elif kind == "grant":
            target = msg.get("id")
            if target in room["users"] and target != uid:
                (room["controllers"].add if msg.get("allowed") else room["controllers"].discard)(target)
                await broadcast(room, roster(room))


async def leave(room_name: str, room: dict, uid: str):
    user = room["users"].pop(uid, None)
    room["controllers"].discard(uid)
    if not room["users"]:
        rooms.pop(room_name, None)
        return
    if user:
        await broadcast(room, {"type": "notice", "text": f"{user['name']} left"})
    if room["host"] == uid:
        room["host"] = next(iter(room["users"]))
        await broadcast(room, {"type": "notice", "text": f"{room['users'][room['host']]['name']} is now the host"})
    await broadcast(room, roster(room))


@app.websocket("/ws/{room_name}")
async def room_socket(ws: WebSocket, room_name: str):
    await ws.accept()
    room, uid = None, None
    try:
        first = await ws.receive_json()
        if first.get("type") != "join":
            await ws.close()
            return
        room = rooms.setdefault(room_name, new_room())
        uid = uuid.uuid4().hex[:8]
        name = clean_name(first.get("name"))
        room["users"][uid] = {"ws": ws, "name": name}
        if room["host"] is None:
            room["host"] = uid

        await ws.send_json({"type": "hello", "id": uid})
        await ws.send_json(snapshot(room["state"]))
        await broadcast(room, {"type": "notice", "text": f"{name} joined"}, skip=uid)
        await broadcast(room, roster(room))

        while True:
            await handle(room, uid, await ws.receive_json())
    except WebSocketDisconnect:
        pass
    finally:
        if room is not None and uid in room["users"]:
            await leave(room_name, room, uid)
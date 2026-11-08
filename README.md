# Commonroom

Watch videos together in sync. Everyone opens the same room link, one person picks a video, and play, pause, and seek stay in step for the whole room. A small chat sits beside the player.

Commonroom is a FastAPI server plus a single HTML page. There is no database, no build step, and no accounts.

## Features

- **Synced playback** for YouTube links and direct video files (`.mp4`, `.webm`)
- **Rooms** that anyone can join from a link, with a live participant list
- **Host controls:** the first person in a room is the host. Only the host can load videos and control playback, unless they let everyone do it or approve specific people
- **Chat** with join and leave notices
- **Late joiners** land at the right timestamp in the right play or pause state
- **Invite link** button, light and dark themes, and a mobile-friendly layout

## Quick start

You need Python 3.10 or newer.

```bash
git clone <https://github.com/michaelhwin/CommonRoom>
cd commonroom

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn main:app --reload
```

Open <http://localhost:8000>. The page creates a random room and adds `?room=...` to the address. Open the same address in a second tab or browser to see the sync.

## Using it

1. Open the page, enter a name, and join. The first person in a room is the host.
2. The host pastes a YouTube link or a direct video link and clicks **Load video**.
3. Everyone in the room follows play, pause, and seek.
4. Click **Copy invite link** and send it to friends. Join the room yourself before sharing, so you are the host.
5. In the sidebar, the host can tick **Everyone can control playback**, or use **Allow control** next to a name to approve one person.

### Which links work

| Link type | Works? | Notes |
| --- | --- | --- |
| YouTube (`youtube.com/watch`, `youtu.be`, Shorts, embeds) | Yes | Plays in YouTube's embedded player. Some videos block embedding. |
| Direct `.mp4` or `.webm` URL | Yes | Must be public and point straight to the file. `.mp4` needs H.264 support in the browser. |
| Netflix, Vimeo, other streaming pages | No | These give page links, not video files. |

Every viewer loads the video in their own browser, so the link has to be reachable by everyone in the room.

## Sharing with people outside your network

The server runs on your computer, so friends cannot reach it by default. For a quick session, expose it with a tunnel such as [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/):

```bash
# terminal 1
uvicorn main:app

# terminal 2
cloudflared tunnel --url http://localhost:8000
```

It prints a public `https://...trycloudflare.com` address. Open it, join the room, then share the full address from your browser's address bar. The page switches to secure WebSockets automatically on HTTPS.

The link stops working when you close the tunnel or your computer sleeps. For something permanent, deploy to any host that supports long-lived WebSocket connections and run a single server process (see Limitations).

## How it works

- `main.py` keeps each room's state in memory: the video URL, whether it is playing, and the playback time. It relays events over a WebSocket at `/ws/{room}`.
- `index.html` is the whole frontend. It uses an HTML5 `<video>` element for files and the YouTube IFrame Player API for YouTube.
- Clients send `join`, `chat`, `load`, `play`, `pause`, and `seek` messages. The server checks permissions, updates the room, and broadcasts a state snapshot to everyone else.
- The server advances the clock for playing videos, so a late joiner gets the current position.
- Control permissions are enforced on the server. A viewer without control who tries to seek or pause is snapped back to the room's state.

```
.
├── main.py           FastAPI app: rooms, roles, chat, sync relay
├── index.html        Single-page client
└── requirements.txt
```

## Limitations

- **State is in memory.** Restarting the server clears all rooms and chat history. Running more than one worker or instance would split a room across processes, so use one until you add shared storage such as Redis.
- **No accounts.** Names are not verified, and the first person into a room becomes host. Use hard-to-guess room names, and share links only with people you trust.
- **Refreshing the page** rejoins you as a new person, so a host who refreshes loses host status.
- **Sync is accurate to roughly a second.** Position is corrected on play, pause, and seek events, not continuously.
- **Autoplay rules:** some browsers block playback until the viewer clicks the page.
- Anything public-facing would also want rate limiting and message size limits.

## Ideas for later

- A persistent host key so refreshes keep host status
- Automatic reconnect
- Periodic drift correction for long videos
- A video queue

## Contributing

Issues and pull requests are welcome.
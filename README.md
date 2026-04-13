# sample-client-server

An example self-hosted server for [Inkbox](https://inkbox.ai). A single FastAPI process handles both:

- **`POST /webhook`** — HTTP webhooks for mail events, incoming texts, and incoming calls. Signatures verified via the `inkbox` SDK; bodies parsed with Pydantic models; raw payloads written to `payloads/<ts>.json` for inspection.
- **`WebSocket /phone/media/ws`** — live phone-media sessions once a call is answered. Receives platform events from Inkbox (`start`, `transcript`, `barge_in`, `stop`) and sends outbound `text` frames for Inkbox-managed TTS to play back to the caller.

See `src/data_models/webhooks.py` and `src/data_models/phone_media.py` for the exact JSON shapes exchanged on each side — the app uses those same Pydantic models to validate incoming requests, so "what hits my endpoint" lives in one place.

## Configuration

Copy `.env.example` to `.env` and fill in your values — at minimum `INKBOX_SIGNING_KEY`. When running in Docker you can skip the `.env` file and pass the same variables via `-e` flags; `env_config.py` reads from `os.environ` and treats `.env` as optional.

Signature verification is **on by default**. If you're testing locally without a real signing key, set `INKBOX_REQUIRE_SIGNATURE=false`.

## Run with Docker (recommended)

The easiest way is the helper script, which builds and runs in one step:

```sh
./scripts/run_docker.py
# or: ./scripts/run_docker.py --host-port 9000 --image-name my-inkbox-server
```

Or do it by hand:

```sh
docker build -t inkbox-sample-client-server .
docker run --rm -p 8080:8080 \
  -e INKBOX_SIGNING_KEY=whsec_... \
  -v "$PWD/payloads:/app/payloads" \
  inkbox-sample-client-server
```

The container runs `inkbox-server` on port 8080 and writes received payloads to `/app/payloads` (mount a host directory if you want to read them from outside the container).

## Run locally without Docker

### 1. Install `uv`

**Linux / macOS:**
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows (PowerShell):**
```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Install dependencies

```sh
uv sync
```

### 3. Run

```sh
uv run inkbox-server   # webhooks + phone media WS on :8080
```

## Endpoints

- `POST /webhook` — Inkbox webhook receiver. Verifies `X-Inkbox-Signature` via `inkbox.verify_webhook`, parses the body into a `MailWebhookPayload`, `PhoneIncomingTextWebhookPayload`, or `PhoneIncomingCallWebhookPayload`, writes the raw payload to `payloads/<ts>.json`, and returns `200 OK` (or an `IncomingCallActionResponse` body for `incoming_call` events).
- `WebSocket /phone/media/ws` — Live phone-media session. Inkbox opens this once a call is answered; we optionally verify the handshake signature, accept with `X-Use-Inkbox-{Text-To-Speech,Speech-To-Text}: true` headers, and respond to final `transcript` frames with outbound `text` replies.
- `GET /health` — liveness check.

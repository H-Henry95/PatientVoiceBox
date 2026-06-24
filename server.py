"""Voice bridge server.

Two responsibilities:

1. `/twiml`  — Twilio fetches this when a call connects. We return TwiML that
   opens a *bidirectional* Media Stream back to this server, and we pass the
   chosen scenario id through as a stream <Parameter>.

2. `/media`  — the Twilio Media Stream WebSocket. For each call we open a
   second WebSocket to the OpenAI Realtime API and pump audio both ways:

       Twilio (agent audio, mu-law) ──> OpenAI input_audio_buffer.append
       OpenAI (bot audio,  mu-law) ──> Twilio media frames

   Because both sides are configured for G.711 mu-law @ 8 kHz, audio passes
   through untouched — no resampling. We also:
     * handle barge-in: when the agent starts talking over the bot, we flush
       Twilio's playback buffer and cancel the bot's in-flight response;
     * record both directions to a stereo file;
     * capture a timestamped, speaker-labelled transcript from the Realtime
       events as the primary transcript for each call.

NOTE ON API VERSION: this targets the widely-deployed `gpt-4o-realtime-preview`
Beta schema (flat session fields + the `OpenAI-Beta: realtime=v1` header),
which is the same path Twilio's own quickstart uses. If you switch to the GA
`gpt-realtime` model, the session schema is nested under `audio` — adjust
`_session_update()` per the current OpenAI docs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from pathlib import Path

import websockets
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse

from .audio import StereoRecorder, wav_to_mp3
from .config import settings
from .scenarios import get_scenario

app = FastAPI()

RECORDINGS_DIR = Path("recordings")
TRANSCRIPTS_DIR = Path("transcripts")

OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model={model}"


@app.get("/health")
async def health() -> dict:
    return {"ok": True}


@app.api_route("/twiml", methods=["GET", "POST"])
async def twiml(request: Request) -> HTMLResponse:
    """Return TwiML that connects the call to our media stream."""
    scenario = request.query_params.get("scenario", "schedule_simple")
    label = request.query_params.get("label", scenario)
    response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{settings.ws_url}">
      <Parameter name="scenario" value="{scenario}" />
      <Parameter name="label" value="{label}" />
    </Stream>
  </Connect>
</Response>"""
    return HTMLResponse(content=response, media_type="application/xml")


def _session_update(instructions: str) -> dict:
    """Realtime session config (Beta schema)."""
    return {
        "type": "session.update",
        "session": {
            "instructions": instructions,
            "voice": settings.REALTIME_VOICE,
            "input_audio_format": "g711_ulaw",
            "output_audio_format": "g711_ulaw",
            "modalities": ["audio", "text"],
            "input_audio_transcription": {"model": "whisper-1"},
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 600,
            },
        },
    }


class CallBridge:
    """Owns one call: the Twilio socket, the OpenAI socket, recording, transcript."""

    def __init__(self, twilio_ws: WebSocket):
        self.twilio_ws = twilio_ws
        self.openai_ws: websockets.WebSocketClientProtocol | None = None
        self.stream_sid: str | None = None
        self.scenario_id = "schedule_simple"
        self.label = "schedule_simple"
        self.start_time = time.time()
        self.recorder: StereoRecorder | None = None
        self.transcript: list[dict] = []  # {t, speaker, text}
        self._stop = asyncio.Event()

    # ---- helpers ----------------------------------------------------------
    def _elapsed(self) -> float:
        return time.time() - self.start_time

    def _log_line(self, speaker: str, text: str) -> None:
        text = (text or "").strip()
        if text:
            self.transcript.append({"t": round(self._elapsed(), 1), "speaker": speaker, "text": text})

    async def _send_twilio(self, payload: dict) -> None:
        await self.twilio_ws.send_text(json.dumps(payload))

    # ---- Twilio -> OpenAI -------------------------------------------------
    async def pump_twilio_to_openai(self) -> None:
        try:
            while not self._stop.is_set():
                raw = await self.twilio_ws.receive_text()
                data = json.loads(raw)
                event = data.get("event")

                if event == "start":
                    self.stream_sid = data["start"]["streamSid"]
                    params = data["start"].get("customParameters", {}) or {}
                    self.scenario_id = params.get("scenario", self.scenario_id)
                    self.label = params.get("label", self.scenario_id)
                    self.start_time = time.time()
                    self.recorder = StereoRecorder(self.start_time)
                    await self._configure_openai()

                elif event == "media":
                    payload = data["media"]["payload"]  # base64 mu-law
                    if self.recorder is not None:
                        self.recorder.add_agent(self._elapsed(), base64.b64decode(payload))
                    if self.openai_ws is not None:
                        await self.openai_ws.send(json.dumps({
                            "type": "input_audio_buffer.append",
                            "audio": payload,
                        }))

                elif event == "stop":
                    break
        except Exception:
            pass
        finally:
            self._stop.set()

    # ---- OpenAI -> Twilio -------------------------------------------------
    async def pump_openai_to_twilio(self) -> None:
        assert self.openai_ws is not None
        try:
            async for raw in self.openai_ws:
                if self._stop.is_set():
                    break
                event = json.loads(raw)
                etype = event.get("type")

                if etype == "response.audio.delta" and event.get("delta"):
                    delta = event["delta"]  # base64 mu-law
                    if self.recorder is not None:
                        self.recorder.add_bot(self._elapsed(), base64.b64decode(delta))
                    if self.stream_sid:
                        await self._send_twilio({
                            "event": "media",
                            "streamSid": self.stream_sid,
                            "media": {"payload": delta},
                        })

                elif etype == "input_audio_buffer.speech_started":
                    # The agent started talking -> barge-in. Flush whatever the
                    # bot was saying and cancel the in-flight response.
                    if self.stream_sid:
                        await self._send_twilio({"event": "clear", "streamSid": self.stream_sid})
                    await self.openai_ws.send(json.dumps({"type": "response.cancel"}))

                elif etype == "response.audio_transcript.done":
                    self._log_line("PATIENT_BOT", event.get("transcript", ""))

                elif etype == "conversation.item.input_audio_transcription.completed":
                    self._log_line("AGENT", event.get("transcript", ""))

                elif etype == "error":
                    self._log_line("SYSTEM_ERROR", json.dumps(event.get("error", {})))
        except Exception:
            pass
        finally:
            self._stop.set()

    # ---- watchdog ---------------------------------------------------------
    async def watchdog(self) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=settings.MAX_CALL_SECONDS)
        except asyncio.TimeoutError:
            self._stop.set()

    async def _configure_openai(self) -> None:
        scenario = get_scenario(self.scenario_id)
        await self.openai_ws.send(json.dumps(_session_update(scenario.instructions)))

    # ---- lifecycle --------------------------------------------------------
    async def run(self) -> None:
        await self.twilio_ws.accept()
        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        }
        url = OPENAI_WS_URL.format(model=settings.OPENAI_REALTIME_MODEL)
        # `additional_headers` (websockets >=13) vs `extra_headers` (<=12).
        try:
            connect_cm = websockets.connect(url, additional_headers=headers, max_size=None)
        except TypeError:
            connect_cm = websockets.connect(url, extra_headers=headers, max_size=None)
        async with connect_cm as openai_ws:
            self.openai_ws = openai_ws
            await asyncio.gather(
                self.pump_twilio_to_openai(),
                self.pump_openai_to_twilio(),
                self.watchdog(),
            )
        self._finalize()

    def _finalize(self) -> None:
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(self.start_time))
        base = f"{stamp}_{self.scenario_id}"

        # transcript (primary, from Realtime events)
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        lines = [f"# Call: {self.label} ({self.scenario_id})", f"# Recorded: {stamp}", ""]
        for row in sorted(self.transcript, key=lambda r: r["t"]):
            mm, ss = divmod(int(row["t"]), 60)
            lines.append(f"[{mm:02d}:{ss:02d}] {row['speaker']}: {row['text']}")
        (TRANSCRIPTS_DIR / f"{base}.txt").write_text("\n".join(lines), encoding="utf-8")
        (TRANSCRIPTS_DIR / f"{base}.json").write_text(
            json.dumps({"scenario": self.scenario_id, "label": self.label, "turns": self.transcript}, indent=2),
            encoding="utf-8",
        )

        # recording -> wav -> mp3
        if self.recorder is not None:
            try:
                wav = self.recorder.write_wav(RECORDINGS_DIR / f"{base}.wav")
                try:
                    wav_to_mp3(wav, RECORDINGS_DIR / f"{base}.mp3")
                    wav.unlink(missing_ok=True)  # keep only the mp3
                except Exception:
                    pass  # ffmpeg missing: leave the wav so nothing is lost
            except Exception:
                pass


@app.websocket("/media")
async def media(ws: WebSocket) -> None:
    bridge = CallBridge(ws)
    await bridge.run()

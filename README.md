# Patient Voice Bot

An automated voice bot that calls a clinic's AI phone agent, plays a realistic
patient on the line, records and transcribes the conversation, and drafts
candidate bugs for review.

It dials **only** the approved test number (`+1-805-439-8008`) — the caller
refuses any other destination.

---

## How it works (short version)

```
run_call ──> Twilio places outbound call ──> clinic AI agent answers
                                   │
                       Twilio Media Stream (mu-law, 8 kHz)
                                   │
                          src/server.py  (the bridge)
                                   │
                     OpenAI Realtime API (the patient bot)
```

Audio flows both ways through the bridge. Because Twilio and the Realtime API
both use G.711 mu-law at 8 kHz, audio passes through with no resampling. The
bridge records both sides to a stereo file and captures a timestamped,
speaker-labelled transcript live from the Realtime session. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) for the reasoning behind these choices.

---

## Prerequisites

- Python 3.10+
- `ffmpeg` on your PATH (used to write MP3s) — `brew install ffmpeg` / `apt install ffmpeg`
- A **Twilio** account with a voice-capable phone number
- An **OpenAI** API key with Realtime access
- **ngrok** (or any public tunnel) so Twilio can reach your local server

## Setup

```bash
git clone <your-repo-url>
cd patient-voice-bot
python -m venv .venv && source .venv/bin/activate
make install                 # pip install -r requirements.txt

cp .env.example .env         # then fill in your keys
```

## Run

You need three things up: the **server**, a **tunnel**, and then you place
**calls**.

**Terminal 1 — start the server**
```bash
make serve
```

**Terminal 2 — expose it publicly**
```bash
ngrok http 5050
```
Copy the forwarding host (e.g. `abcd-12-34.ngrok-free.app`) into `PUBLIC_HOST`
in your `.env`, then restart `make serve` so it picks up the value.

**Terminal 3 — place calls**
```bash
# one call
make call SCENARIO=weekend_trap

# the full default batch (14 scenarios -> 14 calls, over the 10 minimum)
make batch
```

Each finished call writes:
- `recordings/<timestamp>_<scenario>.mp3` — stereo (left = agent, right = bot)
- `transcripts/<timestamp>_<scenario>.txt` and `.json` — timestamped, labelled

## After the calls

```bash
# (optional) re-transcribe a recording straight from the audio to double-check wording
make transcribe REC=recordings/<file>.mp3

# draft candidate bugs from the transcripts (DRAFT — verify against audio)
make analyze
```

Then write up the confirmed issues in [`reports/BUG_REPORT.md`](reports/BUG_REPORT.md).

---

## Scenarios

Defined in [`src/scenarios.py`](src/scenarios.py). They cover scheduling,
rescheduling, cancelling, refills (including a controlled-substance edge case),
hours/location/insurance questions, and edge cases: a weekend-booking trap,
interruptions/barge-in, rambling requests, a possible-emergency triage test,
out-of-scope medical-advice requests, two-tasks-in-one-call, and tricky
name/DOB data capture.

List them: `python -c "from src.scenarios import SCENARIOS; print('\n'.join(SCENARIOS))"`

## Notes

- **Secrets** live only in `.env` (gitignored). `.env.example` documents every
  variable.
- **Model version:** the bridge targets the Beta `gpt-4o-realtime-preview`
  session schema. If you switch to GA `gpt-realtime`, adjust the session config
  per the note in `src/server.py`.
- **Cost/safety:** calls are capped at `MAX_CALL_SECONDS` so a stuck call can't
  run indefinitely.


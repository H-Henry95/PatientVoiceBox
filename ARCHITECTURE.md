# Architecture

**How it works.** A call begins when `scripts/run_call.py` asks Twilio to dial
the clinic's test line. When the agent answers, Twilio fetches our `/twiml`
endpoint, which returns a bidirectional `<Connect><Stream>` and passes the
chosen scenario id through as a stream parameter. Twilio then opens a WebSocket
to `src/server.py` and streams the agent's audio to us as G.711 mu-law frames.
For each call the server opens a second WebSocket to the **OpenAI Realtime API**
— configured with that scenario's patient persona — and pumps audio both ways:
agent audio in, synthesized patient audio back out. Server-side voice-activity
detection decides when the patient should respond, and when the agent starts
talking over the bot we flush Twilio's playback buffer and cancel the in-flight
response so interruptions sound natural. The bridge simultaneously records both
directions to a stereo file (agent left, bot right) and captures a timestamped,
speaker-labelled transcript directly from the Realtime events. After the calls,
`src/analyze.py` runs each transcript through a failure-mode rubric to draft
candidate bugs for a human to confirm against the audio.

**Why these choices.** Priority #1 is a *lucid* voice conversation, which lives
or dies on latency, so I chose a single speech-to-speech model (OpenAI
Realtime) over a stitched STT→LLM→TTS pipeline — the latter adds turn-taking
delay and seams that make a phone call feel robotic. The biggest enabler is
that Twilio and the Realtime API can both speak **G.711 mu-law at 8 kHz**, so
audio passes end-to-end with zero resampling, keeping latency low and the code
small. I capture the transcript from the Realtime session itself (rather than
diarizing one mixed audio file) because that gives **certain** speaker labels
and timing for free; a separate `transcribe.py` re-derives a transcript from
the recording when I want to verify exact wording for a bug write-up. Personas
live as data in `src/scenarios.py` so adding an edge case is a few lines, not a
code change, and each persona is written to *probe* a specific failure mode
(impossible times, identity checks, emergency triage, scope limits). Finally,
the caller hard-restricts the destination to the approved test number and every
call is time-capped, so the bot can't dial anywhere it shouldn't or run away
with cost.

**Trade-offs / what I'd do next with more time.** The local stereo recorder
aligns the two channels by wall-clock arrival time rather than sample-exact
sync — fine for review, and Twilio's own dual-channel recording is enabled as a
backup. I leaned on a managed Realtime model instead of a framework like
Pipecat or LiveKit Agents to keep every moving part visible and easy to read;
those frameworks would be the next step for production-grade reconnection,
metrics, and concurrent calls. The bug analyzer is deliberately an assistant,
not an oracle — it surfaces candidates and quotes, and a human confirms before
anything reaches the final report.

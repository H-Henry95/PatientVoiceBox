# Bug Report — Clinic Phone Agent

> **Status: template.** The entries below are filled in *after* running the
> real calls and confirming each issue against the audio. `src/analyze.py`
> drafts candidates; only verified issues belong here. The brief rewards
> useful, well-described bugs over a long list of nitpicks — so each entry
> names what happened, why it matters, and exactly where to find it.

## How to read an entry

```
Bug:       <one-line description>
Severity:  Low | Medium | High
Call:      <transcript file> at <mm:ss>   (recording: <mp3 file>)
Details:   What the patient said, what the agent did, and what it should
           have done instead.
```

## Example (from the brief — shows the format)

```
Bug:       Agent confirms an appointment for Sunday, but the practice is
           closed on weekends.
Severity:  High
Call:      transcript-07.txt at 1:23  (recording: transcript-07.mp3)
Details:   Asked "Can I come in Sunday at 10am?", the agent replied "I've
           scheduled you for Sunday at 10am" without checking office hours.
           It should have said the office is closed weekends and offered the
           next available weekday.
```

---

## Failure modes this suite is built to surface

Each maps to a scenario in `src/scenarios.py`. Use this as your checklist when
reviewing the calls; confirmed instances become numbered findings below.

| # | What to watch for | Scenario that probes it |
|---|---|---|
| 1 | Books closed-hours / weekend slots without flagging | `weekend_trap`, `hours_location` |
| 2 | Says "you're all set" without actually confirming a slot/record | `schedule_simple`, `reschedule` |
| 3 | Takes a med request with no identity verification | `refill_simple` |
| 4 | Agrees to early controlled-substance refill on the phone | `refill_controlled` |
| 5 | Books a routine slot for possible-emergency symptoms instead of triaging to 911 | `emergency` |
| 6 | Gives specific dosing / medical advice it should defer | `out_of_scope` |
| 7 | States costs / network status / hours it cannot actually know | `insurance`, `hours_location` |
| 8 | Garbles name or DOB, or never reads captured data back | `name_spelling`, `schedule_simple` |
| 9 | Drops one task when asked for two | `multi_intent` |
| 10 | Loses track after interruptions; confirms the wrong detail | `interruptions`, `unclear_rambling` |
| 11 | Old slot not freed on reschedule / cancellation not confirmed | `reschedule`, `cancel` |

---

## Findings

> Fill these in from the real calls. Lead with High-severity, well-evidenced
> issues. Delete any rows above that didn't actually reproduce — don't pad.

### Finding 1
```
Bug:
Severity:
Call:        <transcript> at <mm:ss>  (recording: <mp3>)
Details:
```

### Finding 2
```
Bug:
Severity:
Call:        <transcript> at <mm:ss>  (recording: <mp3>)
Details:
```

### Finding 3
```
Bug:
Severity:
Call:        <transcript> at <mm:ss>  (recording: <mp3>)
Details:
```

---

## Summary

- Calls placed: __ / 14
- High-severity issues: __
- Most impactful issue:
- Patterns noticed across calls:

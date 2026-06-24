"""Places the outbound call via the Twilio REST API.

Safety guard: per the brief ("Calls only our test number") this refuses to
dial anything other than the approved target number.
"""

from __future__ import annotations

from twilio.rest import Client

from .config import ALLOWED_TARGET, settings


class DisallowedNumberError(RuntimeError):
    pass


def _client() -> Client:
    missing = [
        name for name, val in {
            "TWILIO_ACCOUNT_SID": settings.TWILIO_ACCOUNT_SID,
            "TWILIO_AUTH_TOKEN": settings.TWILIO_AUTH_TOKEN,
            "TWILIO_FROM_NUMBER": settings.TWILIO_FROM_NUMBER,
            "PUBLIC_HOST": settings.PUBLIC_HOST,
            "OPENAI_API_KEY": settings.OPENAI_API_KEY,
        }.items() if not val
    ]
    if missing:
        raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")
    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def place_call(scenario_id: str, label: str) -> str:
    """Dial the test number and hand the call off to the media-stream server.

    Returns the Twilio call SID.
    """
    target = settings.TARGET_NUMBER
    if target != ALLOWED_TARGET:
        raise DisallowedNumberError(
            f"Refusing to dial {target!r}. This bot may only call the approved "
            f"test number {ALLOWED_TARGET}."
        )

    client = _client()
    twiml_url = f"{settings.https_url}/twiml?scenario={scenario_id}&label={label}"
    call = client.calls.create(
        to=target,
        from_=settings.TWILIO_FROM_NUMBER,
        url=twiml_url,
        # Twilio-side recording as a backup to our own stereo capture.
        record=True,
        recording_channels="dual",
    )
    return call.sid

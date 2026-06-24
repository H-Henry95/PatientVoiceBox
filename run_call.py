"""Place one call.

    python -m scripts.run_call --scenario weekend_trap

Prerequisites: the media server is running and reachable at PUBLIC_HOST
(see README — typically uvicorn + ngrok).
"""

from __future__ import annotations

import argparse

from src.caller import place_call
from src.scenarios import SCENARIOS, get_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description="Place a single patient-bot call.")
    parser.add_argument(
        "--scenario", required=True, choices=sorted(SCENARIOS),
        help="Scenario id (see src/scenarios.py).",
    )
    args = parser.parse_args()
    scenario = get_scenario(args.scenario)
    sid = place_call(scenario.id, scenario.label)
    print(f"Placed call for '{scenario.label}' — Twilio SID: {sid}")
    print("Recording + transcript will be written when the call ends.")


if __name__ == "__main__":
    main()

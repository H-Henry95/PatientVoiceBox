"""Run a batch of calls sequentially (one call at a time).

    python -m scripts.run_batch                 # the default 14-scenario set
    python -m scripts.run_batch --delay 90      # custom gap between calls
    python -m scripts.run_batch --scenarios weekend_trap emergency

Calls are spaced out so each one fully completes (and frees the line) before
the next begins. The default set covers every category in the brief and gives
you 14 calls — comfortably over the 10-call minimum.
"""

from __future__ import annotations

import argparse
import time

from src.caller import place_call
from src.scenarios import DEFAULT_BATCH, SCENARIOS, get_scenario


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a batch of patient-bot calls.")
    parser.add_argument("--scenarios", nargs="*", default=DEFAULT_BATCH,
                        choices=sorted(SCENARIOS), metavar="SCENARIO")
    parser.add_argument("--delay", type=int, default=75,
                        help="Seconds to wait between calls (default 75).")
    args = parser.parse_args()

    print(f"Running {len(args.scenarios)} calls with a {args.delay}s gap.\n")
    for idx, sid in enumerate(args.scenarios, 1):
        scenario = get_scenario(sid)
        try:
            call_sid = place_call(scenario.id, scenario.label)
            print(f"[{idx}/{len(args.scenarios)}] {scenario.label} -> {call_sid}")
        except Exception as exc:  # keep going if one call fails
            print(f"[{idx}/{len(args.scenarios)}] {scenario.label} FAILED: {exc}")
        if idx < len(args.scenarios):
            time.sleep(args.delay)

    print("\nDone. Check ./recordings and ./transcripts.")


if __name__ == "__main__":
    main()

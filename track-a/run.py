"""Container entrypoint for Speed Demon Track A."""
import importlib
import os
import sys

MODULES = {"a": "a_ingest"}


def run():
    track = os.environ.get("TRACK", "a").strip().lower()
    if track not in MODULES:
        sys.stderr.write(f"TRACK must be one of {sorted(MODULES)}, got {track!r}\n")
        return 2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    importlib.import_module(MODULES[track]).main("/data", "/out")
    return 0


if __name__ == "__main__":
    sys.exit(run())

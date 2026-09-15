"""Content-free, per-loop progress for hcpy exec probes (no heartbeat thread)."""
import argparse
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time


class Health:
    def __init__(self, devices, path=None, budget=300):
        self.path = Path(path or os.environ.get("HCPY_HEALTH_FILE", "/tmp/hcpy-health.json"))
        self.budget = budget
        self.lock = threading.Lock()
        now = time.monotonic()
        self.state = {
            key: {"progress": now, "deadline": now + budget, "ready": False, "last_success": None}
            for key in ["mqtt"] + [f"device-{index}" for index in range(devices)]
        }
        self._write()

    def progress(self, component, success=None):
        with self.lock:
            entry = self.state[component]
            now = time.monotonic()
            entry.update(progress=now, deadline=now + self.budget)
            if success is not None:
                entry["ready"] = bool(success)
                if success:
                    entry["last_success"] = now
            self._write()

    def mqtt_log(self, _client, _userdata, _level, message):
        # This exact payload-free protocol event is emitted by pinned Paho1.6.1
        # from the receive loop. Never print/store other log messages or payloads.
        if message == "Received PINGRESP":
            self.progress("mqtt")

    def _write(self):
        fd, name = tempfile.mkstemp(prefix=".hcpy-health-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"version": 1, "components": self.state}, stream)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def check(path, mode, now=None):
    try:
        state = json.loads(Path(path).read_text())
        entries = state["components"]
        if state["version"] != 1 or "mqtt" not in entries or len(entries) < 2:
            return False
        now = time.monotonic() if now is None else now
        for entry in entries.values():
            start, end = entry["progress"], entry["deadline"]
            if not (math.isfinite(start) and math.isfinite(end) and start <= now <= end and end > start):
                return False
            if mode == "ready" and entry["ready"] is not True:
                return False
        return True
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("live", "ready"))
    parser.add_argument("path", nargs="?", default="/tmp/hcpy-health.json")
    args = parser.parse_args()
    return 0 if check(args.path, args.mode) else 1


if __name__ == "__main__":
    raise SystemExit(main())

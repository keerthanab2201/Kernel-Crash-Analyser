"""Separate cellular event timeline adapter; stage evidence is not a root cause."""
from __future__ import annotations
from datetime import datetime
import re
from pathlib import Path
from .privacy import Redactor

PATTERNS = [
    ("ng_setup_failed", r"NG Setup (?:Failure|failed)"),
    ("registration_rejected", r"Registration (?:Reject|rejected)|Initial Registration failed"),
    ("registration_accepted", r"Registration accept received|Initial Registration is successful"),
    ("session_rejected", r"PDU Session Establishment Reject"),
    ("session_accepted", r"PDU Session Establishment Accept|PDU Session Establishment is successful"),
    ("session_timeout", r"T3580.*expir|expir.*T3580"),
]
STAMP = re.compile(r"\[(\d{4}-\d\d-\d\d[ T]\d\d:\d\d:\d\d(?:\.\d+)?)\]")


def timeline(logs: dict[str, str]) -> dict:
    redactor = Redactor()
    events, ignored = [], 0
    for source, raw in logs.items():
        for line_id, line in enumerate(raw.splitlines(), 1):
            kind = next((name for name, pattern in PATTERNS if re.search(pattern, line, re.I)), None)
            if not kind:
                ignored += 1
                continue
            stamp = STAMP.search(line)
            try:
                timestamp = datetime.fromisoformat(stamp[1]).isoformat() if stamp else None
            except ValueError:
                timestamp = None
            events.append({"source": Path(source).name, "line_id": line_id, "event": kind,
                           "timestamp": timestamp, "evidence": redactor.redact(line)})
    events.sort(key=lambda event: (event["timestamp"] is None, event["timestamp"] or "", event["source"], event["line_id"]))
    failures = [e for e in events if e["event"] in ("ng_setup_failed", "registration_rejected", "session_rejected", "session_timeout")]
    return {"track": "cellular_event_timeline", "events": events, "observed_failure_events": failures,
            "unmatched_lines": ignored, "root_cause": None,
            "limits": "One UE/scenario per input bundle. Clock synchronization is assumed, not established. Untimestamped events sort last. Retries may recover; a failure event is not a final outcome or proven cause. Pattern adapter requires validation against the collected tool versions."}

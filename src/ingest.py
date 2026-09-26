"""Conservative regex-based parsing for x86 Linux oops and panic text."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable

from .models import ParsedCrash

_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("stack_overflow", re.compile(r"kernel stack overflow|stack guard page", re.I)),
    ("use_after_free", re.compile(r"KASAN:.*use-after-free|use-after-free", re.I)),
    (
        "null_pointer_deref",
        re.compile(r"null pointer dereference|unable to handle kernel NULL", re.I),
    ),
    (
        "deadlock",
        re.compile(
            r"possible circular locking dependency|hard LOCKUP|soft lockup", re.I
        ),
    ),
    ("panic_explicit", re.compile(r"Kernel panic - not syncing:", re.I)),
    ("general_protection_fault", re.compile(r"general protection fault", re.I)),
)
_IP_PATTERNS = (
    re.compile(r"^(?:RIP|EIP):\s*(?:\d+:)?\s*(.+)$", re.I),
    re.compile(r"^pc\s*:\s*(.+)$", re.I),
)
_FRAME = re.compile(
    r"^\s*(?:\[<[^>]+>\]\s*)?(?:\?\s*)?[A-Za-z_][\w.]*\+0x[0-9a-f]+/0x[0-9a-f]+",
    re.I,
)
_REGISTER = re.compile(
    r"^\s*(?:(?:R(?:AX|BX|CX|DX|SI|DI|BP|SP|8|9|10|11|12|13|14|15)|"
    r"E(?:AX|BX|CX|DX|SI|DI|BP|SP)|x\d+)[:=]\s*[0-9a-fx]+(?:\s+|$)){1,}",
    re.I,
)
_KEY = re.compile(
    r"BUG:|WARNING:|Kernel panic|Oops:|general protection fault|KASAN:|"
    r"unable to handle|Call Trace:|RIP:|EIP:|stack overflow|lockup",
    re.I,
)


def _strip_kernel_prefix(line: str) -> str:
    """Remove common dmesg timestamps/log-level prefixes without altering evidence."""
    line = re.sub(r"^\s*<\d+>", "", line)
    line = re.sub(r"^\s*\[\s*\d+(?:\.\d+)?\]\s*", "", line)
    return line.rstrip()


def _guess_type(text: str) -> str:
    # Specific sanitizer/signature matches are deliberately checked before the
    # generic panic trailer that commonly follows every fatal oops.
    for category, pattern in _TYPE_PATTERNS:
        if pattern.search(text):
            return category
    return "unknown_other"


def parse_log(
    text: str, *, crash_id: str | None = None, source_file: str = "<memory>"
) -> ParsedCrash:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("crash log is empty")
    normalized = "\n".join(_strip_kernel_prefix(line) for line in text.splitlines())
    if crash_id is None:
        crash_id = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    lines = normalized.splitlines()
    ip = None
    frames: list[str] = []
    registers: list[str] = []
    key_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if ip is None:
            for pattern in _IP_PATTERNS:
                match = pattern.match(stripped)
                if match:
                    ip = match.group(1).strip()
                    break
        if _FRAME.match(line):
            frames.append(stripped)
        if _REGISTER.match(line):
            registers.append(stripped)
        if _KEY.search(line):
            key_lines.append(stripped)
    return ParsedCrash(
        crash_id=crash_id,
        source_file=source_file,
        raw_log=normalized,
        crash_type_guess=_guess_type(normalized),
        faulting_instruction=ip,
        call_stack=frames,
        registers=registers,
        key_lines=key_lines,
    )


def ingest_files(paths: Iterable[Path]) -> list[ParsedCrash]:
    crashes: list[ParsedCrash] = []
    for path in sorted(paths):
        crashes.append(
            parse_log(
                path.read_text(encoding="utf-8", errors="replace"),
                crash_id=path.stem,
                source_file=str(path),
            )
        )
    return crashes


def ingest_directory(directory: Path) -> list[ParsedCrash]:
    return ingest_files(directory.glob("*.log"))


def write_parsed(crashes: Iterable[ParsedCrash], output: Path) -> None:
    output.write_text(
        json.dumps([crash.to_dict() for crash in crashes], indent=2) + "\n",
        encoding="utf-8",
    )

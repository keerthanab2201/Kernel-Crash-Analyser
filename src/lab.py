"""Create an isolated initramfs and capture a QEMU guest; never load host modules."""
from __future__ import annotations
import gzip
import hashlib
import json
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ACTIONS = {"panic": "PANIC", "null": "EXCEPTION", "overflow": "OVERFLOW", "uaf": "READ_AFTER_FREE"}


def _entry(name: str, data: bytes, mode: int, ino: int, rdevmajor=0, rdevminor=0) -> bytes:
    """SVR4 newc entry, fixed timestamps for deterministic archives."""
    encoded = name.encode() + b"\0"
    fields = [ino, mode, 0, 0, 1, 0, len(data), 0, 0, rdevmajor, rdevminor, len(encoded), 0]
    header = b"070701" + b"".join(f"{x:08x}".encode() for x in fields)
    result = header + encoded
    result += b"\0" * (-len(result) % 4)
    result += data + b"\0" * (-len(data) % 4)
    return result


def initramfs(busybox: Path, action: str, module: Path | None = None) -> bytes:
    if action not in (*ACTIONS, "module-uaf", "module-fixed"):
        raise ValueError("unknown fault action")
    if action.startswith("module-") and not module:
        raise ValueError("module action requires module path")
    trigger = f"echo {ACTIONS[action]} > /sys/kernel/debug/provoke-crash/DIRECT" if action in ACTIONS else f"/bin/busybox insmod /kca_demo.ko inject_uaf={int(action == 'module-uaf')}"
    script = f"""#!/bin/busybox sh
/bin/busybox mount -t proc proc /proc
/bin/busybox grep -q kca_lab=1 /proc/cmdline || exit 1
/bin/busybox mount -t sysfs sysfs /sys
/bin/busybox mount -t devtmpfs devtmpfs /dev
/bin/busybox mount -t debugfs debugfs /sys/kernel/debug
echo KCA_GUEST_READY
{trigger}
status=$?
echo KCA_TRIGGER_EXIT=$status
/bin/busybox poweroff -f
"""
    entries = []
    for name in ("bin", "dev", "proc", "sys"):
        entries.append(_entry(name, b"", stat.S_IFDIR | 0o755, len(entries) + 1))
    entries.append(_entry("dev/console", b"", stat.S_IFCHR | 0o600, 5, 5, 1))
    entries.append(_entry("bin/busybox", busybox.read_bytes(), stat.S_IFREG | 0o755, 6))
    entries.append(_entry("init", script.encode(), stat.S_IFREG | 0o755, 7))
    if module:
        entries.append(_entry("kca_demo.ko", module.read_bytes(), stat.S_IFREG | 0o644, 8))
    entries.append(_entry("TRAILER!!!", b"", 0, 9))
    return gzip.compress(b"".join(entries), mtime=0)


def capture(kernel: Path, config: Path, busybox: Path, output: Path, action: str, *, kernel_revision: str,
            module: Path | None = None, qemu="qemu-system-x86_64", timeout=90) -> dict:
    if timeout < 1:
        raise ValueError("timeout must be positive")
    for path in (kernel, config, busybox, *([module] if module else [])):
        if not path.is_file():
            raise ValueError(f"missing lab input: {path}")
    # Exclusive directory creation prevents an accidental overwrite of evidence.
    output.mkdir(parents=True, exist_ok=False)
    archive = output / "initramfs.cpio.gz"
    archive.write_bytes(initramfs(busybox, action, module))
    command = [qemu, "-accel", "tcg", "-m", "1024", "-smp", "1", "-nographic", "-no-reboot",
               "-nic", "none", "-monitor", "none", "-kernel", str(kernel.resolve()),
               "-initrd", str(archive.resolve()), "-append", "console=ttyS0 rdinit=/init panic=-1 oops=panic panic_on_warn=1 kca_lab=1"]
    hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in
              {"kernel": kernel, "config": config, "busybox": busybox, "initramfs": archive, **({"module": module} if module else {})}.items()}
    metadata = {"action": action, "kernel_revision": kernel_revision, "sha256": hashes,
                "started_utc": datetime.now(timezone.utc).isoformat(), "command": command,
                "ground_truth_status": "pending_review", "bug_family": f"{action}-v1"}
    with (output / "serial.log").open("wb") as stream:
        try:
            process = subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout, check=False)
            metadata["exit_code"] = process.returncode
            metadata["timed_out"] = False
        except subprocess.TimeoutExpired:
            metadata["timed_out"] = True
        except OSError as exc:
            metadata["launch_error"] = type(exc).__name__
    metadata["serial_sha256"] = hashlib.sha256((output / "serial.log").read_bytes()).hexdigest()
    (output / "manifest.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata

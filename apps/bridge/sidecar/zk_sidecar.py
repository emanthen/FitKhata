"""Thin pyzk wrapper, JSON-lines over stdio -- see src/devices/zkteco.ts for
the Node side of this protocol and the plan's reasoning for picking pyzk
over a pure-Node ZKTeco library.

One command per stdin line, one response per stdout line. Never buffers:
flush() after every write so the parent process's readline sees it
immediately.

Commands:
  {"cmd": "connect", "host": "...", "port": 4370}
  {"cmd": "poll_attendance", "since_offset": 0}      -> {"ok": true, "rows": [...], "next_offset": N}
  {"cmd": "set_user", "user_id": "...", "name": "..."}
  {"cmd": "delete_user", "user_id": "..."}
  {"cmd": "enable_user" | "disable_user", "user_id": "..."}
  {"cmd": "ping"}
Every response: {"ok": true, ...} or {"ok": false, "error": "..."}
"""

from __future__ import annotations

import json
import sys

try:
    from zk import ZK
except ImportError:  # pyzk not installed in this environment yet
    ZK = None  # type: ignore[assignment,misc]

_conn = None


def _reply(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def _connect(host: str, port: int) -> None:
    global _conn
    if ZK is None:
        raise RuntimeError("pyzk is not installed")
    zk = ZK(host, port=port, timeout=5, force_udp=False, ommit_ping=False)
    _conn = zk.connect()


def _require_conn():
    if _conn is None:
        raise RuntimeError("not connected -- send a 'connect' command first")
    return _conn


def _poll_attendance(since_offset: int) -> dict:
    conn = _require_conn()
    logs = conn.get_attendance() or []
    # pyzk returns the full on-device log each call (no native offset
    # support) -- the offset is this sidecar's own index into that list, so
    # the Node side only has to persist one integer, not raw log state.
    new_rows = logs[since_offset:]
    rows = [
        {
            "user_id": str(row.user_id),
            "timestamp": row.timestamp.isoformat(),
        }
        for row in new_rows
    ]
    return {"rows": rows, "next_offset": len(logs)}


def _set_user(user_id: str, name: str) -> None:
    conn = _require_conn()
    conn.set_user(user_id=user_id, name=name, privilege=0, user_id_str=user_id)


def _delete_user(user_id: str) -> None:
    conn = _require_conn()
    conn.delete_user(user_id=user_id)


def _set_enabled(user_id: str, enabled: bool) -> None:
    # pyzk has no per-user enable/disable primitive -- FR-3.8's "disable on
    # expiry/freeze so the device itself denies entry" is implemented as
    # delete+re-enroll: deleting the device-side user is sufficient to deny
    # entry (no card/finger match left to check against), and set_user
    # re-adds it when re-enabled. Re-enrolling loses the fingerprint
    # template on the device (the bridge doesn't have it to restore) --
    # acceptable for now, but the member will need to re-register their
    # fingerprint after an unfreeze. See the plan's ceiling note.
    if enabled:
        _set_user(user_id, name=user_id)
    else:
        try:
            _delete_user(user_id)
        except Exception:
            pass  # already absent is fine


def handle(command: dict) -> dict:
    cmd = command.get("cmd")
    if cmd == "connect":
        _connect(command["host"], int(command.get("port", 4370)))
        return {"ok": True}
    if cmd == "poll_attendance":
        return {"ok": True, **_poll_attendance(int(command.get("since_offset", 0)))}
    if cmd == "set_user":
        _set_user(command["user_id"], command["name"])
        return {"ok": True}
    if cmd == "delete_user":
        _delete_user(command["user_id"])
        return {"ok": True}
    if cmd in ("enable_user", "disable_user"):
        _set_enabled(command["user_id"], enabled=(cmd == "enable_user"))
        return {"ok": True}
    if cmd == "ping":
        return {"ok": True}
    return {"ok": False, "error": f"unknown command: {cmd}"}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            command = json.loads(line)
            result = handle(command)
        except Exception as exc:  # noqa: BLE001 -- must report, never crash the loop
            result = {"ok": False, "error": str(exc)}
        _reply(result)


if __name__ == "__main__":
    main()

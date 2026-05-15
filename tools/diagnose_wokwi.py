from __future__ import annotations

import socket
import sys
import time
from pathlib import Path
from typing import Protocol


class SerialLike(Protocol):
    @property
    def in_waiting(self) -> int: ...

    def read(self, size: int = 1) -> bytes: ...
    def write(self, data: bytes) -> int | None: ...
    def close(self) -> None: ...


def read_available(ser: SerialLike, timeout_s: float = 1.0) -> bytes:
    deadline = time.monotonic() + timeout_s
    chunks: list[bytes] = []

    while time.monotonic() < deadline:
        waiting = int(getattr(ser, "in_waiting", 0) or 0)
        data = ser.read(waiting or 1)
        if data:
            chunks.append(data)
        else:
            time.sleep(0.03)

    return b"".join(chunks)


def main() -> int:
    print("Python:", sys.version)
    print("Executable:", sys.executable)
    print("Project:", Path.cwd())

    try:
        import serial  # type: ignore[import-not-found]
        print("pyserial:", getattr(serial, "VERSION", "installed"))
    except ImportError:
        print("pyserial: NOT installed")
        print("Install with: python -m pip install pyserial==3.5")
        return 1

    try:
        with socket.create_connection(("localhost", 4000), timeout=3):
            print("TCP localhost:4000: OK")
    except OSError as exc:
        print("TCP localhost:4000: FAILED:", exc)
        print("Start Wokwi simulator and keep the simulator tab visible.")
        return 2

    try:
        with serial.serial_for_url("rfc2217://localhost:4000", baudrate=115200, timeout=0.2) as ser:
            time.sleep(0.4)
            ser.write(b"\x02\x03\x03\r\n")
            output = read_available(ser, timeout_s=2.0)
            print("RFC2217 serial open: OK")
            if output:
                print("Serial output preview:")
                print(output.decode(errors="replace")[-800:])
            else:
                print("Serial output preview: <empty>")
    except Exception as exc:
        print("RFC2217 serial open: FAILED:", exc)
        return 3

    print("Basic diagnostic OK. Run: python tools/upload_wokwi_micropython.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import base64
import re
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Protocol


class SerialLike(Protocol):
    timeout: float | None

    @property
    def in_waiting(self) -> int: ...

    def read(self, size: int = 1) -> bytes: ...
    def write(self, data: bytes) -> int | None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class FileMapping:
    local_path: str
    remote_path: str


PROJECT_FILES: tuple[FileMapping, ...] = (
    FileMapping("boot.py", "/boot.py"),
    FileMapping("config.py", "/config.py"),
    FileMapping("ssd1306.py", "/ssd1306.py"),
    FileMapping("umqtt/__init__.py", "/umqtt/__init__.py"),
    FileMapping("umqtt/simple.py", "/umqtt/simple.py"),
    FileMapping("main.py", "/main.py"),
)


class ReplError(RuntimeError):
    """Communication error with the MicroPython friendly REPL."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def validate_project_files(root: Path, mappings: Iterable[FileMapping]) -> None:
    missing = [mapping.local_path for mapping in mappings if not (root / mapping.local_path).exists()]
    if missing:
        raise FileNotFoundError("Missing project files: " + ", ".join(missing))


def wait_for_tcp_port(host: str, port: int, retries: int, delay_s: float) -> bool:
    for attempt in range(1, retries + 1):
        try:
            with socket.create_connection((host, port), timeout=2.0):
                print(f"Simulator found at {host}:{port} (attempt {attempt}).")
                return True
        except OSError:
            print(f"Waiting for Wokwi RFC2217 at {host}:{port} ({attempt}/{retries})...")
            time.sleep(delay_s)
    return False


def import_pyserial():
    try:
        import serial  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Missing dependency: pyserial. Run: python -m pip install pyserial==3.5") from exc
    return serial


def serial_write(ser: SerialLike, data: bytes, *, chunk_delay_s: float = 0.0) -> None:
    """Write bytes without relying on write_timeout.

    pyserial's RFC2217 backend does not support write_timeout. Passing that
    option raises: "write_timeout is currently not supported".
    """
    written = ser.write(data)
    if written is not None and written != len(data):
        raise ReplError(f"Short serial write: {written}/{len(data)} bytes")
    try:
        ser.flush()
    except Exception:
        # Some RFC2217 implementations make flush a no-op or partial feature.
        pass
    if chunk_delay_s > 0:
        time.sleep(chunk_delay_s)


def read_available(ser: SerialLike, timeout_s: float = 0.5) -> bytes:
    deadline = time.monotonic() + timeout_s
    chunks: list[bytes] = []

    while time.monotonic() < deadline:
        try:
            waiting = int(getattr(ser, "in_waiting", 0) or 0)
        except Exception:
            waiting = 0

        if waiting > 0:
            chunks.append(ser.read(waiting))
            # Drain short bursts without extending the read too much.
            deadline = max(deadline, time.monotonic() + 0.05)
        else:
            # A one-byte read with a short serial timeout catches data that
            # arrives just after in_waiting is checked.
            chunk = ser.read(1)
            if chunk:
                chunks.append(chunk)
                deadline = max(deadline, time.monotonic() + 0.05)
            else:
                time.sleep(0.02)

    return b"".join(chunks)


def read_until_any(ser: SerialLike, needles: tuple[bytes, ...], timeout_s: float) -> bytes:
    deadline = time.monotonic() + timeout_s
    buffer = bytearray()

    while time.monotonic() < deadline:
        try:
            waiting = int(getattr(ser, "in_waiting", 0) or 0)
        except Exception:
            waiting = 0

        chunk = ser.read(waiting or 1)
        if chunk:
            buffer.extend(chunk)
            if any(needle in buffer for needle in needles):
                return bytes(buffer)
        else:
            time.sleep(0.02)

    expected = " or ".join(repr(needle.decode(errors="replace")) for needle in needles)
    tail = bytes(buffer[-1200:]).decode(errors="replace")
    raise ReplError(f"Timeout waiting for {expected}. Last received output:\n{tail}")


def wait_for_prompt(ser: SerialLike, timeout_s: float = 8.0) -> bytes:
    return read_until_any(ser, (b">>> ", b">>>"), timeout_s)


def force_friendly_prompt(ser: SerialLike) -> bytes:
    """Interrupt running code and reach the friendly REPL prompt.

    This handles:
    - main.py running in an infinite loop;
    - an already idle friendly REPL;
    - raw REPL left open by a previous mpremote attempt.
    """
    collected = bytearray()

    for _ in range(8):
        serial_write(ser, b"\x02", chunk_delay_s=0.03)      # Ctrl+B: leave raw REPL.
        serial_write(ser, b"\x03\x03", chunk_delay_s=0.03)  # Ctrl+C twice: interrupt program.
        serial_write(ser, b"\r\n", chunk_delay_s=0.10)
        collected.extend(read_available(ser, timeout_s=0.45))

        if b">>> " in collected or collected.rstrip().endswith(b">>>"):
            return bytes(collected)

    serial_write(ser, b"\x02\x03\r\n", chunk_delay_s=0.05)
    collected.extend(wait_for_prompt(ser, timeout_s=12.0))
    return bytes(collected)


def exec_paste(
    ser: SerialLike,
    code: str,
    *,
    timeout_s: float = 10.0,
    write_chunk_size: int = 128,
    write_delay_s: float = 0.006,
) -> bytes:
    """Execute code in MicroPython paste mode."""
    if "\x04" in code:
        raise ValueError("Code sent to paste mode cannot contain Ctrl+D")

    serial_write(ser, b"\x05", chunk_delay_s=0.05)  # Ctrl+E: paste mode.
    read_until_any(ser, (b"paste mode", b"==="), timeout_s=4.0)

    payload = code.replace("\n", "\r\n").encode("utf-8")
    for start in range(0, len(payload), write_chunk_size):
        serial_write(
            ser,
            payload[start : start + write_chunk_size],
            chunk_delay_s=write_delay_s,
        )

    serial_write(ser, b"\x04", chunk_delay_s=0.05)  # Ctrl+D: execute pasted block.
    output = wait_for_prompt(ser, timeout_s=timeout_s)
    text = output.decode(errors="replace")
    if "Traceback (most recent call last)" in text:
        raise ReplError("MicroPython error while executing pasted code:\n" + text)
    return output


def exec_line(ser: SerialLike, code: str, *, timeout_s: float = 10.0) -> bytes:
    """Execute code through a single friendly-REPL line: exec('...').

    This is slower than paste mode, but it is a useful fallback when Ctrl+E is
    not handled by the terminal/REPL path.
    """
    line = "exec({!r})\r\n".format(code)
    serial_write(ser, line.encode("utf-8"), chunk_delay_s=0.03)
    output = wait_for_prompt(ser, timeout_s=timeout_s)
    text = output.decode(errors="replace")
    if "Traceback (most recent call last)" in text:
        raise ReplError("MicroPython error while executing exec(...) line:\n" + text)
    return output


class FriendlyRepl:
    def __init__(
        self,
        ser: SerialLike,
        method: Literal["auto", "paste", "exec"],
        line_fallback: bool,
        paste_chunk_size: int,
        write_delay_s: float,
    ) -> None:
        self.ser = ser
        self.method = method
        self.line_fallback = line_fallback
        self.paste_chunk_size = paste_chunk_size
        self.write_delay_s = write_delay_s
        self._selected: Literal["paste", "exec"] | None = None

    @property
    def selected(self) -> str:
        return self._selected or self.method

    def execute(self, code: str, *, timeout_s: float = 10.0) -> bytes:
        match self._selected or self.method:
            case "paste":
                return exec_paste(
                    self.ser,
                    code,
                    timeout_s=timeout_s,
                    write_chunk_size=self.paste_chunk_size,
                    write_delay_s=self.write_delay_s,
                )
            case "exec":
                return exec_line(self.ser, code, timeout_s=timeout_s)
            case "auto":
                return self._execute_auto(code, timeout_s=timeout_s)
            case other:
                raise ValueError(f"Invalid execution method: {other}")

    def _execute_auto(self, code: str, *, timeout_s: float) -> bytes:
        if self._selected == "exec":
            return exec_line(self.ser, code, timeout_s=timeout_s)

        try:
            output = exec_paste(
                self.ser,
                code,
                timeout_s=timeout_s,
                write_chunk_size=self.paste_chunk_size,
                write_delay_s=self.write_delay_s,
            )
            self._selected = "paste"
            return output
        except Exception as paste_exc:
            if not self.line_fallback:
                raise

            print("Paste mode did not answer; using exec(...) fallback.")
            force_friendly_prompt(self.ser)
            output = exec_line(self.ser, code, timeout_s=timeout_s)
            self._selected = "exec"
            print(f"Fallback active. Original paste error: {paste_exc}")
            return output


def ensure_remote_dirs(repl: FriendlyRepl) -> None:
    code = """
import os
for directory in ('/umqtt',):
    try:
        os.mkdir(directory)
        print('DIR', directory)
    except OSError:
        pass
"""
    repl.execute(code, timeout_s=10.0)


def write_remote_file(repl: FriendlyRepl, local_file: Path, remote_path: str, chunk_size: int) -> None:
    data = local_file.read_bytes()

    truncate_code = f"f = open({remote_path!r}, 'wb')\nf.close()\nprint('TRUNC {remote_path}')"
    repl.execute(truncate_code, timeout_s=10.0)

    total_chunks = (len(data) + chunk_size - 1) // chunk_size
    for index, start in enumerate(range(0, len(data), chunk_size), start=1):
        chunk = data[start : start + chunk_size]
        encoded = base64.b64encode(chunk).decode("ascii")
        code = (
            "try:\n"
            "    import ubinascii as binascii\n"
            "except ImportError:\n"
            "    import binascii\n"
            f"f = open({remote_path!r}, 'ab')\n"
            f"f.write(binascii.a2b_base64(b'{encoded}'))\n"
            "f.close()\n"
            f"print('WRITE {remote_path} {index}/{total_chunks}')"
        )
        repl.execute(code, timeout_s=20.0)

    stat_code = (
        "import os\n"
        f"size = os.stat({remote_path!r})[6]\n"
        f"print('__SIZE__ {remote_path} %d __END__' % size)"
    )
    output = repl.execute(stat_code, timeout_s=10.0).decode(errors="replace")
    match = re.search(r"__SIZE__\s+\S+\s+(\d+)\s+__END__", output)
    if match is None:
        raise ReplError(f"Could not verify size for {remote_path}. Output:\n{output}")

    remote_size = int(match.group(1))
    if remote_size != len(data):
        raise ReplError(
            f"Size mismatch after upload of {remote_path}. "
            f"Expected {len(data)} bytes, got {remote_size} bytes. Output:\n{output}"
        )

    print(f"OK  {local_file.relative_to(project_root())} -> {remote_path} ({len(data)} bytes)")


def list_remote_files(repl: FriendlyRepl) -> None:
    code = """
import os

def show(path):
    try:
        print(path, os.listdir(path))
    except OSError as exc:
        print(path, exc)

show('/')
show('/umqtt')
"""
    output = repl.execute(code, timeout_s=10.0).decode(errors="replace")
    print(output)


def soft_reset(ser: SerialLike) -> None:
    print("Resetting MicroPython to run main.py...")
    serial_write(ser, b"\x04", chunk_delay_s=0.20)  # Ctrl+D at prompt: soft reset.
    output = read_available(ser, timeout_s=3.0).decode(errors="replace")
    if output.strip():
        print(output)


def open_serial(host: str, port: int) -> SerialLike:
    serial = import_pyserial()
    url = f"rfc2217://{host}:{port}"

    # Important: do not pass write_timeout here. pyserial's RFC2217 client
    # raises NotImplementedError("write_timeout is currently not supported").
    return serial.serial_for_url(
        url,
        baudrate=115200,
        timeout=0.15,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Upload MicroPython files to Wokwi VS Code through friendly REPL/RFC2217. "
            "This avoids mpremote raw-REPL failures."
        )
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=4000)
    parser.add_argument("--retries", type=int, default=20)
    parser.add_argument("--delay", type=float, default=2.0)
    parser.add_argument("--chunk-size", type=int, default=384)
    parser.add_argument("--paste-chunk-size", type=int, default=128)
    parser.add_argument("--write-delay-ms", type=float, default=6.0)
    parser.add_argument(
        "--method",
        choices=("auto", "paste", "exec"),
        default="auto",
        help="REPL execution method. Use 'exec' only if paste mode keeps failing.",
    )
    parser.add_argument("--no-line-fallback", action="store_true")
    parser.add_argument("--no-reset", action="store_true", help="Upload files, but do not reset the ESP32.")
    parser.add_argument("--list-only", action="store_true", help="Only list remote files and exit.")
    parser.add_argument("--skip-port-check", action="store_true", help="Connect directly without the TCP pre-check.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = project_root()

    try:
        validate_project_files(root, PROJECT_FILES)

        if not args.skip_port_check:
            if not wait_for_tcp_port(args.host, args.port, args.retries, args.delay):
                print(f"\nERROR: Wokwi did not answer at {args.host}:{args.port}.")
                print("Open VS Code, run 'Wokwi: Start Simulator', and keep the simulator tab visible.")
                return 1

        print("Connecting to MicroPython friendly REPL through pyserial/RFC2217...")
        with open_serial(args.host, args.port) as ser:
            # Give the RFC2217 negotiation a moment and drain any banner/prompt.
            time.sleep(0.35)
            banner = read_available(ser, timeout_s=0.8).decode(errors="replace")
            if banner.strip():
                print(banner)

            force_friendly_prompt(ser)
            print("REPL ready.")

            repl = FriendlyRepl(
                ser=ser,
                method=args.method,
                line_fallback=not args.no_line_fallback,
                paste_chunk_size=args.paste_chunk_size,
                write_delay_s=args.write_delay_ms / 1000.0,
            )

            # Small probe selects paste or exec before the real upload.
            probe = repl.execute("print('__UPLOAD_PROBE_OK__')", timeout_s=8.0).decode(errors="replace")
            if "__UPLOAD_PROBE_OK__" not in probe:
                raise ReplError("REPL probe did not return expected marker. Output:\n" + probe)
            print(f"Execution method: {repl.selected}")

            if args.list_only:
                list_remote_files(repl)
                return 0

            ensure_remote_dirs(repl)
            print("Uploading project files...\n")

            for mapping in PROJECT_FILES:
                write_remote_file(
                    repl=repl,
                    local_file=root / mapping.local_path,
                    remote_path=mapping.remote_path,
                    chunk_size=args.chunk_size,
                )

            print("\nFiles currently stored in MicroPython:")
            list_remote_files(repl)

            if not args.no_reset:
                soft_reset(ser)
            else:
                print("Upload finished without reset. Press Ctrl+D in the REPL to run main.py.")

        print("\nUpload finished.")
        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user.")
        return 130
    except Exception as exc:
        print("\nERROR:", exc)
        print("\nRecommended actions:")
        print("1. Keep the Wokwi simulator tab visible in VS Code.")
        print("2. Stop and start the simulator again: Wokwi: Stop Simulator / Start Simulator.")
        print("3. Confirm dependencies: python -m pip install -r requirements-dev.txt")
        print("4. Confirm wokwi.toml contains: rfc2217ServerPort = 4000")
        print("5. Retry with slower upload: python tools/upload_wokwi_micropython.py --method exec --chunk-size 192")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

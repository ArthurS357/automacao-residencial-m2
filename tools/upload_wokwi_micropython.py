from __future__ import annotations

# Compatibility entry point for:
#   python tools/upload_wokwi_micropython.py
#
# The implementation uses tools/upload_serial_repl.py.
# It avoids:
#   - mpremote raw-REPL errors: "could not enter raw repl"
#   - pyserial RFC2217 write_timeout error: "write_timeout is currently not supported"

from upload_serial_repl import main


if __name__ == "__main__":
    raise SystemExit(main())

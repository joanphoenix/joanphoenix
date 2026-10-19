#!/usr/bin/env python3
"""Native macOS entry point. Run --help for explicit diagnostic/task commands."""
from macos_port.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

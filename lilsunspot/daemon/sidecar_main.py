from __future__ import annotations

import os
import sys


_stdio_handles = []


def _ensure_windowed_stdio() -> None:
    for name, mode in (("stdin", "r"), ("stdout", "w"), ("stderr", "w")):
        if getattr(sys, name) is not None:
            continue
        handle = open(os.devnull, mode, encoding="utf-8")
        _stdio_handles.append(handle)
        setattr(sys, name, handle)


_ensure_windowed_stdio()

from lilsunspot.daemon.launcher import main


if __name__ == "__main__":
    raise SystemExit(main())

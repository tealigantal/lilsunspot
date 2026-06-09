from __future__ import annotations

import importlib
import sys


def test_sidecar_main_provides_stdio_for_windowed_pyinstaller(monkeypatch):
    import lilsunspot.daemon.sidecar_main as sidecar_main

    monkeypatch.setattr(sys, "stdin", None)
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)

    importlib.reload(sidecar_main)

    assert sys.stdin is not None
    assert sys.stdout is not None
    assert sys.stderr is not None

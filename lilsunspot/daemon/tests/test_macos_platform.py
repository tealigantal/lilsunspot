from __future__ import annotations

from pathlib import Path


def test_macos_default_data_dir_uses_application_support(monkeypatch, tmp_path):
    import lilsunspot.daemon.config_paths as config_paths

    monkeypatch.delenv("LILSUNSPOT_DATA_DIR", raising=False)
    monkeypatch.setattr(config_paths.sys, "platform", "darwin")
    monkeypatch.setattr(config_paths.Path, "home", classmethod(lambda cls: tmp_path))

    assert config_paths.get_data_dir() == tmp_path / "Library" / "Application Support" / "Lilsunspot" / "data"


def test_data_dir_override_has_priority_on_macos(monkeypatch, tmp_path):
    import lilsunspot.daemon.config_paths as config_paths

    override = tmp_path / "override"
    monkeypatch.setattr(config_paths.sys, "platform", "darwin")
    monkeypatch.setenv("LILSUNSPOT_DATA_DIR", str(override))

    assert config_paths.get_data_dir() == override.resolve()


def test_macos_onedir_diagnostic_uses_macos_process_name(monkeypatch, tmp_path):
    import lilsunspot.daemon.runtime_discovery as runtime_discovery

    executable = tmp_path / "lilsunspotd" / "lilsunspotd"
    executable.parent.mkdir()
    monkeypatch.setattr(runtime_discovery.sys, "platform", "darwin")
    monkeypatch.setattr(runtime_discovery.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_discovery.sys, "_MEIPASS", str(executable.parent), raising=False)
    monkeypatch.setattr(runtime_discovery.sys, "executable", str(executable))

    metadata = runtime_discovery.process_metadata()

    assert metadata["process_model"] == "pyinstaller_onedir_single_process"
    assert "lilsunspotd 服务进程" in metadata["note_cn"]
    assert "lilsunspotd.exe" not in metadata["note_cn"]

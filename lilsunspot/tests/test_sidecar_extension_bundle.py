from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "build_lilsunspotd_sidecar.ps1"


def test_windows_sidecar_collects_dynamic_hermes_extension_code_and_assets():
    text = SCRIPT.read_text(encoding="utf-8")
    required_fragments = [
        '"--collect-submodules", "gateway"',
        '"--collect-submodules", "plugins"',
        '"--extra", "messaging"',
        '"--add-data", "$PluginSource;plugins"',
        '"--add-data", "$SkillsSource;skills"',
        '"--add-data", "$OptionalSkillsSource;optional-skills"',
        '"--add-data", "$OptionalMcpsSource;optional-mcps"',
    ]
    for fragment in required_fragments:
        assert fragment in text

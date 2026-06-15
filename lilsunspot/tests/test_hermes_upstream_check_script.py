from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "hermes_upstream_check.ps1"


def test_hermes_upstream_check_script_exists():
    assert SCRIPT.exists()


def test_hermes_upstream_check_is_read_only_by_default():
    text = SCRIPT.read_text(encoding="utf-8")

    assert "[switch] $Fetch" in text
    assert 'if ($Fetch) {' in text
    assert 'Invoke-Git @("fetch", $Remote, $Branch)' in text
    assert 'Invoke-Git @("merge"' not in text
    assert "cherry-pick" not in text
    assert "checkout -b" not in text
    assert "New-Item -ItemType Directory -Force -Path $ReportDir" in text


def test_hermes_upstream_check_uses_product_upstream_metadata_and_reports():
    text = SCRIPT.read_text(encoding="utf-8")

    required_fragments = [
        'Join-Path $Root "lilsunspot\\UPSTREAM_COMMIT.txt"',
        'Join-Path $Root "lilsunspot\\notes\\upstream-sync-reports"',
        'Working tree dirty',
        'Change categories',
        'Required validation after a real sync',
        'Get-ChangeCategory',
        'lilsunspot product',
        'Messaging gateway',
        'Dashboard/TUI',
        'Packaging/deps',
        'Capability surface gaps',
        'lilsunspot.daemon.upstream_audit',
        'Missing TOOLSETS in current worktree',
        'Missing CONFIGURABLE_TOOLSETS in current worktree',
        'Missing DEFAULT_CONFIG keys in current worktree',
    ]

    for fragment in required_fragments:
        assert fragment in text

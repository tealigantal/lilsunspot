from lilsunspot.daemon.logging_utils import mask_secret, redact_text


def test_mask_secret_does_not_leak_full_value():
    secret = "test-key-redacted-1234567890"
    masked = mask_secret(secret)

    assert masked != secret
    assert secret not in masked
    assert masked.startswith("tes...")
    assert masked.endswith("7890")


def test_redact_text_redacts_token_and_env_assignment():
    token = "s" + "k-" + "example-redacted-1234567890"
    env_name = "OPENAI" + "_API_KEY"
    text = f"token={token} {env_name}=test-key-redacted-openai"

    redacted = redact_text(text)

    assert token not in redacted
    assert "test-key-redacted-openai" not in redacted
    assert "..." in redacted

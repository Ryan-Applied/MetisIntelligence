from redaction import Redactor, redact, scan, shannon_entropy


def _cats(text):
    return {f.category for f in scan(text)}


def test_aws_access_key_detected_and_redacted():
    text = "aws key AKIAIOSFODNN7EXAMPLE in config"
    res = redact(text)
    assert "aws_access_key_id" in {f.category for f in res.findings}
    assert "AKIAIOSFODNN7EXAMPLE" not in res.text
    assert "[REDACTED:aws_access_key_id]" in res.text


def test_private_key_block_redacted():
    text = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEpAIBAAKCAQEA3x4example\n"
        "-----END RSA PRIVATE KEY-----"
    )
    res = redact(text)
    assert "private_key" in {f.category for f in res.findings}
    assert "MIIEpAIBAAKCAQEA3x4example" not in res.text


def test_github_token_and_jwt():
    gh = "ghp_" + "a" * 36
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.abcDEF123_-"
    assert "github_token" in _cats(f"token {gh}")
    assert "jwt" in _cats(f"auth {jwt}")


def test_url_credentials_only_password_redacted():
    text = "db at postgres://admin:supersecretpw@db.internal:5432/app"
    res = redact(text)
    assert "supersecretpw" not in res.text
    assert "admin" in res.text  # username preserved
    assert "url_credentials" in {f.category for f in res.findings}


def test_assigned_secret_keeps_key_name():
    text = 'password = "hunter2hunter2"'
    res = redact(text)
    assert "hunter2hunter2" not in res.text
    assert "password" in res.text  # the label stays
    assert "[REDACTED:assigned_secret]" in res.text


def test_email_redaction_default_on_and_toggle_off():
    text = "contact ryan@appliedcomputing.com please"
    assert "email" in {f.category for f in redact(text).findings}
    off = Redactor(redact_emails=False)
    assert off.redact(text).clean is True


def test_clean_text_is_clean():
    res = redact("just a normal sentence with no secrets")
    assert res.clean is True
    assert res.text == "just a normal sentence with no secrets"


def test_findings_never_contain_the_secret():
    gh = "ghp_" + "b" * 36
    for f in scan(f"here {gh}"):
        # fingerprint is a short sha256 prefix, not the raw value
        assert gh not in f.fingerprint
        assert len(f.fingerprint) == 12


def test_redacted_output_has_no_remaining_findings():
    text = "AKIAIOSFODNN7EXAMPLE and ghp_" + "c" * 36 + " and x@y.com"
    res = redact(text)
    # second pass over the redacted text should find nothing
    assert redact(res.text).clean is True


def test_entropy_scan_is_opt_in():
    token = "Zx9Kq2Lm8Pw4Rt6Vy1Nb3Hc7Df5Gk0"  # high-entropy, unknown format
    assert redact(token).clean is True  # default: no entropy scan
    hi = Redactor(entropy_scan=True, entropy_threshold=3.5)
    assert not hi.redact(token).clean


def test_shannon_entropy_monotonic():
    assert shannon_entropy("aaaaaaaa") < shannon_entropy("ab12Cd34")

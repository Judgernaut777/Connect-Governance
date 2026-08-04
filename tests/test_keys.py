"""Issuer key custody: file-based, strict permissions, CLI-generated (OD-008)."""

from __future__ import annotations

import os
import stat

import pytest

from connect_governance.keys import generate_key, main, show_public_pem
from connect_governance_grants import public_key_id


def test_generate_writes_key_with_owner_only_permissions(tmp_path) -> None:
    path = str(tmp_path / "issuer.pem")
    key_id = generate_key(path)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    assert mode == 0o600, f"issuer key must be owner-only, got {oct(mode)}"
    assert key_id.startswith("ed25519:")


def test_generate_refuses_to_overwrite(tmp_path) -> None:
    """Replacing an issuer key orphans every grant it signed; make it deliberate."""
    path = str(tmp_path / "issuer.pem")
    generate_key(path)
    with pytest.raises(FileExistsError):
        generate_key(path)


def test_generated_key_signs_and_verifies(tmp_path) -> None:
    """The custody path produces keys the signing path actually accepts."""
    from connect_governance_grants import GrantPayload, sign_grant, verify_grant

    path = str(tmp_path / "issuer.pem")
    key_id = generate_key(path)
    pub = show_public_pem(path)
    assert public_key_id(pub) == key_id

    with open(path) as f:
        priv = f.read()
    payload = GrantPayload(
        grant_format_version="1",
        grant_id="g-1",
        decision_record_id="dr-1",
        work_request_id="wr-1",
        work_request_revision=None,
        requesting_principal_id="agent-1",
        organization_id="org-1",
        workspace_id="ws-1",
        provider_id="toolconnect",
        permitted_operations=("tool.invoke",),
        policy_versions=(),
        kernel_version="0.0.1",
        not_before=None,
        not_after=None,
        issued_at="2026-08-03T12:00:00Z",
        issuer_key_id=key_id,
        correlation_id=None,
    )
    grant = sign_grant(payload, priv)
    assert verify_grant(grant, pub, at="2026-08-03T12:00:00Z").valid


def test_cli_generate_and_show_public(tmp_path, capsys) -> None:
    path = str(tmp_path / "issuer.pem")
    assert main(["generate", "--out", path]) == 0
    assert main(["show-public", "--key", path]) == 0
    out = capsys.readouterr().out
    assert "BEGIN PUBLIC KEY" in out
    assert "ed25519:" in out


def test_show_public_rejects_non_ed25519(tmp_path) -> None:
    path = tmp_path / "not-a-key.pem"
    path.write_text("-----BEGIN PRIVATE KEY-----\nbogus\n-----END PRIVATE KEY-----\n")
    with pytest.raises(Exception):
        show_public_pem(str(path))

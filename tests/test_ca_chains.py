"""Reject every disclosed TLS chain, including alternate cross-sign paths."""

import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import certifi
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.verification import PolicyBuilder, Store, VerificationError

from shared.security import browser
from shared.security.ca import DISTRUSTED_ROOTS, filtered_ca_bundle

FIXTURES = Path(__file__).parent / "fixtures" / "ca_incident"


@pytest.mark.parametrize(
    "chain_file", sorted(FIXTURES.glob("*emudhra*.pem")), ids=lambda p: p.stem
)
def test_disclosed_chain_has_valid_control_and_is_rejected(chain_file):
    chain = x509.load_pem_x509_certificates(chain_file.read_bytes())
    builder = PolicyBuilder().time(datetime(2026, 10, 22, tzinfo=timezone.utc))
    unsafe_roots = x509.load_pem_x509_certificates(
        (FIXTURES / "roots.pem").read_bytes()
    )
    assert {
        cert.fingerprint(hashes.SHA256()).hex() for cert in unsafe_roots
    } == DISTRUSTED_ROOTS
    control = builder.store(Store(unsafe_roots)).build_server_verifier(
        x509.DNSName(chain_file.stem)
    )
    assert control.verify(chain[0], chain[1:])

    clean_roots = x509.load_pem_x509_certificates(Path(certifi.where()).read_bytes())
    clean = builder.store(Store(clean_roots)).build_server_verifier(
        x509.DNSName(chain_file.stem)
    )
    with pytest.raises(VerificationError):
        clean.verify(chain[0], chain[1:])


def test_filter_removes_all_incident_roots_and_preserves_clean_roots():
    clean = Path(certifi.where()).read_text(encoding="ascii")
    unsafe = (FIXTURES / "roots.pem").read_text(encoding="ascii")
    assert filtered_ca_bundle(clean + unsafe) == filtered_ca_bundle(clean)
    with pytest.raises(Exception, match="No trusted certificates"):
        filtered_ca_bundle(unsafe)


def test_chromium_database_distrust_covers_all_published_intermediate_keys(tmp_path):
    data = Path(browser.__file__).with_name("emudhra_intermediates.pem").read_bytes()
    assert (
        hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()
        == "c6bef0a3d76e4065f63e3bb83932f28a02bc8bc69a6a27a7481310cbb7be393e"
    )
    browser._seed_profile(tmp_path)
    with closing(sqlite3.connect(tmp_path / "Default" / "ServerCertificate")) as db:
        denied = [
            x509.load_der_x509_certificate(row[0])
            for row in db.execute(
                "SELECT der_cert FROM certificates WHERE trust_settings = ?",
                (b"\x0a\x02\x08\x02",),
            )
        ]

    def spki(cert):
        return cert.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    denied_keys = {spki(cert) for cert in denied}
    assert len(denied_keys) == 9  # Eight disclosed keys plus the negative canary.
    for file in FIXTURES.glob("*emudhra*.pem"):
        chain = x509.load_pem_x509_certificates(file.read_bytes())
        assert spki(chain[1]) in denied_keys

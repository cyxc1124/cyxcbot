"""Reject every disclosed TLS chain, including alternate cross-sign paths."""

import hashlib
import json
import sqlite3
import ssl
import subprocess
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import certifi
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.x509.verification import PolicyBuilder, Store, VerificationError

from shared.security import browser
from shared.security.ca import (
    DISTRUSTED_KEYS,
    DISTRUSTED_ROOTS,
    _key_fingerprint,
    check_trust_store,
    filtered_ca_bundle,
)

FIXTURES = Path(__file__).parent / "fixtures" / "ca_incident"


def _tlv(tag, value):
    length = len(value)
    size = length.to_bytes((length.bit_length() + 7) // 8, "big")
    header = bytes([length]) if length < 128 else bytes([0x80 | len(size)]) + size
    return bytes([tag]) + header + value


def _contents(value):
    return value[2 + (value[1] & 0x7F if value[1] & 0x80 else 0) :]


def _replace_spki(cert, spki):
    original = cert.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    tbs = _tlv(0x30, _contents(cert.tbs_certificate_bytes).replace(original, spki))
    return _tlv(
        0x30,
        _contents(cert.public_bytes(serialization.Encoding.DER)).replace(
            cert.tbs_certificate_bytes, tbs
        ),
    )


def _ec_key_pem(cert, encoding):
    key = cert.public_key()
    point = key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.CompressedPoint
    )
    bits = _tlv(0x03, b"\x00" + point)
    if encoding == "constructed":
        bits = _tlv(0x23, bits)
    elif encoding == "unused_bits":
        assert point[-1] & 1 == 0
        bits = _tlv(0x03, b"\x01" + point[:-1] + bytes([point[-1] | 1]))
    original = key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    uncompressed = key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    algorithm = _contents(original).removesuffix(_tlv(0x03, b"\x00" + uncompressed))
    return ssl.DER_cert_to_PEM_cert(_replace_spki(cert, _tlv(0x30, algorithm + bits)))


@pytest.mark.parametrize("encoding", ["compressed", "constructed", "unused_bits"])
def test_incident_ec_key_encodings_cannot_bypass_filter(encoding):
    cert = x509.load_pem_x509_certificates((FIXTURES / "roots.pem").read_bytes())[0]
    pem = _ec_key_pem(cert, encoding)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=pem)
    with pytest.raises(ssl.SSLError):
        check_trust_store(context)
    with pytest.raises(ssl.SSLError):
        filtered_ca_bundle(pem)


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


@pytest.mark.parametrize("representation", ["trailing", "ber", "signature", "reissued"])
def test_filter_rejects_equivalent_incident_trust_anchors(representation):
    variants = []
    for cert in x509.load_pem_x509_certificates((FIXTURES / "roots.pem").read_bytes()):
        der = cert.public_bytes(serialization.Encoding.DER)
        if representation == "trailing":
            der += b"\x00trailing data"
        elif representation == "ber":
            assert der[1] == 0x82
            der = der[:1] + b"\x83\x00" + der[2:]
        elif representation == "signature":
            der = der[:-1] + bytes([der[-1] ^ 1])
        else:
            replacement = (
                x509.CertificateBuilder()
                .subject_name(cert.subject)
                .issuer_name(cert.issuer)
                .public_key(cert.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(cert.not_valid_before_utc)
                .not_valid_after(cert.not_valid_after_utc)
                .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
                .add_extension(
                    x509.KeyUsage(
                        True, False, False, False, False, True, True, None, None
                    ),
                    True,
                )
                .add_extension(
                    x509.SubjectKeyIdentifier.from_public_key(cert.public_key()), False
                )
                .sign(ec.generate_private_key(ec.SECP384R1()), hashes.SHA384())
            )
            der = replacement.public_bytes(serialization.Encoding.DER)
        pem = ssl.DER_cert_to_PEM_cert(der)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=pem)
        with pytest.raises(ssl.SSLError, match="distrusted"):
            check_trust_store(context)
        variants.append(pem)

    clean = Path(certifi.where()).read_text(encoding="ascii")
    assert filtered_ca_bundle(clean + "\n".join(variants)) == filtered_ca_bundle(clean)
    with pytest.raises(ssl.SSLError, match="No trusted certificates"):
        filtered_ca_bundle("\n".join(variants))
    if representation in ("signature", "reissued"):
        unsafe = (
            PolicyBuilder()
            .time(datetime(2026, 10, 22, tzinfo=timezone.utc))
            .store(Store(x509.load_pem_x509_certificates("\n".join(variants).encode())))
        )
        for file in FIXTURES.glob("*emudhra*.pem"):
            chain = x509.load_pem_x509_certificates(file.read_bytes())
            assert unsafe.build_server_verifier(x509.DNSName(file.stem)).verify(
                chain[0], chain[1:]
            )


@pytest.mark.parametrize("compressed", [False, True])
def test_filter_preserves_explicit_private_leaf_anchor(compressed):
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "private leaf")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(datetime(2026, 1, 1, tzinfo=timezone.utc))
        .not_valid_after(datetime(2027, 1, 1, tzinfo=timezone.utc))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), True)
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM).decode("ascii")
    if compressed:
        pem = _ec_key_pem(cert, "compressed")
    assert filtered_ca_bundle(pem) == pem
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cadata=filtered_ca_bundle(pem))
    assert context.cert_store_stats() == {"x509": 1, "crl": 0, "x509_ca": 0}


def test_node_policy_rejects_public_key_aliases_and_preserves_clean_pss_root():
    from playwright._impl._driver import compute_driver_executable

    roots = x509.load_pem_x509_certificates((FIXTURES / "roots.pem").read_bytes())
    variants = [
        _ec_key_pem(roots[0], encoding)
        for encoding in ("compressed", "constructed", "unused_bits")
    ]

    def pss_alias(cert):
        spki = cert.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        body = _contents(spki).replace(
            bytes.fromhex("300d06092a864886f70d0101010500"),
            bytes.fromhex("300b06092a864886f70d01010a"),
        )
        return ssl.DER_cert_to_PEM_cert(_replace_spki(cert, _tlv(0x30, body)))

    variants.append(
        pss_alias(
            next(
                cert
                for cert in roots
                if isinstance(cert.public_key(), rsa.RSAPublicKey)
            )
        )
    )
    clean = next(
        cert
        for cert in x509.load_pem_x509_certificates(Path(certifi.where()).read_bytes())
        if isinstance(cert.public_key(), rsa.RSAPublicKey)
    )
    variants.append(pss_alias(clean))
    policy = Path(browser.__file__).with_name("node_ca_policy.cjs")
    node, _ = compute_driver_executable()
    result = subprocess.run(
        [
            node,
            "-e",
            "const fs=require('node:fs');const {isDistrusted}=require(process.argv[1]);console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(isDistrusted)));",
            str(policy),
        ],
        input=json.dumps(variants),
        text=True,
        capture_output=True,
        timeout=15,
        check=True,
    )
    assert json.loads(result.stdout) == [True, True, True, True, False]


def test_incident_key_identity_matches_public_key_numbers():
    certificates = x509.load_pem_x509_certificates(
        (FIXTURES / "roots.pem").read_bytes()
        + Path(browser.__file__).with_name("emudhra_intermediates.pem").read_bytes()
    )
    expected = set()
    for cert in certificates:
        key = cert.public_key()
        numbers = key.public_numbers()
        if isinstance(key, rsa.RSAPublicKey):
            identity = f"rsa:{numbers.n:x}"
        else:
            identity = f"ec:{numbers.x:0{(key.key_size + 7) // 8 * 2}x}"
        fingerprint = hashlib.sha256(identity.encode("ascii")).hexdigest()
        assert (
            _key_fingerprint(cert.public_bytes(serialization.Encoding.DER))
            == fingerprint
        )
        expected.add(fingerprint)
    assert expected == DISTRUSTED_KEYS


@pytest.mark.parametrize("payload", ["!", "AA=="])
def test_filter_rejects_malformed_certificates(payload):
    clean = Path(certifi.where()).read_text(encoding="ascii")
    with pytest.raises(ssl.SSLError):
        filtered_ca_bundle(
            clean
            + f"\n-----BEGIN CERTIFICATE-----\n{payload}\n-----END CERTIFICATE-----\n"
        )


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

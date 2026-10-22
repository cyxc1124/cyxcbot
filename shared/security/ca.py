"""Incident roots shared by runtime, installers and packaged trust checks."""

import hashlib
import json
import re
import ssl
from pathlib import Path

DISTRUSTED_ROOTS = frozenset(
    json.loads(Path(__file__).with_name("distrusted_roots.json").read_text()).values()
)
DISTRUSTED_KEYS = frozenset(
    json.loads(Path(__file__).with_name("distrusted_keys.json").read_text()).values()
)


def _der_items(data: bytes):
    offset = 0
    while offset < len(data):
        if offset + 2 > len(data):
            raise ssl.SSLError("Invalid certificate encoding")
        tag, length = data[offset : offset + 2]
        if tag & 0x1F == 0x1F:
            raise ssl.SSLError("Unsupported certificate tag")
        offset += 2
        if length & 0x80:
            count = length & 0x7F
            if not count or offset + count > len(data):
                raise ssl.SSLError("Unsupported certificate encoding")
            length = int.from_bytes(data[offset : offset + count])
            offset += count
        end = offset + length
        if end > len(data):
            raise ssl.SSLError("Invalid certificate length")
        yield tag, data[offset:end]
        offset = end


def _key_fingerprint(der: bytes) -> str | None:
    # Bootstrap runs before cryptography is installed; OpenSSL validates the input.
    certificate_tag, certificate = next(_der_items(der))
    tbs_tag, tbs = next(_der_items(certificate))
    if certificate_tag != 0x30 or tbs_tag != 0x30:
        raise ssl.SSLError("Invalid CA certificate structure")
    fields = list(_der_items(tbs))
    spki_tag, spki = fields[6 if fields[0][0] == 0xA0 else 5]
    if spki_tag != 0x30:
        raise ssl.SSLError("Invalid public key structure")
    algorithm, public_key = list(_der_items(spki))
    if (
        algorithm[0] != 0x30
        or public_key[0] != 0x03
        or not public_key[1]
        or public_key[1][0] != 0
    ):
        raise ssl.SSLError("Non-canonical public key BIT STRING in CA certificate")
    oid_tag, oid_bytes = next(_der_items(algorithm[1]))
    if oid_tag != 0x06:
        raise ssl.SSLError("Non-canonical public key algorithm in CA certificate")
    start = True
    for byte in oid_bytes:
        if start and byte == 0x80:
            raise ssl.SSLError("Non-canonical public key algorithm in CA certificate")
        start = byte < 0x80
    if not start:
        raise ssl.SSLError("Invalid public key algorithm in CA certificate")
    oid = oid_bytes.hex()
    key = public_key[1][1:]
    if oid in ("2a864886f70d010101", "2a864886f70d01010a"):
        tag, sequence = next(_der_items(key))
        integer_tag, modulus = next(_der_items(sequence))
        if tag != 0x30 or integer_tag != 0x02 or not modulus or modulus[0] & 0x80:
            raise ssl.SSLError("Non-canonical RSA public key in CA certificate")
        identity = f"rsa:{int.from_bytes(modulus):x}"
    elif oid == "2a8648ce3d0201":
        if not key or key[0] not in (2, 3, 4):
            raise ssl.SSLError("Unsupported EC public key encoding in CA certificate")
        # The x coordinate matches compressed, uncompressed and inverse EC keys.
        coordinate = key[1:] if key[0] in (2, 3) else key[1 : 1 + (len(key) - 1) // 2]
        identity = f"ec:{coordinate.hex()}"
    else:
        return None
    return hashlib.sha256(identity.encode("ascii")).hexdigest()


def fingerprints(context: ssl.SSLContext) -> set[str]:
    return {
        hashlib.sha256(cert).hexdigest()
        for cert in context.get_ca_certs(binary_form=True)
    }


def check_trust_store(context: ssl.SSLContext) -> None:
    roots = fingerprints(context)
    if (
        not context.cert_store_stats()["x509"]
        or roots & DISTRUSTED_ROOTS
        or any(
            _key_fingerprint(cert) in DISTRUSTED_KEYS
            for cert in context.get_ca_certs(binary_form=True)
        )
    ):
        raise ssl.SSLError("CA bundle is empty or contains a distrusted incident root")


def filtered_ca_bundle(pem: str) -> str:
    certs = re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", pem, re.DOTALL
    )
    allowed = []
    for cert in certs:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=cert)
        if _key_fingerprint(ssl.PEM_cert_to_DER_cert(cert)) not in DISTRUSTED_KEYS:
            allowed.append(cert)
    if not allowed:
        raise ssl.SSLError("No trusted certificates remain in the CA bundle")
    return "\n".join(allowed) + "\n"

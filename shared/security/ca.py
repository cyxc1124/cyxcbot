"""Incident roots shared by runtime, installers and packaged trust checks."""

import hashlib
import json
import re
import ssl
from pathlib import Path

DISTRUSTED_ROOTS = frozenset(
    json.loads(Path(__file__).with_name("distrusted_roots.json").read_text()).values()
)


def fingerprints(context: ssl.SSLContext) -> set[str]:
    return {
        hashlib.sha256(cert).hexdigest()
        for cert in context.get_ca_certs(binary_form=True)
    }


def check_trust_store(context: ssl.SSLContext) -> None:
    roots = fingerprints(context)
    if not context.cert_store_stats()["x509"] or roots & DISTRUSTED_ROOTS:
        raise ssl.SSLError("CA bundle is empty or contains a distrusted incident root")


def filtered_ca_bundle(pem: str) -> str:
    certs = re.findall(
        r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", pem, re.DOTALL
    )
    allowed = [
        cert
        for cert in certs
        if hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert)).hexdigest()
        not in DISTRUSTED_ROOTS
    ]
    if not allowed:
        raise ssl.SSLError("No trusted certificates remain in the CA bundle")
    return "\n".join(allowed) + "\n"

"""Real signed images verify provenance separately from AI declarations and trust."""

from datetime import datetime, timedelta, timezone
from io import BytesIO

import ai_image_helpers  # noqa: F401
import c2pa
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from PIL import Image

from plugins.ai_image_detector.c2pa_check import _has_ai_declaration, inspect_c2pa

AI_SOURCE = "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia"


def _image() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (8, 8), "red").save(stream, format="PNG")
    return stream.getvalue()


@pytest.fixture(scope="module")
def signer_info():
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CyxcBot test only")])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(True, True, False, False, False, False, False, False, False),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]),
            critical=False,
        )
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(key.public_key()),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    return c2pa.C2paSignerInfo(
        "es256",
        cert.public_bytes(serialization.Encoding.PEM),
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        None,
    )


def _signed_image(signer_info, source: str) -> bytes:
    manifest = {
        "title": "test",
        "format": "image/png",
        "assertions": [
            {
                "label": "c2pa.actions.v2",
                "data": {
                    "actions": [{"action": "c2pa.created", "digitalSourceType": source}]
                },
            }
        ],
    }
    output = BytesIO()
    with (
        c2pa.Signer.from_info(signer_info) as signer,
        c2pa.Builder(manifest) as builder,
    ):
        builder.sign(signer, "image/png", BytesIO(_image()), output)
    return output.getvalue()


def test_unsigned_image_has_no_credentials():
    result = inspect_c2pa(_image())
    assert result.status == "absent"
    assert not result.ai_declared


@pytest.mark.parametrize(
    "source,expected",
    [
        (AI_SOURCE, True),
        (AI_SOURCE.replace("trainedAlgorithmicMedia", "digitalCapture"), False),
    ],
)
def test_real_credentials_distinguish_ai_and_self_signed_trust(
    signer_info, source, expected
):
    result = inspect_c2pa(_signed_image(signer_info, source))
    assert result.status == "present"
    assert result.ai_declared is expected
    assert result.validation_state == "Valid"
    assert result.validation_state != "Trusted"


def test_modified_image_does_not_pass_validation(signer_info):
    image = bytearray(_signed_image(signer_info, AI_SOURCE))
    image[image.index(b"IDAT") + 5] ^= 1
    result = inspect_c2pa(bytes(image))
    assert result.validation_state == "Invalid"


def test_non_image_is_not_reported_as_clean():
    assert inspect_c2pa(b"not an image").status == "unreadable"


def test_only_active_provenance_chain_counts():
    ai = {
        "assertions": [
            {
                "label": "c2pa.actions",
                "data": {"actions": [{"digitalSourceType": AI_SOURCE}]},
            }
        ]
    }
    store = {"active_manifest": "photo", "manifests": {"photo": {}, "ai": ai}}
    assert not _has_ai_declaration(store)
    store["manifests"]["photo"]["ingredients"] = [{"active_manifest": "ai"}]
    assert _has_ai_declaration(store)


@pytest.mark.parametrize(
    "data", [None, [], {"actions": [None, {"digitalSourceType": []}]}]
)
def test_unstructured_assertions_are_not_ai_evidence(data):
    assert not _has_ai_declaration(
        {
            "active_manifest": "image",
            "manifests": {
                "image": {"assertions": [{"label": "c2pa.actions", "data": data}]}
            },
        }
    )

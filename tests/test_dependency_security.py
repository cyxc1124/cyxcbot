"""Regression checks for the CA bundle and native image decoder security fixes."""

import hashlib
import ssl
import subprocess
import sys

import httpx
import pytest
from PIL import Image


def test_httpx_trust_store_excludes_compromised_emsign_ca():
    context = httpx.create_ssl_context(trust_env=False)
    roots = {
        hashlib.sha256(cert).hexdigest()
        for cert in context.get_ca_certs(binary_form=True)
    }

    assert roots
    assert (
        "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b" not in roots
    )
    assert context.check_hostname
    assert context.verify_mode == ssl.CERT_REQUIRED


@pytest.mark.parametrize("mode", ["L", "RGB"])
def test_jpeg_decoder_rejects_scanlines_wider_than_tile(tmp_path, mode):
    path = tmp_path / "image.jpg"
    Image.new(mode, (128, 128)).save(path)

    # A vulnerable native decoder must not be able to corrupt the pytest process.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from PIL import Image

with Image.open(sys.argv[1]) as image:
    image.tile = [image.tile[0]._replace(extents=(0, 0, 64, 64))]
    try:
        image.load()
    except OSError as exc:
        assert "broken data stream" in str(exc)
    else:
        raise AssertionError("JPEG decoder accepted scanlines wider than its tile")
""",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr

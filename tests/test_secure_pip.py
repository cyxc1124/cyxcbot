"""Installer policy must survive stale vendored roots, host CAs and pip config."""

import os
import ssl
import subprocess
import sys
from pathlib import Path

import certifi
import pytest

from scripts import secure_pip
from shared.security.ca import DISTRUSTED_ROOTS, fingerprints
from tests.test_x_https_proxy import tls_contexts as tls_contexts


@pytest.mark.parametrize("pip_version", ["24.3.1", "26.2.2"])
def test_installer_filters_roots_preserves_private_ca_and_proxy(
    monkeypatch, tmp_path, tls_contexts, pip_version
):
    from pip._vendor import certifi as vendored

    roots = Path(__file__).parent / "fixtures" / "ca_incident" / "roots.pem"
    monkeypatch.setattr(vendored, "where", lambda: str(roots))
    private_ca = tmp_path / "private.pem"
    private_ca.write_bytes(
        Path(certifi.where()).read_bytes() + (tmp_path / "cert.pem").read_bytes()
    )
    monkeypatch.setenv("PIP_CERT", str(private_ca))
    monkeypatch.setenv("PIP_TRUSTED_HOST", "pypi.org")
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.invalid:8080")
    monkeypatch.setenv("PIP_INDEX_URL", "https://index.invalid/simple")
    monkeypatch.setattr(secure_pip, "version", lambda name: pip_version)
    calls = []
    real_run = subprocess.run

    def run(command, *, env, check):
        assert check
        assert "--use-deprecated=legacy-certs" in command
        assert "PIP_TRUSTED_HOST" not in env
        assert env["PIP_CONFIG_FILE"] == os.devnull
        assert env["PIP_USE_DEPRECATED"] == "legacy-certs"
        assert env["HTTPS_PROXY"] == "http://proxy.invalid:8080"
        assert env["PIP_INDEX_URL"] == "https://index.invalid/simple"
        context = ssl.create_default_context(cafile=env["PIP_CERT"])
        assert not fingerprints(context) & DISTRUSTED_ROOTS
        assert (tmp_path / "cert.pem").read_text().strip() in Path(
            env["PIP_CERT"]
        ).read_text()
        calls.append(command)
        if command[-1] == "requirements.txt":
            real_run(
                [
                    sys.executable,
                    "-c",
                    """
import os
from pip._internal.commands import create_command
from pip._internal.cli import index_command
def forbidden():
    raise AssertionError('build subprocess restored system trust')
index_command._create_truststore_ssl_context = forbidden
command = create_command('install')
options, _ = command.parse_args(['--no-index', '--ignore-installed', '--no-user', 'example'])
session = command._build_session(options)
assert session.verify == os.environ['PIP_CERT']
""",
                ],
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

    monkeypatch.setattr(secure_pip.subprocess, "run", run)
    secure_pip.main(["install", "-r", "requirements.txt"])
    assert len(calls) == (2 if pip_version == "24.3.1" else 1)
    assert calls[-1][-3:] == ["install", "-r", "requirements.txt"]


def test_installer_stops_on_failed_secure_bootstrap(monkeypatch):
    monkeypatch.setattr(secure_pip, "version", lambda name: "24.3.1")
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(secure_pip.subprocess, "run", fail)
    with pytest.raises(subprocess.CalledProcessError):
        secure_pip.main(["install", "-r", "requirements.txt"])
    assert len(calls) == 1


@pytest.mark.parametrize(
    "override",
    [
        "--trusted-host=pypi.org",
        "--cert=other.pem",
        "--use-feature=truststore",
        "--isolated",
        "--trusted-h=pypi.org",
        "--cer=other.pem",
        "--use-f=truststore",
        "--isola",
    ],
)
def test_installer_rejects_tls_overrides(override):
    with pytest.raises(SystemExit, match="TLS overrides"):
        secure_pip.main(["install", override, "example"])

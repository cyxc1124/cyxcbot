"""Install build dependencies without restoring incident roots from pip or the OS."""

import os
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.security.ca import filtered_ca_bundle  # noqa: E402


def main(args=None) -> None:
    from pip._vendor import certifi

    args = sys.argv[1:] if args is None else args
    if not args or args[0] != "install":
        raise SystemExit("Usage: secure_pip.py install <pip install arguments>")
    restricted = ("--cert", "--trusted-host", "--use-feature", "--isolated")
    # pip also accepts unambiguous long-option abbreviations.
    if any(
        option.startswith("--")
        and len(option) > 2
        and any(flag.startswith(option) for flag in restricted)
        for option in (arg.split("=", 1)[0] for arg in args)
    ):
        raise SystemExit("TLS overrides must use a reviewed PIP_CERT bundle")

    pem = Path(certifi.where()).read_text(encoding="ascii")
    for key in ("PIP_CERT", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "SSL_CERT_FILE"):
        if extra := os.environ.get(key):
            pem += "\n" + Path(extra).read_text(encoding="ascii")
    pem = filtered_ca_bundle(pem)
    env = os.environ.copy()
    for key in (
        "PIP_TRUSTED_HOST",
        "REQUESTS_CA_BUNDLE",
        "CURL_CA_BUNDLE",
        "PIP_USE_FEATURE",
    ):
        env.pop(key, None)
    # A user/site pip.conf can add trusted-host; index/proxy env settings remain.
    env["PIP_CONFIG_FILE"] = os.devnull
    # PEP 517 build-dependency subprocesses do not inherit the parent's argv.
    env["PIP_USE_DEPRECATED"] = "legacy-certs"
    with tempfile.TemporaryDirectory(prefix="cyxcbot-pip-ca-") as directory:
        bundle = Path(directory) / "cacert.pem"
        bundle.write_text(pem, encoding="ascii")
        env["PIP_CERT"] = str(bundle)
        command = [
            sys.executable,
            "-m",
            "pip",
            "--cert",
            str(bundle),
            # Modern pip otherwise unions Windows/macOS system trust into certifi.
            "--use-deprecated=legacy-certs",
        ]
        if tuple(int(part) for part in version("pip").split(".")[:3]) < (26, 2, 2):
            subprocess.run(
                [*command, "install", "--upgrade", "pip==26.2.2"], env=env, check=True
            )
        subprocess.run([*command, *args], env=env, check=True)


if __name__ == "__main__":
    main()

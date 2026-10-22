"""Install build dependencies without restoring incident roots from pip or the OS."""

import os
import subprocess
import sys
import tempfile
from importlib.metadata import version
from optparse import BadOptionError, Values
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shared.security.ca import filtered_ca_bundle  # noqa: E402


def main(args=None) -> None:
    from pip._internal.commands import create_command
    from pip._internal.utils.misc import strtobool
    from pip._vendor import certifi

    args = sys.argv[1:] if args is None else args
    if not args or args[0] != "install":
        raise SystemExit("Usage: secure_pip.py install <pip install arguments>")
    restricted = ("--cert", "--trusted-host", "--use-feature", "--isolated")
    network_flags = (
        ("index_url", "--index-url"),
        ("extra_index_urls", "--extra-index-url"),
        ("no_index", "--no-index"),
        ("find_links", "--find-links"),
        ("proxy", "--proxy"),
        ("client_cert", "--client-cert"),
        ("timeout", "--timeout"),
        ("retries", "--retries"),
    )
    parser = create_command("install", isolated=True).parser
    if not parser.has_option("--no-proxy-env"):
        parser.add_option("--no-proxy-env", action="store_true", dest="no_proxy_env")
    network_names = {name for name, _ in network_flags} | {"no_proxy_env"}
    restricted_options = {parser.get_option(flag) for flag in restricted}

    def reject_tls_override(*args):
        raise SystemExit("TLS overrides must use a reviewed PIP_CERT bundle")

    # Reuse pip's option arities so backend values cannot become TLS options.
    for option in parser._get_all_options():
        if option in restricted_options:
            option.process = reject_tls_override
        elif option.dest not in network_names:
            option.process = lambda *args: None
    process_args = parser._process_args

    def process_network_args(largs, rargs, values):
        while True:
            try:
                return process_args(largs, rargs, values)
            except BadOptionError:
                # New install options need not exist in the bootstrapping pip.
                continue

    parser._process_args = process_network_args
    options, _ = parser.parse_args(args[1:], values=Values())

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
    if (
        getattr(options, "proxy", env.get("PIP_PROXY")) is not None
        or getattr(options, "no_proxy_env", False)
        or strtobool(env.get("PIP_NO_PROXY_ENV", "no") or "no")
    ):
        # Older pip lacks both --no-proxy-env and explicit-proxy precedence.
        for key in tuple(env):
            if key.lower() in {"http_proxy", "https_proxy", "all_proxy", "no_proxy"}:
                env.pop(key)
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
            bootstrap_options = []
            for name, flag in network_flags:
                value = getattr(options, name, None)
                if value is None:
                    continue
                if value is True:
                    bootstrap_options.append(flag)
                else:
                    for item in value if isinstance(value, list) else [value]:
                        bootstrap_options.extend((flag, str(item)))
            subprocess.run(
                [*command, "install", "--upgrade", *bootstrap_options, "pip==26.2.2"],
                env=env,
                check=True,
            )
        subprocess.run([*command, *args], env=env, check=True)


if __name__ == "__main__":
    main()

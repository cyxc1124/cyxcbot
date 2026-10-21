"""Verify source/image or actual frozen-package CA and Playwright driver data."""

import asyncio
import hashlib
import json
import ssl
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import certifi  # noqa: E402
from playwright._impl._driver import compute_driver_executable  # noqa: E402

from shared.security.browser import create_browser_context  # noqa: E402
from shared.security.ca import check_trust_store, fingerprints  # noqa: E402
from shared.security.playwright import node_environment  # noqa: E402


def check_artifacts(dist=None) -> None:
    policy_dir = Path(__file__).resolve().parents[1] / "shared" / "security"
    bundle = Path(certifi.where())
    node, _ = compute_driver_executable()
    if dist is not None:
        internal = Path(dist) / "_internal"
        bundled_policy = internal / "shared" / "security"
        for name in (
            "node_ca.cjs",
            "node_ca_policy.cjs",
            "distrusted_keys.json",
            "distrusted_roots.json",
            "emudhra_intermediates.pem",
            "browser.py",
            "playwright.py",
            "ca.py",
            "tls.py",
        ):
            if (bundled_policy / name).read_bytes() != (policy_dir / name).read_bytes():
                raise RuntimeError("Packaged TLS policy differs from tested source")
        policy_dir = bundled_policy
        packaged_bundle = internal / "certifi" / "cacert.pem"
        if packaged_bundle.read_bytes() != bundle.read_bytes():
            raise RuntimeError("Packaged CA bundle differs from tested certifi")
        bundle = packaged_bundle
        node = str(internal / "playwright" / "driver" / "node.exe")

    context = ssl.create_default_context(cafile=str(bundle))
    check_trust_store(context)
    result = subprocess.run(
        [
            node,
            "-e",
            "const tls=require('node:tls');const {X509Certificate}=require('node:crypto');"
            "console.log(JSON.stringify(tls.getCACertificates('default').map("
            "c=>new X509Certificate(c).fingerprint256.replaceAll(':','').toLowerCase())))",
        ],
        env=node_environment(bundle=bundle, policy_dir=policy_dir),
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    if set(json.loads(result.stdout)) != fingerprints(context):
        raise RuntimeError("Playwright Node default trust differs from tested certifi")
    from playwright._impl import _transport
    from playwright.async_api import async_playwright

    original_driver = _transport.compute_driver_executable
    original_env = _transport.get_driver_env

    def driver_env():
        env = node_environment(original_env(), bundle=bundle, policy_dir=policy_dir)
        if dist is not None:
            env["PLAYWRIGHT_BROWSERS_PATH"] = str(
                (Path(dist) / "ms-playwright").resolve(strict=True)
            )
        return env

    _transport.get_driver_env = driver_env
    if dist is not None:
        _transport.compute_driver_executable = lambda: (
            node,
            str(internal / "playwright" / "driver" / "package" / "cli.js"),
        )

    async def verify_browser():
        async with async_playwright() as pw:
            options = {"headless": True, "args": ["--no-sandbox"]}
            if dist is not None:
                executable = Path(pw.chromium.executable_path)
                if not executable.is_file():
                    raise RuntimeError("Required packaged Chromium is missing")
                options["executable_path"] = str(executable)
            browser_context, resources = await create_browser_context(pw, **options)
            try:
                page = await browser_context.new_page()
                await page.set_content("<h1>TLS verified</h1>")
                if not (await page.screenshot()).startswith(b"\x89PNG\r\n\x1a\n"):
                    raise RuntimeError("Packaged Chromium screenshot failed")
            finally:
                await resources.aclose()

    try:
        asyncio.run(verify_browser())
    finally:
        _transport.compute_driver_executable = original_driver
        _transport.get_driver_env = original_env
    print(
        "CA bundle, Playwright Node trust and Chromium distrust verified:",
        hashlib.sha256(bundle.read_bytes()).hexdigest(),
    )


if __name__ == "__main__":
    check_artifacts(sys.argv[1] if len(sys.argv) > 1 else None)

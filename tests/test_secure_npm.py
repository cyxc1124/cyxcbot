"""npm and its lifecycle children must use filtered CAs without losing private trust."""

import asyncio
import json
import os
import shutil
import ssl
import subprocess
from pathlib import Path

import certifi
import pytest
from aiohttp import web

from shared.security.ca import DISTRUSTED_ROOTS
from tests.test_x_https_proxy import tls_contexts as tls_contexts

ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="npm requires a Node installation")


def environment(monkeypatch, tmp_path):
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
        monkeypatch.delenv(name, raising=False)
        monkeypatch.delenv(name.lower(), raising=False)
    monkeypatch.setenv("NO_PROXY", "*")
    monkeypatch.setenv(
        "NODE_EXTRA_CA_CERTS", str(ROOT / "tests/fixtures/ca_incident/roots.pem")
    )
    monkeypatch.setenv("NODE_TLS_REJECT_UNAUTHORIZED", "0")
    monkeypatch.setenv("NPM_CONFIG_STRICT_SSL", "false")
    monkeypatch.setenv("NPM_CONFIG_CACHE", str(tmp_path / "npm-cache"))
    monkeypatch.setenv("NPM_CONFIG_USERCONFIG", str(tmp_path / "user.npmrc"))
    monkeypatch.setenv("NPM_CONFIG_GLOBALCONFIG", str(tmp_path / "global.npmrc"))
    monkeypatch.setenv("NPM_CONFIG_UPDATE_NOTIFIER", "false")
    return dict(os.environ)


@pytest.mark.parametrize("exit_code", [0, 7])
def test_npm_children_filter_roots_and_preserve_private_ca_proxy_and_unicode_paths(
    monkeypatch, tmp_path, tls_contexts, exit_code
):
    project = tmp_path / "项目 with spaces"
    project.mkdir()
    checkout = tmp_path / "源码 checkout with spaces"
    (checkout / "scripts").mkdir(parents=True)
    policy = checkout / "shared/security"
    policy.mkdir(parents=True)
    wrapper = checkout / "scripts/secure_npm.cjs"
    shutil.copyfile(ROOT / "scripts/secure_npm.cjs", wrapper)
    for name in (
        "node_ca.cjs",
        "node_ca_policy.cjs",
        "distrusted_roots.json",
        "distrusted_keys.json",
    ):
        shutil.copyfile(ROOT / "shared/security" / name, policy / name)
    bundle = project / "private CA.pem"
    root = ssl.PEM_cert_to_DER_cert(
        (ROOT / "tests/fixtures/emsign_ecc_root_ca_g3.pem").read_text()
    )
    bundle.write_bytes(
        (tmp_path / "cert.pem").read_bytes()
        + ssl.DER_cert_to_PEM_cert(root[:-1] + bytes([root[-1] ^ 1])).encode()
    )
    (project / ".npmrc").write_text(
        f"cafile={bundle}\nstrict-ssl=false\nnode-options=--max-old-space-size=256\n"
    )
    (project / "package.json").write_text(
        json.dumps({"scripts": {"ca-audit": "node audit.cjs"}})
    )
    (project / "audit.cjs").write_text(
        "const {Worker}=require('node:worker_threads');"
        "function roots(){return require('node:tls').getCACertificates('default').map("
        "c=>new (require('node:crypto').X509Certificate)(c).fingerprint256.replaceAll(':','').toLowerCase())}"
        "const worker=new Worker(roots.toString()+\";require('node:worker_threads').parentPort.postMessage(roots())\",{eval:true});"
        "worker.once('message',workerRoots=>{process.stdout.write(JSON.stringify({roots:roots(),workerRoots,"
        "bundle:process.env.CYXCBOT_CA_BUNDLE,reject:process.env.NODE_TLS_REJECT_UNAUTHORIZED,"
        "proxy:process.env.HTTPS_PROXY==='http://proxy.invalid:8080',"
        "heap:require('node:v8').getHeapStatistics().heap_size_limit,args:process.argv.slice(2)})+'\\n',()=>{"
        f"process.exit({exit_code});"
        "})});worker.once('error',error=>{throw error});"
    )
    env = environment(monkeypatch, tmp_path)
    env["HTTPS_PROXY"] = "http://proxy.invalid:8080"
    result = subprocess.run(
        [
            NODE,
            str(wrapper),
            "run",
            "ca-audit",
            "--silent",
            "--",
            "forwarded=中文 with spaces",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == exit_code, result.stdout + result.stderr
    audit = json.loads(result.stdout.strip())
    assert not set(audit["roots"]) & DISTRUSTED_ROOTS
    assert set(audit["workerRoots"]) == set(audit["roots"])
    import hashlib

    assert (
        hashlib.sha256(root[:-1] + bytes([root[-1] ^ 1])).hexdigest()
        not in audit["roots"]
    )
    private = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    private.load_verify_locations(cafile=tmp_path / "cert.pem")
    from shared.security.ca import check_trust_store, fingerprints

    assert fingerprints(private) <= set(audit["roots"])
    check_trust_store(private)
    assert audit["proxy"] and audit["reject"] == "1"
    assert audit["heap"] < 400 * 1024 * 1024
    assert audit["args"] == ["forwarded=中文 with spaces"]
    assert not Path(audit["bundle"]).exists()


@pytest.mark.parametrize(
    "trust,override",
    [
        ("trusted", None),
        ("untrusted", None),
        ("wrong_hostname", None),
        ("untrusted", "--no-strict-ssl"),
        ("wrong_hostname", "--no-strict-ssl"),
    ],
)
async def test_npm_actual_registry_tls_rejects_before_auth(
    monkeypatch, tmp_path, tls_contexts, trust, override
):
    server_context, _ = tls_contexts
    received = []

    async def package(request):
        received.append(request.headers.get("Authorization"))
        return web.json_response(
            {
                "name": "ca-regression",
                "dist-tags": {"latest": "1.0.0"},
                "versions": {"1.0.0": {"name": "ca-regression", "version": "1.0.0"}},
            }
        )

    app = web.Application()
    app.router.add_get("/ca-regression", package)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0, ssl_context=server_context)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    host = "localhost" if trust == "wrong_hostname" else "127.0.0.1"
    registry = f"{host}:{port}"
    ca = tmp_path / "cert.pem" if trust != "untrusted" else Path(certifi.where())
    (tmp_path / ".npmrc").write_text(
        f"registry=https://{registry}/\ncafile={ca}\nstrict-ssl=false\n"
        f"//{registry}/:_authToken=ca-regression-token\n"
    )
    env = environment(monkeypatch, tmp_path)
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            NODE,
            str(ROOT / "scripts/secure_npm.cjs"),
            *([override] if override else []),
            "view",
            "ca-regression",
            "version",
            "--fetch-retries=0",
            "--fetch-timeout=3000",
            "--loglevel=error",
            cwd=tmp_path,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), 25)
        if trust == "trusted":
            assert process.returncode == 0, stdout + stderr
            assert b"1.0.0" in stdout
            assert received == ["Bearer ca-regression-token"]
        else:
            assert process.returncode != 0
            assert any(
                code in stderr
                for code in (
                    b"SELF_SIGNED_CERT",
                    b"CERT_ALTNAME_INVALID",
                    b"UNABLE_TO_VERIFY",
                    b"TLS overrides",
                )
            ), stderr
            assert not received
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        await runner.cleanup()

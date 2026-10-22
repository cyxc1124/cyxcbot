"""npm and its lifecycle children must use filtered CAs without losing private trust."""

import asyncio
import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
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


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX split npm symlink layout")
@pytest.mark.parametrize("split_dependencies", [False, True])
@pytest.mark.parametrize("bundled_symlink", [False, True])
def test_npm_supports_split_package_and_dependency_layouts(
    monkeypatch, tmp_path, split_dependencies, bundled_symlink
):
    npm_entrypoint = shutil.which("npm")
    assert npm_entrypoint
    original = Path(npm_entrypoint).resolve().parent.parent
    npm = tmp_path / "distribution/share/nodejs/npm"
    shutil.copytree(original, npm, symlinks=True)
    if split_dependencies:
        shutil.move(npm / "node_modules", npm.parent / "node_modules")
    binary_directory = tmp_path / "distribution/bin"
    binary_directory.mkdir()
    node = binary_directory / "node"
    node.symlink_to(Path(NODE).resolve())
    (binary_directory / "npm").symlink_to(npm / "bin/npm-cli.js")
    if bundled_symlink:
        bundled = tmp_path / "distribution/lib/node_modules/npm"
        bundled.parent.mkdir(parents=True)
        bundled.symlink_to(npm, target_is_directory=True)
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text(
        json.dumps({"scripts": {"ca-audit": "node audit.cjs"}}), encoding="utf-8"
    )
    (project / "audit.cjs").write_text(
        "console.log(JSON.stringify({roots:require('node:tls').getCACertificates('default').map("
        "c=>new (require('node:crypto').X509Certificate)(c).fingerprint256.replaceAll(':','').toLowerCase()),"
        "args:process.argv.slice(2)}))",
        encoding="utf-8",
    )
    wrapper = str(ROOT / "scripts/secure_npm.cjs")
    arguments = [str(node), wrapper, "run", "ca-audit", "--silent", "--", "kept value"]
    script = (
        f"Object.defineProperty(process,'execPath',{{value:{json.dumps(str(node))}}});"
        f"process.argv={json.dumps(arguments)};require({json.dumps(wrapper)});"
    )
    env = environment(monkeypatch, tmp_path)
    env["PATH"] = str(binary_directory) + os.pathsep + env["PATH"]
    result = subprocess.run(
        [NODE, "-e", script],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    audit = json.loads(result.stdout.strip())
    assert audit["roots"] and not set(audit["roots"]) & DISTRUSTED_ROOTS
    assert audit["args"] == ["kept value"]


@pytest.mark.parametrize("separator", ["--", "---"])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_npm_children_filter_roots_and_preserve_private_ca_proxy_and_unicode_paths(
    monkeypatch, tmp_path, tls_contexts, exit_code, separator
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
        f"cafile={bundle}\nstrict-ssl=false\nnode-options=--max-old-space-size=256\n",
        encoding="utf-8",
    )
    (project / "package.json").write_text(
        json.dumps({"scripts": {"ca-audit": "node audit.cjs"}}), encoding="utf-8"
    )
    (project / "audit.cjs").write_text(
        "const {Worker}=require('node:worker_threads');"
        "function roots(){return require('node:tls').getCACertificates('default').map("
        "c=>new (require('node:crypto').X509Certificate)(c).fingerprint256.replaceAll(':','').toLowerCase())}"
        "const worker=new Worker(roots.toString()+\";require('node:worker_threads').parentPort.postMessage(roots())\",{eval:true});"
        "worker.once('message',workerRoots=>{process.stdout.write(JSON.stringify({roots:roots(),workerRoots,"
        "bundle:process.env.CYXCBOT_CA_BUNDLE,reject:process.env.NODE_TLS_REJECT_UNAUTHORIZED,"
        "proxy:process.env.HTTPS_PROXY==='http://proxy.invalid:8080',"
        "heap:require('node:v8').getHeapStatistics().heap_size_limit,options:process.env.NODE_OPTIONS,args:process.argv.slice(2)})+'\\n',()=>{"
        f"process.exit({exit_code});"
        "})});worker.once('error',error=>{throw error});",
        encoding="utf-8",
    )
    env = environment(monkeypatch, tmp_path)
    env["HTTPS_PROXY"] = "http://proxy.invalid:8080"
    env["NODE_OPTIONS"] = "--trace-warnings"
    result = subprocess.run(
        [
            NODE,
            str(wrapper),
            "run",
            "ca-audit",
            "--silent",
            separator,
            "forwarded=中文 with spaces",
            "--ca=literal-script-argument",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == exit_code, result.stdout + result.stderr
    audit = json.loads(result.stdout.strip())
    assert not set(audit["roots"]) & DISTRUSTED_ROOTS
    assert set(audit["workerRoots"]) == set(audit["roots"])
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
    expected_heap = int(
        subprocess.check_output(
            [
                NODE,
                "--max-old-space-size=256",
                "-p",
                "require('node:v8').getHeapStatistics().heap_size_limit",
            ],
            env=env,
        )
    )
    assert audit["heap"] == expected_heap
    assert "--trace-warnings" in audit["options"]
    assert audit["args"] == [
        "forwarded=中文 with spaces",
        "--ca=literal-script-argument",
    ]
    assert not Path(audit["bundle"]).exists()


@pytest.mark.parametrize(
    "trust,override",
    [
        ("trusted", None),
        ("untrusted", None),
        ("wrong_hostname", None),
        ("untrusted", "--no-strict-ssl"),
        ("wrong_hostname", "--no-strict-ssl"),
        ("distrusted", "cafile_ca"),
        ("distrusted", "ca_cafile"),
        ("distrusted", "repeated_ca"),
        ("distrusted", "equals"),
        ("distrusted", "abbreviated"),
        ("distrusted", "no_prefix"),
        ("distrusted", "expanded_key"),
        ("distrusted", "nested"),
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
        f"//{registry}/:_authToken=ca-regression-token\n",
        encoding="utf-8",
    )
    env = environment(monkeypatch, tmp_path)
    wrapper = ROOT / "scripts/secure_npm.cjs"
    options = [override] if override else []
    command = ["view", "ca-regression", "version"]
    if trust == "distrusted":
        checkout = tmp_path / "checkout"
        (checkout / "scripts").mkdir(parents=True)
        policy = checkout / "shared/security"
        shutil.copytree(ROOT / "shared/security", policy)
        wrapper = checkout / "scripts/secure_npm.cjs"
        shutil.copyfile(ROOT / "scripts/secure_npm.cjs", wrapper)
        roots = policy / "distrusted_roots.json"
        denied = json.loads(roots.read_text())
        private = (tmp_path / "cert.pem").read_text()
        denied["local regression canary"] = hashlib.sha256(
            ssl.PEM_cert_to_DER_cert(private)
        ).hexdigest()
        roots.write_text(json.dumps(denied))
        clean = (
            Path(certifi.where()).read_text().split("-----END CERTIFICATE-----", 1)[0]
            + "-----END CERTIFICATE-----\n"
        )
        mixed = clean + private
        ca = tmp_path / "mixed.pem"
        ca.write_text(mixed)
        options = {
            "cafile_ca": ["--cafile", str(ca), "--ca", mixed],
            "ca_cafile": ["--ca", mixed, "--cafile", str(ca)],
            "repeated_ca": ["--cafile", str(ca), "--ca", clean, "--ca", private],
            "equals": [f"--cafile={ca}", f"--ca={mixed}"],
            "abbreviated": ["--cafile", str(ca), "--ca", mixed, "--strict-ss=false"],
            "no_prefix": ["--cafile", str(ca), "--no-no-ca", mixed],
            "expanded_key": ["--cafile", str(ca), f"--${{ca_option}}={mixed}"],
            "nested": ["--cafile", str(ca), "--ca", mixed],
        }[override]
        env["ca_option"] = "ca"
        env["NPM_CONFIG_CA"] = mixed
        env["npm_config_CA"] = mixed
        if override == "nested":
            (tmp_path / "package.json").write_text(
                json.dumps({"scripts": {"registry-audit": "node registry-audit.cjs"}})
            )
            (tmp_path / "registry-audit.cjs").write_text(
                "const {spawnSync}=require('node:child_process');"
                "const result=spawnSync(process.execPath,[process.env.npm_execpath,"
                "'view','ca-regression','version','--fetch-retries=0',"
                "'--fetch-timeout=3000','--loglevel=error'],{stdio:'inherit'});"
                "if(result.error)throw result.error;process.exitCode=result.status??1;"
            )
            command = ["run", "registry-audit", "--silent"]
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            NODE,
            str(wrapper),
            *options,
            *command,
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
            ), (process.returncode, stdout, stderr)
            assert not received
    finally:
        if process is not None and process.returncode is None:
            process.kill()
            await process.wait()
        await runner.cleanup()

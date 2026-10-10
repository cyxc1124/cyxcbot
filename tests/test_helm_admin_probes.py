"""Helm health probes follow the Web Admin and probe switches."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize("web_admin_enabled", [True, False])
@pytest.mark.parametrize("probes_enabled", [True, False])
def test_helm_admin_probes_require_both_switches(
    web_admin_enabled: bool,
    probes_enabled: bool,
) -> None:
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("Helm is required to render the chart")
    chart = Path(__file__).resolve().parents[1] / "deploy" / "helm"
    result = subprocess.run(
        [
            helm,
            "template",
            "audit",
            str(chart),
            "--set",
            "secret.name=audit-existing-secret",
            "--set",
            f"webAdmin.enabled={str(web_admin_enabled).lower()}",
            "--set",
            f"probes.enabled={str(probes_enabled).lower()}",
            "--show-only",
            "templates/deployment.yaml",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    deployment = yaml.safe_load(result.stdout)
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    for probe in ("livenessProbe", "readinessProbe"):
        if web_admin_enabled and probes_enabled:
            assert container[probe] == {
                "httpGet": {"path": "/health", "port": "web-admin"},
                "initialDelaySeconds": 15,
                "periodSeconds": 20,
            }
        else:
            assert probe not in container

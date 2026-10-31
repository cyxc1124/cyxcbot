"""ServiceAccount resources match the names used by the Deployment."""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.skipif(shutil.which("helm") is None, reason="Helm is required")

CHART = Path(__file__).resolve().parents[1] / "deploy" / "helm"


def _render(*settings: str) -> list[dict]:
    command = [
        "helm",
        "template",
        "audit",
        str(CHART),
        "--set",
        "secret.name=audit-existing-secret",
    ]
    for setting in settings:
        command.extend(["--set", setting])
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return [document for document in yaml.safe_load_all(result.stdout) if document]


@pytest.mark.parametrize("name", ["", "existing-account"])
def test_disabled_service_account_only_references_existing_account(name: str) -> None:
    documents = _render(f"serviceAccount.name={name}")
    assert not any(document["kind"] == "ServiceAccount" for document in documents)
    deployment = next(
        document for document in documents if document["kind"] == "Deployment"
    )
    assert deployment["spec"]["template"]["spec"]["serviceAccountName"] == (
        name or "default"
    )


@pytest.mark.parametrize(
    ("settings", "expected_name"),
    [
        ([], "audit-cyxcbot"),
        (["serviceAccount.name=custom-account"], "custom-account"),
        (["fullnameOverride=custom-fullname"], "custom-fullname"),
        (["nameOverride=custom-chart"], "audit-custom-chart"),
    ],
)
@pytest.mark.parametrize("annotations", [{}, {"audit": "render-test"}])
def test_created_service_account_matches_deployment_and_metadata(
    settings: list[str], expected_name: str, annotations: dict[str, str]
) -> None:
    documents = _render(
        "serviceAccount.create=true",
        *settings,
        *(
            f"serviceAccount.annotations.{key}={value}"
            for key, value in annotations.items()
        ),
    )
    accounts = [
        document for document in documents if document["kind"] == "ServiceAccount"
    ]
    assert len(accounts) == 1
    account = accounts[0]
    deployment = next(
        document for document in documents if document["kind"] == "Deployment"
    )
    assert account["metadata"]["name"] == expected_name
    assert deployment["spec"]["template"]["spec"]["serviceAccountName"] == expected_name
    assert account["metadata"]["labels"] == deployment["metadata"]["labels"]
    assert account["metadata"].get("annotations", {}) == annotations
    assert not any(document["kind"] == "Secret" for document in documents)

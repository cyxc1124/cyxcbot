"""Read embedded Content Credentials without fetching resources named by the image."""

from __future__ import annotations

import json
from dataclasses import dataclass
from io import BytesIO

import c2pa

_AI_SOURCE_TYPES = frozenset(
    f"http://cv.iptc.org/newscodes/digitalsourcetype/{name}"
    for name in (
        "trainedAlgorithmicMedia",
        "compositeWithTrainedAlgorithmicMedia",
    )
)


@dataclass(frozen=True)
class C2PAResult:
    status: str
    ai_declared: bool = False
    validation_state: str = ""


def _has_ai_declaration(store: dict) -> bool:
    manifests = store.get("manifests", {})
    pending = [store.get("active_manifest")]
    seen = set()
    while pending:
        label = pending.pop()
        if not isinstance(label, str) or not label or label in seen:
            continue
        seen.add(label)
        manifest = manifests.get(label, {})
        for assertion in manifest.get("assertions", []):
            if not isinstance(assertion, dict) or assertion.get("label") not in {
                "c2pa.actions",
                "c2pa.actions.v2",
            }:
                continue
            data = assertion.get("data")
            if not isinstance(data, dict) or not isinstance(data.get("actions"), list):
                continue
            for action in data["actions"]:
                source = (
                    action.get("digitalSourceType")
                    if isinstance(action, dict)
                    else None
                )
                if isinstance(source, str) and source in _AI_SOURCE_TYPES:
                    return True
        pending.extend(
            ingredient.get("active_manifest")
            for ingredient in manifest.get("ingredients", [])
            if isinstance(ingredient, dict)
        )
    return False


def inspect_c2pa(data: bytes) -> C2PAResult:
    with c2pa.Context.from_dict(
        {
            "verify": {
                "verify_after_reading": True,
                "verify_trust": True,
                "remote_manifest_fetch": False,
                "ocsp_fetch": False,
            }
        }
    ) as context:
        try:
            with c2pa.Reader(BytesIO(data), context=context) as reader:
                store = json.loads(reader.json())
        except c2pa.C2paError.ManifestNotFound:
            return C2PAResult("absent")
        except c2pa.C2paError.RemoteManifest:
            return C2PAResult("remote")
        except c2pa.C2paError:
            return C2PAResult("unreadable")
    if not store.get("active_manifest"):
        return C2PAResult("unreadable")
    return C2PAResult(
        "present", _has_ai_declaration(store), store.get("validation_state", "Unknown")
    )

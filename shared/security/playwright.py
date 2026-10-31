"""Give Playwright's driver and downloader their own reviewed Node trust store."""

import json
import os
from functools import wraps
from pathlib import Path

import certifi


def node_environment(env=None, *, bundle=None, policy_dir=None) -> dict[str, str]:
    result = dict(os.environ if env is None else env)
    policy_dir = Path(policy_dir or Path(__file__).parent)
    preload = (policy_dir / "node_ca.cjs").resolve(strict=True)
    ca_file = Path(bundle or certifi.where()).resolve(strict=True)
    option = f"--require {json.dumps(str(preload), ensure_ascii=False)}"
    options = result.get("NODE_OPTIONS", "")
    if option not in options:
        result["NODE_OPTIONS"] = f"{options} {option}".strip()
    result["CYXCBOT_CA_BUNDLE"] = str(ca_file)
    result["NODE_TLS_REJECT_UNAUTHORIZED"] = "1"
    return result


def configure_playwright_tls() -> None:
    from playwright._impl import _transport

    original = _transport.get_driver_env
    if getattr(original, "_cyxcbot_ca_policy", False):
        return

    @wraps(original)
    def driver_env():
        return node_environment(original())

    driver_env._cyxcbot_ca_policy = True
    _transport.get_driver_env = driver_env

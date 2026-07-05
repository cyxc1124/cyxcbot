"""Sanitize database URLs for logs."""


def mask_database_url(url: str) -> str:
    """Hide credentials while keeping driver/host/db name visible."""
    if "@" in url and "://" in url:
        scheme, rest = url.split("://", 1)
        if "@" in rest:
            creds, host_part = rest.rsplit("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                return f"{scheme}://{user}:***@{host_part}"
            return f"{scheme}://***@{host_part}"
    return url

"""Browser-only JWT cookies; API clients keep explicit Bearer authentication."""

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from admin.config import get_access_token_expires, get_web_public_origin
from admin.schemas.common import TokenResponse

SESSION_COOKIE = "cyxcbot_session"
SESSION_COOKIE_PATH = "/api/v1"
SESSION_HEADER = "X-Cyxcbot-Session"


def require_browser_session(request: Request) -> None:
    if request.headers.get(SESSION_HEADER) != "cookie":
        raise HTTPException(status_code=403, detail="Browser session header required")
    site = request.headers.get("sec-fetch-site")
    origin = request.headers.get("origin")
    if site is not None:
        allowed = site in ("same-origin", "none")
    else:
        # Credentialed CORS is disabled; the custom header also blocks HTML forms.
        allowed_origins = {
            str(request.base_url).rstrip("/"),
            str(request.base_url.replace(scheme="https")).rstrip("/"),
            get_web_public_origin(),
        }
        allowed = origin is None or origin in allowed_origins
    if not allowed:
        raise HTTPException(status_code=403, detail="Cross-origin session rejected")


def browser_session_requested(request: Request) -> bool:
    if SESSION_HEADER not in request.headers:
        return False
    require_browser_session(request)
    return True


def auth_response(request: Request, token: str) -> JSONResponse:
    browser_session = browser_session_requested(request)
    body = (
        {"message": "Authenticated"}
        if browser_session
        else TokenResponse(access_token=token).model_dump()
    )
    response = JSONResponse(body, headers={"Cache-Control": "no-store"})
    if browser_session:
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=int(get_access_token_expires().total_seconds()),
            path=SESSION_COOKIE_PATH,
            httponly=True,
            # Origin retains the browser's HTTPS scheme behind a TLS terminator.
            secure=request.url.scheme == "https"
            or request.headers.get("origin", "").startswith("https://"),
            samesite="strict",
        )
    return response

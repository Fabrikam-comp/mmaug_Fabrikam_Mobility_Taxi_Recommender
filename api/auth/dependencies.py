"""Reusable checks that every route uses.

Use it in a route like this:  user: CurrentUser = Depends(current_user)
At app start, main.py must do:  app.state.authenticator = build_authenticator()
"""

from fastapi import HTTPException, Request

from .token_check import AuthError, CurrentUser


async def current_user(request: Request) -> CurrentUser:
    authenticator = getattr(request.app.state, "authenticator", None)
    if authenticator is None:
        raise HTTPException(
            status_code=500, detail="authentication is not configured")
    try:
        return await authenticator.authenticate(request.headers.get("Authorization"))
    except AuthError as exc:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status == 401 else None
        raise HTTPException(status_code=exc.status,
                            detail=str(exc), headers=headers) from exc

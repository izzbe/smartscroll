"""Authentication service — Firebase ID token verification."""

import base64
import json

import firebase_admin
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials as fb_creds

from smartscroll.config import get_settings

_initialized = False


def _init_firebase() -> None:
    global _initialized
    if _initialized or firebase_admin._apps:
        _initialized = True
        return

    settings = get_settings()
    if settings.firebase_admin_credentials_json:
        sa_json = json.loads(
            base64.b64decode(settings.firebase_admin_credentials_json).decode()
        )
        cred = fb_creds.Certificate(sa_json)
    else:
        cred = fb_creds.ApplicationDefault()

    firebase_admin.initialize_app(cred, {"projectId": settings.gcp_project_id})
    _initialized = True


_bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    http_creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """Verify Firebase ID token and return the caller's UID."""
    _init_firebase()

    if http_creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        decoded = firebase_auth.verify_id_token(http_creds.credentials)
        return decoded["uid"]
    except firebase_auth.ExpiredIdTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

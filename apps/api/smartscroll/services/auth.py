"""Authentication service."""

# TODO: Replace with Firebase Auth token verification


async def get_current_user_id() -> str:
    """Get the current user ID from the request.

    For now, returns a dummy user ID. Will be replaced with
    Firebase Auth token verification.
    """
    return "user_demo_123"

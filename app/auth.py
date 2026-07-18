"""
Manasvi - Authentication
========================
Supabase is responsible ONLY for: signup, email verification, login,
Google OAuth, and issuing JWTs. This module verifies those JWTs and
resolves the corresponding row in OUR MySQL `users` table, which
remains the single source of truth for application data.

Flow:

    Browser (Supabase JS SDK)
            |
            | signs up / logs in / Google OAuth
            v
    Supabase Auth  -->  issues a JWT (access_token)
            |
            | Authorization: Bearer <jwt>
            v
    FastAPI (this file)
            |
            | verify signature + expiry with SUPABASE_JWT_SECRET
            v
    MySQL  -->  find-or-create the user row, keyed on supabase_user_id
"""

import jwt
from fastapi import Header, HTTPException

from app.config import SUPABASE_URL, SUPABASE_JWT_SECRET
from app.database import DatabaseManager

db = DatabaseManager()

# Newer Supabase projects sign JWTs with an asymmetric key (RS256/ES256)
# and publish the public half at this well-known JWKS endpoint. Older
# projects may still use a single shared HS256 secret instead - we try
# JWKS first and fall back to the shared secret if one was provided.
_JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"
_jwks_client = jwt.PyJWKClient(_JWKS_URL)


def verify_supabase_jwt(token: str) -> dict:
    """
    Verifies a Supabase-issued JWT and returns its decoded claims.
    Raises HTTPException(401) if the token is missing, expired, or
    has an invalid signature.
    """

    try:
        try:
            # Preferred path: newer Supabase projects (asymmetric keys).
            signing_key = _jwks_client.get_signing_key_from_jwt(token).key

            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "ES256"],
                audience="authenticated",
            )

        except jwt.exceptions.PyJWKClientError:
            # Fallback path: legacy Supabase projects (shared HS256 secret).
            if not SUPABASE_JWT_SECRET:
                raise

            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")

    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token.")


def _extract_bearer_token(authorization: str) -> str:

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header.")

    return authorization.removeprefix("Bearer ").strip()


def get_current_claims(authorization: str = Header(default=None)) -> dict:
    """
    Lightweight dependency: verifies the JWT and returns its claims,
    without touching MySQL. Useful for the /api/auth/sync endpoint,
    which is what actually creates the MySQL row on first login.
    """

    token = _extract_bearer_token(authorization)

    return verify_supabase_jwt(token)


def get_current_user(authorization: str = Header(default=None)) -> dict:
    """
    Full dependency for protecting normal API routes: verifies the
    JWT AND resolves the matching MySQL user row. If the user has
    never been synced (first login not yet completed), this raises
    a 401 telling the frontend to call /api/auth/sync first.
    """

    claims = get_current_claims(authorization)
    supabase_user_id = claims.get("sub")

    user = db.get_user_by_supabase_id(supabase_user_id)

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="User not found. Please complete login sync first.",
        )

    return user

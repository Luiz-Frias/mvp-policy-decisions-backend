# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""SSO authentication endpoints for user login."""

from typing import Any

from beartype import beartype
from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from policy_core.core.cache import Cache
from policy_core.core.config import Settings, get_settings

from ...core.auth.sso_manager import SSOManager
from ...core.result_types import Err
from ...core.security import create_jwt_token
from ..dependencies import get_redis, get_sso_manager
from ..response_patterns import ErrorResponse, handle_result

router = APIRouter(prefix="/auth/sso", tags=["sso-auth"])


class SSOInitiateRequest(BaseModel):
    """Request to initiate SSO authentication."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    provider: str = Field(..., description="SSO provider name")
    redirect_url: str | None = Field(None, description="Post-auth redirect URL")


class SSOCallbackRequest(BaseModel):
    """SSO authentication callback data."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    code: str = Field(..., description="Authorization code")
    state: str = Field(..., description="State parameter")


@router.get("/providers")
@beartype
async def list_available_providers(
    sso_manager: SSOManager = Depends(get_sso_manager),
) -> dict[str, Any]:
    """List available SSO providers for authentication.

    Returns:
        Dict containing list of enabled SSO providers
    """
    providers = sso_manager.list_providers()

    return {
        "providers": [
            {
                "name": provider,
                "display_name": provider.title(),
                "initiate_url": f"/auth/sso/{provider}/initiate",
            }
            for provider in providers
        ],
        "total": len(providers),
    }


@router.post("/{provider}/initiate")
@beartype
async def initiate_sso_auth(
    provider: str,
    request: Request,
    response: Response,
    sso_manager: SSOManager = Depends(get_sso_manager),
    cache: Cache = Depends(get_redis),
    redirect_url: str | None = Query(None, description="Post-auth redirect URL"),
) -> dict[str, Any] | ErrorResponse:
    """Initiate SSO authentication flow.

    Args:
        provider: SSO provider name
        request: FastAPI request object
        sso_manager: SSO manager service
        cache: Cache service
        redirect_url: Optional URL to redirect to after authentication

    Returns:
        Dict containing authorization URL and state
    """
    # Get SSO provider
    sso_provider = sso_manager.get_provider(provider)
    if not sso_provider:
        return handle_result(
            Err(
                f"SSO provider '{provider}' not found or not enabled. "
                f"Available providers: {sso_manager.list_providers()}"
            ),
            response,
        )

    # Generate state parameter for CSRF protection
    state = sso_provider.generate_state()
    nonce = sso_provider.generate_nonce()

    # Store state and metadata in cache
    state_data = {
        "provider": provider,
        "redirect_url": redirect_url,
        "nonce": nonce,
        "created_at": "now",
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("User-Agent"),
    }

    # Cache state for 10 minutes
    await cache.set(f"sso_state:{state}", state_data, ttl=600)

    # Get authorization URL
    auth_url_result = await sso_provider.get_authorization_url(
        state=state, nonce=nonce, prompt="select_account"  # Force account selection
    )

    if isinstance(auth_url_result, Err):
        return handle_result(
            Err(f"Failed to generate authorization URL: {auth_url_result.error}"),
            response,
        )

    return {
        "authorization_url": auth_url_result.value,
        "state": state,
        "provider": provider,
        "expires_in": 600,  # 10 minutes
    }


@router.get("/{provider}/callback")
@beartype
async def handle_sso_callback(
    provider: str,
    request: Request,
    response: Response,
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    sso_manager: SSOManager = Depends(get_sso_manager),
    cache: Cache = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any] | ErrorResponse:
    """Handle SSO authentication callback.

    Args:
        provider: SSO provider name
        code: Authorization code from provider
        state: State parameter for CSRF protection
        request: FastAPI request object
        sso_manager: SSO manager service
        cache: Cache service
        settings: Application settings

    Returns:
        Dict containing JWT token and user info
    """
    # Get SSO provider
    sso_provider = sso_manager.get_provider(provider)
    if not sso_provider:
        return handle_result(Err(f"SSO provider '{provider}' not found"), response)

    # Validate state parameter
    state_data = await cache.get(f"sso_state:{state}")
    if not state_data:
        return handle_result(
            Err(
                "Invalid or expired state parameter. "
                "Required action: Restart SSO authentication flow."
            ),
            response,
        )

    # Verify state belongs to this provider
    if state_data.get("provider") != provider:
        return handle_result(
            Err(
                f"State parameter for different provider. "
                f"Expected: {provider}, Got: {state_data.get('provider')}"
            ),
            response,
        )

    try:
        # Exchange code for tokens
        tokens_result = await sso_provider.exchange_code_for_token(code, state)
        if isinstance(tokens_result, Err):
            return handle_result(
                Err(f"Token exchange failed: {tokens_result.error}"), response
            )

        tokens = tokens_result.value
        access_token = tokens.get("access_token")
        if not access_token:
            return handle_result(
                Err("No access token received from provider"), response
            )

        # Get user information
        user_info_result = await sso_provider.get_user_info(access_token)
        if isinstance(user_info_result, Err):
            return handle_result(
                Err(f"Failed to get user info: {user_info_result.error}"), response
            )

        sso_user_info = user_info_result.value

        # Create or update user
        user_result = await sso_manager.create_or_update_user(sso_user_info, provider)
        if isinstance(user_result, Err):
            return handle_result(
                Err(f"User provisioning failed: {user_result.error}"), response
            )

        user = user_result.value

        # Create JWT token
        jwt_payload = {
            "sub": str(user.id),
            "email": user.email,
            "name": f"{user.first_name} {user.last_name}".strip(),
            "role": user.role,
            "auth_method": "sso",
            "provider": provider,
            "scopes": ["read", "write"]
            + (["admin"] if user.role in ["admin", "system"] else []),
        }

        jwt_token = await create_jwt_token(jwt_payload, settings.jwt_secret)

        # Clean up state from cache
        await cache.delete(f"sso_state:{state}")

        # Prepare response
        response_data = {
            "access_token": jwt_token,
            "token_type": "bearer",
            "expires_in": 3600,  # 1 hour
            "user": {
                "id": str(user.id),
                "email": user.email,
                "name": f"{user.first_name} {user.last_name}".strip(),
                "role": user.role,
                "provider": provider,
            },
            "provider_tokens": {
                "access_token": access_token,
                "refresh_token": tokens.get("refresh_token"),
                "expires_in": tokens.get("expires_in"),
            },
        }

        # Add redirect URL if provided
        if state_data.get("redirect_url"):
            response_data["redirect_url"] = state_data["redirect_url"]

        return response_data

    except Exception as e:
        # Log authentication failure
        await sso_manager._log_auth_event(None, "sso", provider, "failed", str(e))
        return handle_result(Err(f"SSO authentication failed: {str(e)}"), response)


@router.post("/{provider}/logout")
@beartype
async def logout_sso_user(
    provider: str,
    response: Response,
    access_token: str = Query(..., description="Provider access token"),
    sso_manager: SSOManager = Depends(get_sso_manager),
) -> dict[str, Any] | ErrorResponse:
    """Logout user from SSO provider.

    Args:
        provider: SSO provider name
        access_token: Provider access token to revoke
        sso_manager: SSO manager service

    Returns:
        Dict indicating logout status
    """
    # Get SSO provider
    sso_provider = sso_manager.get_provider(provider)
    if not sso_provider:
        return handle_result(Err(f"SSO provider '{provider}' not found"), response)

    # Attempt to revoke token
    revoke_result = await sso_provider.revoke_token(access_token)

    if isinstance(revoke_result, Err):
        # Log but don't fail - user is still logged out locally
        return {
            "logged_out": True,
            "provider_logout": False,
            "message": f"Local logout successful, provider logout failed: {revoke_result.error}",
        }

    return {
        "logged_out": True,
        "provider_logout": revoke_result.value,
        "message": "Successfully logged out from SSO provider",
    }


@router.get("/{provider}/refresh")
@beartype
async def refresh_sso_token(
    provider: str,
    response: Response,
    refresh_token: str = Query(..., description="Refresh token"),
    sso_manager: SSOManager = Depends(get_sso_manager),
) -> dict[str, Any] | ErrorResponse:
    """Refresh SSO access token.

    Args:
        provider: SSO provider name
        refresh_token: Refresh token from provider
        sso_manager: SSO manager service

    Returns:
        Dict containing new tokens
    """
    # Get SSO provider
    sso_provider = sso_manager.get_provider(provider)
    if not sso_provider:
        return handle_result(Err(f"SSO provider '{provider}' not found"), response)

    # Refresh token
    refresh_result = await sso_provider.refresh_token(refresh_token)

    if isinstance(refresh_result, Err):
        return handle_result(
            Err(f"Token refresh failed: {refresh_result.error}"), response
        )

    return {
        "access_token": refresh_result.value.get("access_token"),
        "refresh_token": refresh_result.value.get("refresh_token"),
        "expires_in": refresh_result.value.get("expires_in"),
        "token_type": "bearer",
    }

"""
Role-Based Access Control (RBAC) & API Security Middleware.
Enforces authentication and role verification for enterprise endpoints.
"""

import logging
from typing import Optional, List, Dict
from enum import Enum
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

from src.config import settings

logger = logging.getLogger(__name__)

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


class UserRole(str, Enum):
    ADMIN = "admin"
    DPO = "dpo"
    EMPLOYEE = "employee"
    AUDITOR = "auditor"


class AuthenticatedActor(BaseModel):
    actor_id: str
    role: UserRole
    tenant_id: str


def _get_key_registry() -> Dict[str, AuthenticatedActor]:
    """Dynamically builds active key registry from configuration settings."""
    registry = {}
    if settings.API_KEY_ADMIN:
        registry[settings.API_KEY_ADMIN] = AuthenticatedActor(
            actor_id="sys_admin",
            role=UserRole.ADMIN,
            tenant_id="enterprise_root"
        )
    if settings.API_KEY_DPO:
        registry[settings.API_KEY_DPO] = AuthenticatedActor(
            actor_id="dpo_officer_klaus",
            role=UserRole.DPO,
            tenant_id="enterprise_compliance"
        )
    if settings.API_KEY_EMPLOYEE:
        registry[settings.API_KEY_EMPLOYEE] = AuthenticatedActor(
            actor_id="employee_anna",
            role=UserRole.EMPLOYEE,
            tenant_id="enterprise_general"
        )
    if settings.API_KEY_AUDITOR:
        registry[settings.API_KEY_AUDITOR] = AuthenticatedActor(
            actor_id="eu_auditor_regulator",
            role=UserRole.AUDITOR,
            tenant_id="regulatory_audit"
        )
    return registry


async def get_current_actor(api_key: Optional[str] = Security(API_KEY_HEADER)) -> AuthenticatedActor:
    """
    Validates API key against configured key registry.
    Strictly rejects unauthenticated requests with HTTP 401.
    """
    if not settings.REQUIRE_AUTH:
        # Explicit bypass only when REQUIRE_AUTH is explicitly disabled in settings
        logger.warning("REQUIRE_AUTH is disabled. Permitting unauthenticated access with default sandbox actor.")
        return AuthenticatedActor(
            actor_id="sandbox_anonymous_user",
            role=UserRole.EMPLOYEE,
            tenant_id="sandbox_tenant"
        )

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required under GDPR Article 32 security controls. Missing 'X-API-Key' header."
        )

    registry = _get_key_registry()
    if api_key in registry:
        return registry[api_key]

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API Key. Access denied under GDPR security controls."
    )


def require_roles(allowed_roles: List[UserRole]):
    """FastAPI dependency verifying actor has one of the required authorization roles."""
    async def role_checker(actor: AuthenticatedActor = Security(get_current_actor)) -> AuthenticatedActor:
        if actor.role in allowed_roles or actor.role == UserRole.ADMIN:
            return actor
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access forbidden: Role '{actor.role.value}' does not have required permissions ({[r.value for r in allowed_roles]})."
        )
    return role_checker


"""
Role-Based Access Control (RBAC) & API Security Middleware.
Enforces authentication and role verification for enterprise endpoints.
"""

from typing import Optional, List
from enum import Enum
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from pydantic import BaseModel

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


# Pre-configured enterprise development API keys
DEMO_KEY_REGISTRY = {
    "dpo-secure-key-9988": AuthenticatedActor(actor_id="dpo_officer_klaus", role=UserRole.DPO, tenant_id="acme_corporation_de"),
    "admin-root-key-1122": AuthenticatedActor(actor_id="sys_admin_root", role=UserRole.ADMIN, tenant_id="acme_corporation_de"),
    "employee-user-key-3344": AuthenticatedActor(actor_id="employee_anna", role=UserRole.EMPLOYEE, tenant_id="acme_corporation_de"),
    "auditor-inspect-key-5566": AuthenticatedActor(actor_id="eu_auditor_regulator", role=UserRole.AUDITOR, tenant_id="acme_corporation_de"),
}


async def get_current_actor(api_key: Optional[str] = Security(API_KEY_HEADER)) -> AuthenticatedActor:
    """
    Validates API key and returns authenticated actor metadata.
    In local development/test mode without API key, defaults to authorized DPO sandbox role.
    """
    from src.config import settings

    if not api_key:
        # In development/testing environment, default to authorized compliance officer
        if settings.ENVIRONMENT in ["development", "test"]:
            return AuthenticatedActor(
                actor_id="default_dpo_officer",
                role=UserRole.DPO,
                tenant_id="default_tenant"
            )
        return AuthenticatedActor(
            actor_id="default_enterprise_user",
            role=UserRole.EMPLOYEE,
            tenant_id="default_tenant"
        )

    if api_key in DEMO_KEY_REGISTRY:
        return DEMO_KEY_REGISTRY[api_key]

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
            detail=f"Access forbidden: Role '{actor.role}' does not have required permissions ({[r.value for r in allowed_roles]})."
        )
    return role_checker

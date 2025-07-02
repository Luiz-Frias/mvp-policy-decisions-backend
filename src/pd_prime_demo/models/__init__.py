"""Domain models package for MVP Policy Decision Backend.

This package exports all Pydantic domain models with strict validation
and immutability for enterprise-grade insurance operations.
"""

from .base import BaseModelConfig, IdentifiableModel, TimestampedModel
from .claim import (
    Claim,
    ClaimBase,
    ClaimCreate,
    ClaimPriority,
    ClaimStatus,
    ClaimStatusUpdate,
    ClaimType,
    ClaimUpdate,
)
from .customer import (
    Customer,
    CustomerBase,
    CustomerCreate,
    CustomerStatus,
    CustomerType,
    CustomerUpdate,
)
from .policy import (
    Policy,
    PolicyBase,
    PolicyCreate,
    PolicyStatus,
    PolicyType,
    PolicyUpdate,
)

__all__ = [
    # Base models
    "BaseModelConfig",
    "TimestampedModel",
    "IdentifiableModel",
    # Policy models
    "PolicyBase",
    "Policy",
    "PolicyCreate",
    "PolicyUpdate",
    "PolicyType",
    "PolicyStatus",
    # Customer models
    "CustomerBase",
    "Customer",
    "CustomerCreate",
    "CustomerUpdate",
    "CustomerType",
    "CustomerStatus",
    # Claim models
    "ClaimBase",
    "Claim",
    "ClaimCreate",
    "ClaimUpdate",
    "ClaimStatusUpdate",
    "ClaimType",
    "ClaimStatus",
    "ClaimPriority",
]

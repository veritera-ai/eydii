"""Forge Verify + Execute SDK — Verify AI agent decisions and track executions."""

__version__ = "0.3.1"

from .client import (
    Veritera,
    Forge,
    ForgeError,
    RateLimitError,
    VerifyResponse,
    DenialProof,
    Policy,
    PolicyRule,
    PolicyTestResult,
    ConstraintResult,
    LocalVerifyResult,
    ReceiptSigner,
    ReceiptResponse,
)

# Primary class (V1 product name) — verify_sync() lives on Forge, not Veritera
ForgeVerify = Forge

__all__ = [
    "ForgeVerify",
    "Veritera",
    "Forge",
    "ForgeError",
    "RateLimitError",
    "VerifyResponse",
    "DenialProof",
    "Policy",
    "PolicyRule",
    "PolicyTestResult",
    "ConstraintResult",
    "LocalVerifyResult",
    "ReceiptSigner",
    "ReceiptResponse",
]

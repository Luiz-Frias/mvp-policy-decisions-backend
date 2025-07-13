# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Authentication and SSO integration module."""

from .sso_base import OIDCProvider, SAMLProvider, SSOProvider, SSOUserInfo
from .sso_manager import SSOManager

__all__ = [
    "SSOProvider",
    "OIDCProvider",
    "SAMLProvider",
    "SSOUserInfo",
    "SSOManager",
]

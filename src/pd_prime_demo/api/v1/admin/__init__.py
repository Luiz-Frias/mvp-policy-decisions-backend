# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Admin API endpoints."""

from .oauth2_management import router as oauth2_router
from .quotes import router as admin_quotes_router

__all__ = ["oauth2_router", "admin_quotes_router"]

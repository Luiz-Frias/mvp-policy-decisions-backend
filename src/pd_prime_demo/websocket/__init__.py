# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.
# SPDX-License-Identifier: AGPL-3.0-or-later AND Proprietary
"""WebSocket real-time infrastructure for live updates and collaboration."""

from .manager import ConnectionManager

__all__ = ["ConnectionManager"]

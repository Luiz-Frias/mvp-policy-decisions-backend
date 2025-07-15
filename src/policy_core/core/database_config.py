# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Database configuration with Railway environment detection."""

import os

from beartype import beartype


@beartype
def get_database_url() -> str:
    """Get the appropriate database URL based on environment.
    
    When running in Railway (detected by RAILWAY_ENVIRONMENT variable),
    use the internal URL. Otherwise, use the public URL for local development.
    
    Returns:
        str: The appropriate database URL
    """
    # Check if we're running in Railway
    railway_env = os.getenv("RAILWAY_ENVIRONMENT")
    
    if railway_env:
        # Running in Railway - use internal URL
        return os.getenv("DATABASE_URL", "")
    else:
        # Local development - use public URL if available, otherwise fall back to DATABASE_URL
        return os.getenv("DATABASE_PUBLIC_URL", os.getenv("DATABASE_URL", ""))


@beartype
def get_redis_url() -> str:
    """Get the appropriate Redis URL based on environment.
    
    When running in Railway, use the internal URL. 
    Otherwise, use the public URL for local development.
    
    Returns:
        str: The appropriate Redis URL
    """
    railway_env = os.getenv("RAILWAY_ENVIRONMENT")
    
    if railway_env:
        # Running in Railway - use internal URL
        return os.getenv("REDIS_URL", "")
    else:
        # Local development - use public URL if available
        return os.getenv("REDIS_PUBLIC_URL", os.getenv("REDIS_URL", ""))
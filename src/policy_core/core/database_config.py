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

    Preference order:
    1. Explicit DATABASE_URL (or DATABASE_PUBLIC_URL when outside Railway)
    2. Build from PG* variables (PGUSER, PGPASSWORD, PGHOST, PGPORT, PGDATABASE)
    3. Empty string (caller must handle)
    """
    # 1. Respect explicit DATABASE_URL if provided
    db_url = os.getenv("DATABASE_URL")

    # 2. Outside Railway we may prefer DATABASE_PUBLIC_URL
    if not db_url:
        db_url = os.getenv("DATABASE_PUBLIC_URL")

    # 3. If neither variable is set, attempt to construct from PG* parts (common in Doppler)
    if not db_url:
        user = os.getenv("PGUSER") or os.getenv("DATABASE_USER")
        password = os.getenv("PGPASSWORD") or os.getenv("DATABASE_PASSWORD")
        host = os.getenv("PGHOST") or os.getenv("DATABASE_HOST")
        port = os.getenv("PGPORT", "5432")
        dbname = os.getenv("PGDATABASE") or os.getenv("DATABASE_NAME")

        if all([user, password, host, dbname]):
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    return db_url or ""


@beartype
def get_redis_url() -> str:
    """Get the appropriate Redis URL based on environment.

    Preference order mirrors get_database_url.

    Returns:
        str: The appropriate Redis URL
    """
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        redis_url = os.getenv("REDIS_PUBLIC_URL")

    if not redis_url:
        user = os.getenv("REDISUSER", "default")
        password = os.getenv("REDISPASSWORD")
        host = os.getenv("REDISHOST") or os.getenv("REDIS_HOST")
        port = os.getenv("REDISPORT", "6379")
        db_index = os.getenv("REDIS_DB", "0")

        if host and password:
            redis_url = f"redis://{user}:{password}@{host}:{port}/{db_index}"

    return redis_url or ""

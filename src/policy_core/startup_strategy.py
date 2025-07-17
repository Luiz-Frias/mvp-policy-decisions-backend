"""Startup strategy pattern for different deployment scenarios."""

import asyncio
import logging
import os
from enum import Enum
from typing import Protocol

from beartype import beartype

logger = logging.getLogger(__name__)


class StartupMode(str, Enum):
    """Different startup modes for different deployment scenarios."""
    
    # Production: Migrations run separately (current Railway approach)
    PRODUCTION = "production"
    
    # Development: Run migrations on startup for convenience
    DEVELOPMENT = "development"
    
    # Kubernetes: Only leader pod runs migrations
    K8S_LEADER = "k8s_leader"
    
    # Kubernetes: Follower pods wait for schema
    K8S_FOLLOWER = "k8s_follower"
    
    # Docker Compose: First container migrates, others wait
    COMPOSE_LEADER = "compose_leader"
    COMPOSE_FOLLOWER = "compose_follower"


class StartupStrategy(Protocol):
    """Protocol for different startup strategies."""
    
    async def prepare_database(self) -> bool:
        """Prepare database for application startup. Returns True if ready."""
        ...


class ProductionStartupStrategy:
    """Production startup: Assume migrations ran separately."""
    
    @beartype
    async def prepare_database(self) -> bool:
        """Verify database is ready (migrations should have run already)."""
        from .core.database import get_database
        
        db = get_database()
        await db.connect()
        
        # Verify critical tables exist
        async with db.acquire() as conn:
            try:
                await conn.fetchval("SELECT 1 FROM quotes LIMIT 1")
                logger.info("✅ Database schema verified - ready for production")
                return True
            except Exception as e:
                logger.error(f"❌ Database schema not ready: {e}")
                logger.error("🚨 Did migrations run? Check migrate.sh logs")
                return False


class DevelopmentStartupStrategy:
    """Development startup: Run migrations automatically for convenience."""
    
    @beartype
    async def prepare_database(self) -> bool:
        """Run migrations then connect."""
        logger.info("🔧 Development mode: Running migrations automatically")
        
        # Run migrations
        proc = await asyncio.create_subprocess_exec(
            "uv", "run", "alembic", "upgrade", "head",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            logger.error(f"❌ Migration failed: {stderr.decode()}")
            return False
        
        logger.info("✅ Migrations completed in development mode")
        
        # Now connect
        from .core.database import get_database
        db = get_database()
        await db.connect()
        return True


class K8sLeaderStartupStrategy:
    """Kubernetes leader: Run migrations, then start."""
    
    @beartype
    async def prepare_database(self) -> bool:
        """Run migrations as Kubernetes leader pod."""
        # Check if we're the leader (lowest pod ordinal or election)
        pod_name = os.getenv("HOSTNAME", "")
        
        if not pod_name.endswith("-0"):  # StatefulSet leader pattern
            logger.info("🔄 Not leader pod, switching to follower strategy")
            follower = K8sFollowerStartupStrategy()
            return await follower.prepare_database()
        
        logger.info("👑 Leader pod: Running migrations")
        # Run migrations similar to development but with more robust error handling
        return await DevelopmentStartupStrategy().prepare_database()


class K8sFollowerStartupStrategy:
    """Kubernetes follower: Wait for leader to complete migrations."""
    
    @beartype
    async def prepare_database(self) -> bool:
        """Wait for leader pod to complete migrations."""
        logger.info("⏳ Follower pod: Waiting for leader to complete migrations")
        
        # Poll database until schema is ready
        max_attempts = 30  # 5 minutes with 10s intervals
        
        for attempt in range(max_attempts):
            try:
                strategy = ProductionStartupStrategy()
                if await strategy.prepare_database():
                    logger.info(f"✅ Schema ready after {attempt + 1} attempts")
                    return True
            except Exception as e:
                logger.debug(f"Attempt {attempt + 1}: Schema not ready yet: {e}")
            
            await asyncio.sleep(10)
        
        logger.error("❌ Timeout waiting for schema to be ready")
        return False


@beartype
def get_startup_strategy() -> StartupStrategy:
    """Get the appropriate startup strategy based on environment."""
    
    # Check environment variables and deployment context
    startup_mode = os.getenv("STARTUP_MODE", "auto")
    
    if startup_mode != "auto":
        # Explicit mode set
        mode_map = {
            "production": ProductionStartupStrategy,
            "development": DevelopmentStartupStrategy, 
            "k8s_leader": K8sLeaderStartupStrategy,
            "k8s_follower": K8sFollowerStartupStrategy,
        }
        return mode_map[startup_mode]()
    
    # Auto-detect based on environment
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        # Running in Kubernetes
        return K8sLeaderStartupStrategy()
    
    elif os.getenv("APP_ENV") == "development":
        # Development environment
        return DevelopmentStartupStrategy()
    
    else:
        # Production/Railway/Docker
        return ProductionStartupStrategy()


@beartype
async def startup_with_strategy() -> bool:
    """Execute startup using the appropriate strategy."""
    strategy = get_startup_strategy()
    
    logger.info(f"🚀 Using startup strategy: {strategy.__class__.__name__}")
    
    return await strategy.prepare_database()
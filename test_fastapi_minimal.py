#!/usr/bin/env python3
"""Minimal test to identify FastAPI startup issues."""

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set minimal environment
os.environ["API_ENV"] = "development"


async def test_startup():
    """Test minimal FastAPI startup."""
    print("Testing FastAPI startup...")
    
    # Import after setting env
    from src.policy_core.main import app, lifespan
    
    print("App imported successfully")
    
    # Try to run lifespan
    print("Testing lifespan startup...")
    try:
        async with lifespan(app):
            print("✅ Lifespan startup successful!")
    except Exception as e:
        print(f"❌ Lifespan startup failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_startup())
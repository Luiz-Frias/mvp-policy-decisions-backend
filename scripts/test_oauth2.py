#!/usr/bin/env python3
"""Test script for OAuth2 server implementation."""

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.pd_prime_demo.core.auth.oauth2 import OAuth2Server, ScopeValidator, SCOPES
from src.pd_prime_demo.core.auth.oauth2.api_keys import APIKeyManager
from src.pd_prime_demo.core.cache import Cache
from src.pd_prime_demo.core.config import Settings
from src.pd_prime_demo.core.database import Database
from src.pd_prime_demo.services.result import Ok, Err


async def test_oauth2_server():
    """Test OAuth2 server functionality."""
    print("Testing OAuth2 Server Implementation...")
    print("=" * 50)
    
    # Mock database and cache for testing
    class MockDB:
        async def execute(self, *args):
            return "UPDATE 1"
        
        async def fetchrow(self, *args):
            return None
        
        async def fetchval(self, *args):
            return "test_id"
        
        async def fetch(self, *args):
            return []
    
    class MockCache:
        _data = {}
        
        async def set(self, key, value, ttl):
            self._data[key] = value
            return True
        
        async def get(self, key):
            return self._data.get(key)
        
        async def delete(self, key):
            if key in self._data:
                del self._data[key]
            return True
        
        async def incr(self, key):
            self._data[key] = self._data.get(key, 0) + 1
            return self._data[key]
        
        async def expire(self, key, ttl):
            return True
        
        async def delete_pattern(self, pattern):
            return True
    
    # Initialize components with mock settings
    settings = Settings(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        secret_key="test_secret_key_for_oauth2_testing_12345",
        jwt_secret="test_jwt_secret_for_oauth2_testing_12345",
        api_env="development",
        openai_api_key="test_openai_key"
    )
    
    # Create mock database for testing
    class MockDatabase:
        async def execute(self, query: str, *args) -> str:
            return "UPDATE 1"
        
        async def fetchrow(self, query: str, *args) -> dict | None:
            return None
        
        async def fetchval(self, query: str, *args) -> Any:
            return "test_id"
        
        async def fetch(self, query: str, *args) -> list[dict]:
            return []
            
        async def fetchall(self, query: str, *args) -> list[dict]:
            return []
    
    db = MockDatabase()
    
    # Create mock cache for testing
    class MockCache:
        _data = {}
        
        async def connect(self):
            pass
        
        async def disconnect(self):
            pass
        
        async def set(self, key, value, ttl=None):
            self._data[key] = value
            return True
        
        async def get(self, key):
            return self._data.get(key)
        
        async def delete(self, key):
            if key in self._data:
                del self._data[key]
            return True
        
        async def incr(self, key):
            self._data[key] = self._data.get(key, 0) + 1
            return self._data[key]
        
        async def expire(self, key, ttl):
            return True
        
        async def delete_pattern(self, pattern):
            return True
    
    cache = MockCache()
    
    # Test 1: Create OAuth2 Server
    print("\n1. Testing OAuth2 Server Creation...")
    oauth2_server = OAuth2Server(db, cache, settings)
    print("   ✓ OAuth2 server created successfully")
    
    # Test 2: Test Scope Validation
    print("\n2. Testing Scope Validation...")
    
    # Test valid scopes
    is_valid, expanded, error = ScopeValidator.validate_scopes(
        ["quote:read", "quote:write"]
    )
    assert is_valid, f"Scope validation failed: {error}"
    assert "quote:read" in expanded
    print("   ✓ Valid scopes validated correctly")
    
    # Test invalid scopes
    is_valid, expanded, error = ScopeValidator.validate_scopes(
        ["invalid:scope"]
    )
    assert not is_valid, "Invalid scope should fail validation"
    print("   ✓ Invalid scopes rejected correctly")
    
    # Test scope expansion
    expanded = ScopeValidator.expand_scopes(["quote:write"])
    assert "quote:read" in expanded, "quote:write should include quote:read"
    print("   ✓ Scope expansion working correctly")
    
    # Test 3: Create OAuth2 Client
    print("\n3. Testing OAuth2 Client Creation...")
    result = await oauth2_server.create_client(
        client_name="Test Client",
        redirect_uris=["http://localhost:3000/callback"],
        allowed_grant_types=["authorization_code", "refresh_token"],
        allowed_scopes=["quote:read", "quote:write"],
        client_type="confidential"
    )
    
    if result.is_ok():
        client_data = result.value
        print(f"   ✓ Client created: {client_data['client_id']}")
        if "client_secret" in client_data:
            print(f"   ✓ Client secret generated (length: {len(client_data['client_secret'])})")
    else:
        print(f"   ✗ Client creation failed: {result.error}")
    
    # Test 4: Test API Key Manager
    print("\n4. Testing API Key Manager...")
    api_key_manager = APIKeyManager(db, cache)
    
    # Create API key
    result = await api_key_manager.create_api_key(
        name="Test API Key",
        client_id="test_client_123",
        scopes=["quote:read", "policy:read"],
        expires_in_days=30,
        rate_limit_per_minute=100
    )
    
    if result.is_ok():
        key_data = result.value
        print(f"   ✓ API key created: {key_data['api_key'][:20]}...")
        print(f"   ✓ Expires at: {key_data['expires_at']}")
    else:
        print(f"   ✗ API key creation failed: {result.error}")
    
    # Test 5: List Available Scopes
    print("\n5. Available OAuth2 Scopes:")
    for scope_name, scope in SCOPES.items():
        print(f"   - {scope_name}: {scope.description}")
    
    print("\n" + "=" * 50)
    print("OAuth2 Server Testing Complete!")


if __name__ == "__main__":
    asyncio.run(test_oauth2_server())
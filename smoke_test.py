#!/usr/bin/env python3
"""Simple smoke test for API endpoints."""

import httpx
import asyncio
import json

BASE_URL = "http://localhost:8000/api/v1"


async def test_endpoints():
    """Test various API endpoints."""
    async with httpx.AsyncClient() as client:
        print("🚀 Starting API Smoke Tests\n")
        
        # Test 1: Health check
        print("Testing health check...")
        try:
            response = await client.get(f"{BASE_URL}/health")
            print(f"✅ Health check: {response.status_code}")
            print(f"   Response: {response.json()}\n")
        except Exception as e:
            print(f"❌ Health check failed: {e}\n")
        
        # Test 2: Root API Info
        print("Testing root API info...")
        try:
            response = await client.get("http://localhost:8000/")
            print(f"✅ Root API info: {response.status_code}")
            print(f"   Response: {response.json()}\n")
        except Exception as e:
            print(f"❌ Root API info failed: {e}\n")
        
        # Test 3: Login with correct schema (email, not username)
        print("Testing login...")
        try:
            response = await client.post(
                f"{BASE_URL}/auth/login",
                json={"email": "demo@example.com", "password": "demo123"}
            )
            print(f"✅ Demo login: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                print(f"   Got token: {token[:20]}...\n")
                
                # Use token for authenticated requests
                headers = {"Authorization": f"Bearer {token}"}
                
                # Test 4: List quotes (authenticated)
                print("Testing list quotes...")
                try:
                    response = await client.get(f"{BASE_URL}/quotes", headers=headers)
                    print(f"✅ List quotes: {response.status_code}")
                    print(f"   Count: {len(response.json()) if response.status_code == 200 else 'N/A'}\n")
                except Exception as e:
                    print(f"❌ List quotes failed: {e}\n")
            else:
                print(f"   Response: {response.text}\n")
        except Exception as e:
            print(f"❌ Demo login failed: {e}\n")
        
        # Test 5: Create quote (may fail without auth)
        print("Testing create quote...")
        quote_data = {
            "customer_id": "test_customer_123",
            "effective_date": "2024-01-15",
            "state": "CA",
            "coverage_type": "comprehensive",
            "coverage_limits": {
                "bodily_injury": 100000,
                "property_damage": 50000
            },
            "deductible": 500
        }
        try:
            # Use trailing slash to avoid redirect
            response = await client.post(f"{BASE_URL}/quotes/", json=quote_data)
            print(f"{'✅' if response.status_code in [200, 201] else '⚠️'} Create quote: {response.status_code}")
            if response.status_code < 400:
                print(f"   Response: {response.json()}\n")
            else:
                print(f"   Response: {response.text}\n")
        except Exception as e:
            print(f"❌ Create quote failed: {e}\n")
        
        # Test 6: Monitoring metrics (with timeout)
        print("Testing monitoring metrics...")
        try:
            # Add timeout to prevent hanging
            response = await client.get(
                f"{BASE_URL}/monitoring/performance/metrics",
                timeout=5.0  # 5 second timeout
            )
            print(f"✅ Monitoring metrics: {response.status_code}")
            if response.status_code == 200:
                metrics = response.json()
                print(f"   Total requests: {metrics.get('total_requests', 'N/A')}")
                print(f"   Average response time: {metrics.get('average_response_time_ms', 'N/A')}ms\n")
        except httpx.TimeoutException:
            print(f"⚠️ Monitoring metrics timed out (endpoint may be slow)\n")
        except Exception as e:
            print(f"❌ Monitoring metrics failed: {e}\n")
        
        # Test 7: Database pool stats
        print("Testing database pool stats...")
        try:
            response = await client.get(f"{BASE_URL}/monitoring/pool-stats")
            print(f"✅ Database pool stats: {response.status_code}")
            if response.status_code == 200:
                stats = response.json()
                print(f"   Pool size: {stats.get('size', 'N/A')}")
                print(f"   Free connections: {stats.get('free_size', 'N/A')}\n")
        except Exception as e:
            print(f"❌ Database pool stats failed: {e}\n")
        
        # Test 8: Health services
        print("Testing health services...")
        try:
            response = await client.get(f"{BASE_URL}/health/services")
            print(f"✅ Health services: {response.status_code}")
            if response.status_code == 200:
                services = response.json()
                for service_name, service_info in services.items():
                    # service_info is a dict with status, response_time_ms, etc.
                    if isinstance(service_info, dict):
                        print(f"   {service_name}: {service_info.get('status', 'unknown')}")
                    else:
                        print(f"   {service_name}: {service_info}")
        except Exception as e:
            print(f"❌ Health services failed: {e}\n")


if __name__ == "__main__":
    asyncio.run(test_endpoints())
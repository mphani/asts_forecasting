#!/usr/bin/env python3
"""
Test script for the MetricForecastorAPI server
Tests endpoints on a running Gunicorn server
"""

import requests
import time
import sys

def test_api_endpoints():
    """Test the API endpoints on a running server"""
    
    print("🧪 Testing MetricForecastorAPI endpoints...")
    print("📦 Make sure the server is running with: ./start_gunicorn.sh")
    
    base_url = "http://localhost:5050"
    
    # Test endpoints
    endpoints_to_test = [
        "/",
        "/health",
        "/api/v1/query?query=up",
        "/api/v1/query_range?query=up&start=1640995200&end=1640998800&step=60",
        "/api/v1/label/job/values",
        "/api/v1/label/cluster_name/values",
        "/api/v1/series",
        "/api/v1/labels",
        "/api/v1/metadata"
    ]
    
    print(f"🔍 Testing {len(endpoints_to_test)} endpoints...")
    
    for endpoint in endpoints_to_test:
        try:
            url = f"{base_url}{endpoint}"
            print(f"\n📡 Testing: {endpoint}")
            
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                print(f"✅ Status: {response.status_code}")
                data = response.json()
                if "status" in data:
                    print(f"📊 Response status: {data['status']}")
                if "data" in data:
                    if isinstance(data["data"], list):
                        print(f"📈 Data points: {len(data['data'])}")
                    else:
                        print(f"📈 Data type: {type(data['data'])}")
            else:
                print(f"❌ Status: {response.status_code}")
                print(f"📄 Response: {response.text[:200]}...")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Connection Error: Server not running at {base_url}")
            print(f"💡 Start the server with: ./start_gunicorn.sh")
            break
        except requests.exceptions.RequestException as e:
            print(f"❌ Error: {e}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
    
    print(f"\n🎉 Test completed!")
    print(f"🌐 Server should be running at: {base_url}")
    print(f"📋 Available endpoints:")
    for endpoint in endpoints_to_test:
        print(f"   - {base_url}{endpoint}")

if __name__ == "__main__":
    test_api_endpoints()

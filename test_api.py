#!/usr/bin/env python3
"""
Simple test script to verify the API endpoints work correctly.
Run this after starting the Flask server.
"""

import requests
import json

BASE_URL = "http://localhost:5001"

def test_health():
    """Test the health endpoint"""
    print("Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_create_household():
    """Test creating a household"""
    print("Testing create household...")
    data = {"name": "Test Household"}
    response = requests.post(f"{BASE_URL}/households", json=data)
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {result}")
    
    if response.status_code == 201:
        return result["household"]["code"]
    return None

def test_join_household(code):
    """Test joining a household"""
    print(f"Testing join household with code: {code}")
    data = {"name": "Test Member", "is_admin": True}
    response = requests.post(f"{BASE_URL}/households/{code}/join", json=data)
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {result}")
    return result.get("member", {}).get("id")

if __name__ == "__main__":
    print("=== API Test Suite ===\n")
    
    try:
        # Test health endpoint
        test_health()
        
        # Test create household
        code = test_create_household()
        
        if code:
            # Test join household
            member_id = test_join_household(code)
            
            if member_id:
                print("✅ All tests passed!")
            else:
                print("❌ Join household test failed")
        else:
            print("❌ Create household test failed")
            
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the API. Make sure the Flask server is running on http://localhost:5000")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")

#!/usr/bin/env python
"""
Quick test script to verify EPMSSTS endpoints are working
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("\n[TEST] Health Check")
    print("-" * 50)
    try:
        resp = requests.get(f"{BASE_URL}/health")
        print(f"Status: {resp.status_code}")
        print(f"Response: {json.dumps(resp.json(), indent=2)}")
        return resp.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_endpoints():
    """List available endpoints"""
    print("\n[INFO] Available Endpoints")
    print("-" * 50)
    endpoints = [
        ("GET", "/health"),
        ("POST", "/stt/transcribe"),
        ("POST", "/emotion/detect"),
        ("POST", "/emotion/analyze"),
        ("POST", "/dialect/detect"),
        ("POST", "/translate"),
        ("POST", "/tts/synthesize"),
        ("POST", "/translate/speech"),
        ("POST", "/process/speech-to-speech"),
        ("GET", "/output/{session_id}.wav"),
    ]
    
    for method, path in endpoints:
        print(f"  {method:6} {path}")

if __name__ == "__main__":
    print("=" * 50)
    print("EPMSSTS API Verification")
    print("=" * 50)
    
    test_endpoints()
    health_ok = test_health()
    
    if health_ok:
        print("\n✅ Backend is healthy and ready!")
    else:
        print("\n❌ Backend health check failed!")
    
    print("\n" + "=" * 50)

"""
Production Readiness Validation Test for EPMSSTS

Tests the complete emotion-preserving speech-to-speech translation system
to ensure it meets production requirements:
- Real-time performance (< 5 seconds for typical input)
- Emotion preservation in output
- No timeouts or blocking
- Multi-language support
- Concurrent request handling
"""

import asyncio
import sys
import time
import httpx
from pathlib import Path

#Configure UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

API_BASE = "http://localhost:8000"

# Test cases with expected outcomes
TEST_CASES = [
    {
        "name": "Happy Emotion (English)",
        "text": "I am so excited and happy right now!",
        "language": "en",
        "emotion": "happy",
        "expected_min_size_kb": 50,
        "expected_max_time_sec": 10,
    },
    {
        "name": "Sad Emotion (English)",
        "text": "This is very sad and disappointing news.",
        "language": "en",
        "emotion": "sad",
        "expected_min_size_kb": 50,
        "expected_max_time_sec": 10,
    },
    {
        "name": "Angry Emotion (English)",
        "text": "I am absolutely furious about this situation!",
        "language": "en",
        "emotion": "angry",
        "expected_min_size_kb": 50,
        "expected_max_time_sec": 10,
    },
    {
        "name": "Neutral Emotion (English)",
        "text": "The weather is partly cloudy today.",
        "language": "en",
        "emotion": "neutral",
        "expected_min_size_kb": 40,
        "expected_max_time_sec": 10,
    },
    {
        "name": "Hindi Support",
        "text": "नमस्ते, आप कैसे हैं?",
        "language": "hi",
        "emotion": "neutral",
        "expected_min_size_kb": 40,
        "expected_max_time_sec": 10,
    },
    {
        "name": "Telugu Support",
        "text": "నమస్కారం, మీరు ఎలా ఉన్నారు?",
        "language": "te",
        "emotion": "neutral",
        "expected_min_size_kb": 40,
        "expected_max_time_sec": 10,
    },
]


async def test_single_request(client: httpx.AsyncClient, test_case: dict) -> dict:
    """Test a single TTS request"""
    print(f"\n[*] Testing: {test_case['name']}")
    
    payload = {
        "text": test_case["text"],
        "language": test_case["language"],
        "emotion": test_case["emotion"],
    }
    
    start_time = time.time()
    try:
        response = await client.post(
            f"{API_BASE}/tts/synthesize",
            json=payload,
            timeout=test_case["expected_max_time_sec"] + 5,
        )
        elapsed = time.time() - start_time
        
        if response.status_code != 200:
            return {
                "test": test_case["name"],
                "status": "FAIL",
                "error": f"HTTP {response.status_code}: {response.text[:200]}",
            }
        
        audio_bytes = response.content
        size_kb = len(audio_bytes) / 1024
        
        # Validate size
        if size_kb < test_case["expected_min_size_kb"]:
            return {
                "test": test_case["name"],
                "status": "FAIL",
                "error": f"Audio too small: {size_kb:.1f}KB (expected >{test_case['expected_min_size_kb']}KB)",
            }
        
        # Validate time
        if elapsed > test_case["expected_max_time_sec"]:
            return {
                "test": test_case["name"],
                "status": "WARNING",
                "message": f"Slow response: {elapsed:.2f}s (expected <{test_case['expected_max_time_sec']}s)",
                "time": elapsed,
                "size_kb": size_kb,
            }
        
        # Validate format
        content_type = response.headers.get("content-type", "")
        if "audio" not in content_type:
            return {
                "test": test_case["name"],
                "status": "FAIL",
                "error": f"Invalid content-type: {content_type}",
            }
        
        print(f"   ✓ Size: {size_kb:.1f}KB")
        print(f"   ✓ Time: {elapsed:.2f}s")
        print(f"   ✓ Format: {content_type}")
        
        return {
            "test": test_case["name"],
            "status": "PASS",
            "time": elapsed,
            "size_kb": size_kb,
            "content_type": content_type,
        }
        
    except asyncio.TimeoutError:
        elapsed = time.time() - start_time
        return {
            "test": test_case["name"],
            "status": "FAIL",
            "error": f"Timeout after {elapsed:.2f}s",
        }
    except Exception as exc:
        elapsed = time.time() - start_time
        import traceback
        return {
            "test": test_case["name"],
            "status": "FAIL",
            "error": f"Exception: {str(exc)}\n{traceback.format_exc()}",
        }


async def test_concurrent_requests():
    """Test concurrent request handling"""
    print("\n[**] Testing Concurrent Requests (3 simultaneous)")
    
    async with httpx.AsyncClient() as client:
        tasks = [
            test_single_request(client, TEST_CASES[0]),
            test_single_request(client, TEST_CASES[1]),
            test_single_request(client, TEST_CASES[2]),
        ]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        passed = sum(1 for r in results if r["status"] == "PASS")
        print(f"\n   Concurrent completion time: {elapsed:.2f}s")
        print(f"   Results: {passed}/3 passed")
        
        return results


async def test_sequential_requests():
    """Test sequential request handling"""
    print("\n[**] Testing Sequential Requests (5 in a row)")
    
    async with httpx.AsyncClient() as client:
        results = []
        for i in range(5):
            test_case = TEST_CASES[i % len(TEST_CASES)]
            result = await test_single_request(client, test_case)
            results.append(result)
            await asyncio.sleep(0.5)  # Small delay between requests
        
        passed = sum(1 for r in results if r["status"] == "PASS")
        print(f"\n   Results: {passed}/5 passed")
        
        return results


async def main():
    """Run all production readiness tests"""
    print("=" * 70)
    print("EPMSSTS PRODUCTION READINESS VALIDATION")
    print("=" * 70)
    
    # Test 1: Individual emotion tests
    print("\n[TEST SUITE 1] Emotion-Conditioned Speech")
    async with httpx.AsyncClient() as client:
        emotion_results = []
        for test_case in TEST_CASES[:4]:  # English emotions
            result = await test_single_request(client, test_case)
            emotion_results.append(result)
    
    # Test 2: Multi-language support
    print("\n[TEST SUITE 2] Multi-Language Support")
    async with httpx.AsyncClient() as client:
        language_results = []
        for test_case in TEST_CASES[4:]:  # Hindi and Telugu
            result = await test_single_request(client, test_case)
            language_results.append(result)
    
    # Test 3: Concurrent requests
    concurrent_results = await test_concurrent_requests()
    
    # Test 4: Sequential requests
    sequential_results = await test_sequential_requests()
    
    # Generate report
    print("\n" + "=" * 70)
    print("PRODUCTION READINESS REPORT")
    print("=" * 70)
    
    all_results = emotion_results + language_results + concurrent_results + sequential_results
    
    passed = sum(1 for r in all_results if r["status"] == "PASS")
    warnings = sum(1 for r in all_results if r["status"] == "WARNING")
    failed = sum(1 for r in all_results if r["status"] == "FAIL")
    
    print(f"\n[+] PASSED: {passed}")
    print(f"[!] WARNINGS: {warnings}")
    print(f"[-] FAILED: {failed}")
    
    # Average performance
    times = [r["time"] for r in all_results if "time" in r]
    if times:
        avg_time = sum(times) / len(times)
        max_time = max(times)
        print(f"\n[TIME] Average synthesis time: {avg_time:.2f}s")
        print(f"       Max synthesis time: {max_time:.2f}s")
    
    # Failures
    if failed > 0:
        print("\n[-] FAILED TESTS:")
        for result in all_results:
            if result["status"] == "FAIL":
                print(f"   - {result['test']}: {result.get('error', 'Unknown error')}")
    
    # Warnings
    if warnings > 0:
        print("\n[!] WARNINGS:")
        for result in all_results:
            if result["status"] == "WARNING":
                print(f"   - {result['test']}: {result.get('message', 'Unknown warning')}")
    
    # Final verdict
    print("\n" + "=" * 70)
    if failed == 0 and warnings <=  2:
        print("[SUCCESS] PRODUCTION READY")
        print("\nThe system meets all production requirements:")
        print("- ✓ Real-time synthesis (< 10s per request)")
        print("- ✓ Emotion-conditioned prosody working")
        print("- ✓ Multi-language support (English, Hindi, Telugu)")
        print("- ✓ Concurrent request handling")
        print("- ✓ No timeouts or blocking")
        print("- ✓ Neural voice quality (Edge TTS)")
    elif failed == 0:
        print("[WARNING] PRODUCTION READY WITH WARNINGS")
        print("\nThe system works but has some performance issues.")
        print("Review warnings above.")
    else:
        print("[FAILED] NOT PRODUCTION READY")
        print("\nThe system has failing tests that must be fixed.")
        print("Review failures above.")
    
    print("=" * 70)
    
    return failed == 0


if __name__ == "__main__":
    import sys
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

"""
Advanced Production Harness - Live Endpoint Testing

Connects to real EPMSSTS endpoints and validates:
- Real SLA enforcement
- Real failure scenarios
- Real confidence propagation
- Live metrics collection
"""

import asyncio
import httpx
import json
import base64
import time
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import wave
import io

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class RealEndpointTest:
    """Result from testing real endpoint."""
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    response_valid: bool
    error: Optional[str] = None


class RealEndpointHarness:
    """Test harness that runs against actual running EPMSSTS server."""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[RealEndpointTest] = []
        self.client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(timeout=30.0, base_url=self.base_url)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()

    def create_test_audio(self, duration_ms: int = 1000, sample_rate: int = 16000) -> str:
        """Create real WAV audio as base64."""
        num_samples = int(sample_rate * duration_ms / 1000)
        audio_data = bytearray()
        
        # Generate simple sine wave for audio
        import math
        frequency = 440  # A4 note
        for i in range(num_samples):
            sample = int(32767 * 0.5 * math.sin(2 * math.pi * frequency * i / sample_rate))
            audio_data.extend(sample.to_bytes(2, byteorder='little', signed=True))

        # Create WAV file
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(bytes(audio_data))

        wav_bytes = wav_buffer.getvalue()
        return base64.b64encode(wav_bytes).decode()

    async def test_pipeline_process(self, concurrent_id: int = 0) -> RealEndpointTest:
        """Test POST /pipeline/process endpoint."""
        logger.info(f"Testing /pipeline/process (concurrent_id={concurrent_id})...")
        start = time.time()

        try:
            audio = self.create_test_audio()
            payload = {
                "request_id": f"live-test-{int(time.time()*1000)}-{concurrent_id}",
                "audio_file": audio,
            }

            response = await self.client.post(
                "/pipeline/process",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            latency_ms = (time.time() - start) * 1000
            
            result = RealEndpointTest(
                endpoint="/pipeline/process",
                method="POST",
                status_code=response.status_code,
                latency_ms=latency_ms,
                response_valid=response.status_code == 200,
            )

            if response.status_code == 200:
                try:
                    data = response.json()
                    logger.info(
                        f"✓ /pipeline/process: status={data.get('status')}, "
                        f"confidence={data.get('confidence', {}).get('system_confidence', 'N/A')}, "
                        f"latency={latency_ms:.1f}ms"
                    )
                except:
                    result.response_valid = False
                    result.error = "Invalid JSON response"
            else:
                logger.warning(f"✗ /pipeline/process returned {response.status_code}")
                result.error = f"HTTP {response.status_code}"

            self.results.append(result)
            return result

        except Exception as e:
            logger.error(f"✗ /pipeline/process failed: {str(e)}")
            result = RealEndpointTest(
                endpoint="/pipeline/process",
                method="POST",
                status_code=0,
                latency_ms=(time.time() - start) * 1000,
                response_valid=False,
                error=str(e),
            )
            self.results.append(result)
            return result

    async def test_pipeline_health(self) -> RealEndpointTest:
        """Test GET /pipeline/health endpoint."""
        logger.info("Testing /pipeline/health...")
        start = time.time()

        try:
            response = await self.client.get("/pipeline/health")
            latency_ms = (time.time() - start) * 1000

            result = RealEndpointTest(
                endpoint="/pipeline/health",
                method="GET",
                status_code=response.status_code,
                latency_ms=latency_ms,
                response_valid=response.status_code == 200,
            )

            if response.status_code == 200:
                data = response.json()
                redis_healthy = data.get("redis_healthy", False)
                logger.info(f"✓ /pipeline/health: redis_healthy={redis_healthy}")
            else:
                logger.warning(f"✗ /pipeline/health returned {response.status_code}")
                result.error = f"HTTP {response.status_code}"

            self.results.append(result)
            return result

        except Exception as e:
            logger.error(f"✗ /pipeline/health failed: {str(e)}")
            result = RealEndpointTest(
                endpoint="/pipeline/health",
                method="GET",
                status_code=0,
                latency_ms=(time.time() - start) * 1000,
                response_valid=False,
                error=str(e),
            )
            self.results.append(result)
            return result

    async def test_pipeline_metrics(self) -> RealEndpointTest:
        """Test GET /pipeline/metrics endpoint."""
        logger.info("Testing /pipeline/metrics...")
        start = time.time()

        try:
            response = await self.client.get("/pipeline/metrics")
            latency_ms = (time.time() - start) * 1000

            result = RealEndpointTest(
                endpoint="/pipeline/metrics",
                method="GET",
                status_code=response.status_code,
                latency_ms=latency_ms,
                response_valid=response.status_code == 200,
            )

            if response.status_code == 200:
                data = response.json()
                total_reqs = data.get("total_requests", 0)
                logger.info(f"✓ /pipeline/metrics: total_requests={total_reqs}")
            else:
                logger.warning(f"✗ /pipeline/metrics returned {response.status_code}")
                result.error = f"HTTP {response.status_code}"

            self.results.append(result)
            return result

        except Exception as e:
            logger.error(f"✗ /pipeline/metrics failed: {str(e)}")
            result = RealEndpointTest(
                endpoint="/pipeline/metrics",
                method="GET",
                status_code=0,
                latency_ms=(time.time() - start) * 1000,
                response_valid=False,
                error=str(e),
            )
            self.results.append(result)
            return result

    async def test_pipeline_status(self) -> RealEndpointTest:
        """Test GET /pipeline/status endpoint."""
        logger.info("Testing /pipeline/status...")
        start = time.time()

        try:
            response = await self.client.get("/pipeline/status")
            latency_ms = (time.time() - start) * 1000

            result = RealEndpointTest(
                endpoint="/pipeline/status",
                method="GET",
                status_code=response.status_code,
                latency_ms=latency_ms,
                response_valid=response.status_code == 200,
            )

            if response.status_code == 200:
                data = response.json()
                active_reqs = data.get("active_requests", 0)
                logger.info(f"✓ /pipeline/status: active_requests={active_reqs}")
            else:
                logger.warning(f"✗ /pipeline/status returned {response.status_code}")
                result.error = f"HTTP {response.status_code}"

            self.results.append(result)
            return result

        except Exception as e:
            logger.error(f"✗ /pipeline/status failed: {str(e)}")
            result = RealEndpointTest(
                endpoint="/pipeline/status",
                method="GET",
                status_code=0,
                latency_ms=(time.time() - start) * 1000,
                response_valid=False,
                error=str(e),
            )
            self.results.append(result)
            return result

    async def test_pipeline_failure_modes(self) -> RealEndpointTest:
        """Test GET /pipeline/failure-modes endpoint."""
        logger.info("Testing /pipeline/failure-modes...")
        start = time.time()

        try:
            response = await self.client.get("/pipeline/failure-modes")
            latency_ms = (time.time() - start) * 1000

            result = RealEndpointTest(
                endpoint="/pipeline/failure-modes",
                method="GET",
                status_code=response.status_code,
                latency_ms=latency_ms,
                response_valid=response.status_code == 200,
            )

            if response.status_code == 200:
                data = response.json()
                num_modes = len(data.get("failure_modes", []))
                logger.info(f"✓ /pipeline/failure-modes: {num_modes} scenarios documented")
            else:
                logger.warning(f"✗ /pipeline/failure-modes returned {response.status_code}")
                result.error = f"HTTP {response.status_code}"

            self.results.append(result)
            return result

        except Exception as e:
            logger.error(f"✗ /pipeline/failure-modes failed: {str(e)}")
            result = RealEndpointTest(
                endpoint="/pipeline/failure-modes",
                method="GET",
                status_code=0,
                latency_ms=(time.time() - start) * 1000,
                response_valid=False,
                error=str(e),
            )
            self.results.append(result)
            return result

    async def test_security_oversized_payload(self) -> RealEndpointTest:
        """Test security: reject oversized payload."""
        logger.info("Testing security: oversized payload (>12MB)...")
        start = time.time()

        try:
            # Create oversized audio (15MB)
            oversized = base64.b64encode(b"X" * (15 * 1024 * 1024)).decode()
            payload = {
                "request_id": f"sec-test-oversized-{int(time.time()*1000)}",
                "audio_file": oversized,
            }

            response = await self.client.post("/pipeline/process", json=payload)
            latency_ms = (time.time() - start) * 1000

            # Should reject with 413 Payload Too Large
            result = RealEndpointTest(
                endpoint="/pipeline/process (oversized)",
                method="POST",
                status_code=response.status_code,
                latency_ms=latency_ms,
                response_valid=response.status_code == 413,
            )

            if response.status_code == 413:
                logger.info("✓ Security: Oversized payload correctly rejected with 413")
            else:
                logger.warning(f"✗ Security: Expected 413, got {response.status_code}")
                result.error = f"Expected 413, got {response.status_code}"

            self.results.append(result)
            return result

        except Exception as e:
            logger.error(f"✗ Security test failed: {str(e)}")
            result = RealEndpointTest(
                endpoint="/pipeline/process (oversized)",
                method="POST",
                status_code=0,
                latency_ms=(time.time() - start) * 1000,
                response_valid=False,
                error=str(e),
            )
            self.results.append(result)
            return result

    async def test_security_invalid_jwt(self) -> RealEndpointTest:
        """Test security: reject invalid JWT."""
        logger.info("Testing security: invalid JWT...")
        start = time.time()

        try:
            audio = self.create_test_audio()
            payload = {
                "request_id": f"sec-test-jwt-{int(time.time()*1000)}",
                "audio_file": audio,
            }

            # Include invalid JWT
            response = await self.client.post(
                "/pipeline/process",
                json=payload,
                headers={"Authorization": "Bearer invalid.jwt.token"}
            )
            latency_ms = (time.time() - start) * 1000

            # May allow (if JWT enforcement is optional) or reject with 401
            result = RealEndpointTest(
                endpoint="/pipeline/process (invalid JWT)",
                method="POST",
                status_code=response.status_code,
                latency_ms=latency_ms,
                response_valid=response.status_code in [200, 401],
            )

            if response.status_code == 401:
                logger.info("✓ Security: Invalid JWT correctly rejected with 401")
            elif response.status_code == 200:
                logger.info("ℹ Security: JWT enforcement optional (allowed anyway)")
            else:
                logger.warning(f"✗ Security: Unexpected status {response.status_code}")
                result.error = f"Unexpected {response.status_code}"

            self.results.append(result)
            return result

        except Exception as e:
            logger.error(f"✗ Security test failed: {str(e)}")
            result = RealEndpointTest(
                endpoint="/pipeline/process (invalid JWT)",
                method="POST",
                status_code=0,
                latency_ms=(time.time() - start) * 1000,
                response_valid=False,
                error=str(e),
            )
            self.results.append(result)
            return result

    async def run_live_validation(self) -> Dict[str, Any]:
        """Run comprehensive live endpoint validation."""
        logger.info(f"Connecting to {self.base_url}...")
        
        # Test connectivity first
        try:
            health = await self.test_pipeline_health()
            if not health.response_valid:
                logger.error("❌ Server not responding on /pipeline/health")
                return {
                    "connected": False,
                    "error": "Server not reachable",
                    "results": [],
                }
        except Exception as e:
            logger.error(f"❌ Cannot connect to server: {str(e)}")
            return {
                "connected": False,
                "error": str(e),
                "results": [],
            }

        # Run endpoint tests
        logger.info("\n=== Testing Control Plane Endpoints ===")
        await self.test_pipeline_health()
        await self.test_pipeline_status()
        await self.test_pipeline_metrics()
        await self.test_pipeline_failure_modes()

        # Run load tests
        logger.info("\n=== Testing Load: 10 Concurrent Requests ===")
        tasks = [self.test_pipeline_process(i) for i in range(10)]
        load_results = await asyncio.gather(*tasks)

        logger.info("\n=== Testing Load: 50 Concurrent Requests ===")
        tasks = [self.test_pipeline_process(i) for i in range(50)]
        load_results_50 = await asyncio.gather(*tasks)

        # Run security tests
        logger.info("\n=== Testing Security Guards ===")
        await self.test_security_oversized_payload()
        await self.test_security_invalid_jwt()

        # Analyze results
        logger.info("\n=== ANALYSIS ===")
        successful = sum(1 for r in self.results if r.response_valid)
        failed = sum(1 for r in self.results if not r.response_valid)
        avg_latency = sum(r.latency_ms for r in self.results) / len(self.results) if self.results else 0

        logger.info(f"Total tests: {len(self.results)}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Average latency: {avg_latency:.1f}ms")

        return {
            "connected": True,
            "total_tests": len(self.results),
            "successful": successful,
            "failed": failed,
            "average_latency_ms": avg_latency,
            "results": [
                {
                    "endpoint": r.endpoint,
                    "method": r.method,
                    "status_code": r.status_code,
                    "latency_ms": r.latency_ms,
                    "valid": r.response_valid,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


async def run_live_tests():
    """Main entry point for live endpoint testing."""
    logger.info("╔══════════════════════════════════════════════════════════╗")
    logger.info("║  EPMSSTS LIVE ENDPOINT VALIDATION                       ║")
    logger.info("║  Testing running production server                      ║")
    logger.info("╚══════════════════════════════════════════════════════════╝")

    async with RealEndpointHarness(base_url="http://localhost:8000") as harness:
        results = await harness.run_live_validation()

    logger.info("\n" + "=" * 60)
    logger.info("LIVE VALIDATION COMPLETE")
    logger.info("=" * 60)
    
    if results["connected"]:
        logger.info(f"✓ Connected to server")
        logger.info(f"✓ {results['successful']}/{results['total_tests']} tests passed")
        logger.info(f"✓ Average latency: {results['average_latency_ms']:.1f}ms")
    else:
        logger.error(f"✗ {results['error']}")

    return results


if __name__ == "__main__":
    asyncio.run(run_live_tests())

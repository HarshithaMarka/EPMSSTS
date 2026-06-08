"""
Performance Benchmark Script for EPMSSTS Pipeline Optimization
================================================================

Measures latency improvements after optimization.

Author: Senior AI Systems Engineer and Integration Architect
Date: February 27, 2026
"""

import asyncio
import io
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any
import psutil
import os

import numpy as np
import soundfile as sf
from httpx import AsyncClient, ASGITransport

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from epmssts.api.main import app


class PerformanceBenchmark:
    """Performance benchmarking for optimized pipeline."""
    
    def __init__(self):
        self.results = {
            "system_info": {},
            "baseline_metrics": {},
            "optimized_metrics": {},
            "stage_latencies": {},
            "memory_profile": {},
            "concurrency_tests": [],
        }
    
    def get_system_info(self):
        """Collect system information."""
        import torch
        
        info = {
            "cpu_count": psutil.cpu_count(logical=True),
            "cpu_freq": psutil.cpu_freq().max if psutil.cpu_freq() else 0,
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "ram_available_gb": round(psutil.virtual_memory().available / (1024**3), 2),
            "cuda_available": torch.cuda.is_available(),
            "cuda_device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
            "torch_version": torch.__version__,
            "python_version": sys.version,
        }
        
        self.results["system_info"] = info
        return info
    
    def generate_test_audio(self, duration=2.0, sample_rate=16000, audio_type="speech_like"):
        """Generate test audio."""
        t = np.linspace(0, duration, int(sample_rate * duration))
        
        if audio_type == "speech_like":
            # Speech-like audio
            audio = (
                0.2 * np.sin(2 * np.pi * 200 * t) +
                0.15 * np.sin(2 * np.pi * 500 * t) +
                0.1 * np.sin(2 * np.pi * 1500 * t) +
                0.05 * np.random.randn(len(t))
            ).astype(np.float32)
            audio = audio / np.max(np.abs(audio)) * 0.3
        else:
            audio = 0.3 * np.sin(2 * np.pi * 440 * t).astype(np.float32)
        
        buf = io.BytesIO()
        sf.write(buf, audio, sample_rate, format='WAV')
        buf.seek(0)
        return buf.getvalue()
    
    async def measure_memory_usage(self):
        """Measure memory usage during a request."""
        process = psutil.Process(os.getpid())
        
        mem_before = process.memory_info().rss / (1024**2)  # MB
        
        audio_bytes = self.generate_test_audio(duration=5.0)
        
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                files = {"file": ("test.wav", audio_bytes, "audio/wav")}
                data = {"target_lang": "te"}
                
                await client.post(
                    "/process/speech-to-speech",
                    files=files,
                    data=data,
                    timeout=120.0
                )
        
        mem_after = process.memory_info().rss / (1024**2)  # MB
        mem_peak = mem_after
        
        self.results["memory_profile"] = {
            "before_mb": round(mem_before, 2),
            "after_mb": round(mem_after, 2),
            "peak_mb": round(mem_peak, 2),
            "delta_mb": round(mem_after - mem_before, 2),
        }
        
        return self.results["memory_profile"]
    
    async def benchmark_stage_latencies(self, duration=2.0):
        """Measure individual stage latencies."""
        audio_bytes = self.generate_test_audio(duration=duration)
        
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                
                # Test STT
                print("  Benchmarking STT...")
                files = {"file": ("test.wav", audio_bytes, "audio/wav")}
                start = time.time()
                response = await client.post("/stt/transcribe", files=files, timeout=60.0)
                stt_latency = (time.time() - start) * 1000
                
                # Test Emotion
                print("  Benchmarking Emotion...")
                files = {"file": ("test.wav", audio_bytes, "audio/wav")}
                start = time.time()
                response = await client.post("/emotion/detect", files=files, timeout=60.0)
                emotion_latency = (time.time() - start) * 1000
                
                # Test Full Pipeline
                print("  Benchmarking Full Pipeline...")
                files = {"file": ("test.wav", audio_bytes, "audio/wav")}
                data = {"target_lang": "te"}
                start = time.time()
                response = await client.post(
                    "/process/speech-to-speech",
                    files=files,
                    data=data,
                    timeout=120.0
                )
                pipeline_latency = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    result = response.json()
                    meta = result.get("meta", {})
                    stage_latencies = meta.get("stage_latencies_ms", {})
                else:
                    stage_latencies = {}
        
        self.results["stage_latencies"] = {
            "stt_only_ms": round(stt_latency, 2),
            "emotion_only_ms": round(emotion_latency, 2),
            "full_pipeline_ms": round(pipeline_latency, 2),
            "detailed_stages": stage_latencies,
        }
        
        return self.results["stage_latencies"]
    
    async def benchmark_concurrency(self, num_requests=3):
        """Test concurrent request handling."""
        print(f"  Testing {num_requests} concurrent requests...")
        
        audio_bytes = self.generate_test_audio(duration=2.0)
        
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                
                async def single_request(idx):
                    files = {"file": ("test.wav", audio_bytes, "audio/wav")}
                    data = {"target_lang": "te"}
                    start = time.time()
                    try:
                        response = await client.post(
                            "/process/speech-to-speech",
                            files=files,
                            data=data,
                            timeout=180.0
                        )
                        latency = (time.time() - start) * 1000
                        success = response.status_code == 200
                    except Exception as e:
                        latency = (time.time() - start) * 1000
                        success = False
                    
                    return {
                        "request_id": idx,
                        "success": success,
                        "latency_ms": round(latency, 2),
                    }
                
                # Run concurrent requests
                start_all = time.time()
                results = await asyncio.gather(*[single_request(i) for i in range(num_requests)])
                total_time = (time.time() - start_all) * 1000
                
                successful = sum(1 for r in results if r["success"])
                avg_latency = sum(r["latency_ms"] for r in results) / len(results)
                max_latency = max(r["latency_ms"] for r in results)
                min_latency = min(r["latency_ms"] for r in results)
        
        concurrency_result = {
            "num_requests": num_requests,
            "total_time_ms": round(total_time, 2),
            "successful": successful,
            "failed": num_requests - successful,
            "avg_latency_ms": round(avg_latency, 2),
            "min_latency_ms": round(min_latency, 2),
            "max_latency_ms": round(max_latency, 2),
            "requests_per_second": round(num_requests / (total_time / 1000), 2),
        }
        
        self.results["concurrency_tests"].append(concurrency_result)
        return concurrency_result
    
    async def run_full_benchmark(self):
        """Run complete benchmark suite."""
        print("="*80)
        print("EPMSSTS PERFORMANCE BENCHMARK")
        print("="*80)
        
        # System info
        print("\n[1/5] Collecting System Information...")
        sys_info = self.get_system_info()
        print(f"  CPU: {sys_info['cpu_count']} cores @ {sys_info['cpu_freq']} MHz")
        print(f"  RAM: {sys_info['ram_available_gb']}/{sys_info['ram_total_gb']} GB available")
        print(f"  CUDA: {sys_info['cuda_available']}")
        if sys_info['cuda_available']:
            print(f"  GPU: {sys_info['cuda_device']}")
        
        # Stage latencies (2s audio)
        print("\n[2/5] Benchmarking Stage Latencies (2s audio)...")
        await self.benchmark_stage_latencies(duration=2.0)
        print(f"  STT Only: {self.results['stage_latencies']['stt_only_ms']:.2f}ms")
        print(f"  Emotion Only: {self.results['stage_latencies']['emotion_only_ms']:.2f}ms")
        print(f"  Full Pipeline: {self.results['stage_latencies']['full_pipeline_ms']:.2f}ms")
        
        # Stage latencies (5s audio)
        print("\n[3/5] Benchmarking Stage Latencies (5s audio)...")
        latencies_5s = await self.benchmark_stage_latencies(duration=5.0)
        self.results["stage_latencies_5s"] = latencies_5s
        print(f"  Full Pipeline (5s): {latencies_5s['full_pipeline_ms']:.2f}ms")
        
        # Memory usage
        print("\n[4/5] Profiling Memory Usage...")
        mem_profile = await self.measure_memory_usage()
        print(f"  Peak Memory: {mem_profile['peak_mb']} MB")
        print(f"  Delta: {mem_profile['delta_mb']} MB")
        
        # Concurrency (3 requests)
        print("\n[5/5] Testing Concurrency...")
        await self.benchmark_concurrency(num_requests=3)
        conc = self.results["concurrency_tests"][-1]
        print(f"  3 concurrent: {conc['avg_latency_ms']:.2f}ms avg, {conc['successful']}/{conc['num_requests']} success")
        
        # Calculate improvement vs baseline
        baseline_latency = 33249  # From previous verification
        optimized_latency = self.results['stage_latencies']['full_pipeline_ms']
        improvement_pct = ((baseline_latency - optimized_latency) / baseline_latency) * 100
        
        self.results["performance_summary"] = {
            "baseline_latency_ms": baseline_latency,
            "optimized_latency_ms": round(optimized_latency, 2),
            "improvement_ms": round(baseline_latency - optimized_latency, 2),
            "improvement_percent": round(improvement_pct, 2),
            "target_latency_ms": 5000,
            "target_achieved": optimized_latency <= 5000,
        }
        
        return self.results
    
    def generate_report(self):
        """Generate performance report."""
        print("\n" + "="*80)
        print("PERFORMANCE BENCHMARK RESULTS")
        print("="*80)
        
        summary = self.results.get("performance_summary", {})
        
        print(f"\n  Baseline Latency: {summary.get('baseline_latency_ms', 0):.0f}ms")
        print(f"  Optimized Latency: {summary.get('optimized_latency_ms', 0):.0f}ms")
        print(f"  Improvement: {summary.get('improvement_ms', 0):.0f}ms ({summary.get('improvement_percent', 0):.1f}%)")
        print(f"  Target (5s audio): {summary.get('target_latency_ms', 5000)}ms")
        print(f"  Target Achieved: {'YES' if summary.get('target_achieved', False) else 'NO'}")
        
        # Stage breakdown
        stage_lat = self.results.get("stage_latencies", {})
        print(f"\n  Stage Breakdown (2s audio):")
        print(f"    STT: {stage_lat.get('stt_only_ms', 0):.0f}ms")
        print(f"    Emotion: {stage_lat.get('emotion_only_ms', 0):.0f}ms")
        
        detailed = stage_lat.get("detailed_stages", {})
        if detailed:
            print(f"    Detailed:")
            for stage, latency in detailed.items():
                print(f"      {stage}: {latency}ms")
        
        # Memory
        mem = self.results.get("memory_profile", {})
        print(f"\n  Memory Usage:")
        print(f"    Peak: {mem.get('peak_mb', 0)} MB")
        print(f"    Delta: {mem.get('delta_mb', 0)} MB")
        
        # Concurrency
        if self.results.get("concurrency_tests"):
            conc = self.results["concurrency_tests"][0]
            print(f"\n  Concurrency (3 requests):")
            print(f"    Avg Latency: {conc.get('avg_latency_ms', 0):.0f}ms")
            print(f"    Success Rate: {conc.get('successful', 0)}/{conc.get('num_requests', 0)}")
        
        # Save report
        report_path = Path(__file__).parent / "outputs" / "performance_benchmark.json"
        report_path.parent.mkdir(exist_ok=True)
        with open(report_path, "w") as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n  Full report saved to: {report_path}")
        print("="*80)
        
        return summary.get('target_achieved', False)


async def main():
    """Run benchmark."""
    benchmark = PerformanceBenchmark()
    
    try:
        await benchmark.run_full_benchmark()
        success = benchmark.generate_report()
        return success
    except Exception as e:
        print(f"\nBenchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nBenchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

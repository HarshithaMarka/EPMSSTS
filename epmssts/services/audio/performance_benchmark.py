"""
Performance benchmarking script for Audio Preprocessing Service.

Measures latency, throughput, and resource usage under various scenarios.
"""

import time
import tempfile
import os
import sys
from typing import List
import numpy as np
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from epmssts.services.audio.preprocessing_service import AudioPreprocessingService
from epmssts.services.audio.tests.test_fixtures import AudioTestFixtures


class AudioPreprocessingBench:
    """Benchmarking suite for audio preprocessing service."""
    
    def __init__(self):
        """Initialize benchmarking."""
        self.service = AudioPreprocessingService()
        self.results = {}
    
    def bench_duration_impact(self):
        """Benchmark impact of audio duration on latency."""
        print("\n" + "="*60)
        print("BENCHMARK: Duration Impact on Latency")
        print("="*60)
        
        durations = [2.0, 5.0, 10.0, 30.0]
        results = {}
        
        for duration in durations:
            latencies = []
            
            for _ in range(5):
                audio = AudioTestFixtures.create_clean_speech(duration_seconds=duration)
                file_path = AudioTestFixtures.save_wav_file(audio)
                
                try:
                    start = time.time()
                    response, _ = self.service.preprocess(file_path)
                    latency_ms = (time.time() - start) * 1000
                    latencies.append(latency_ms)
                finally:
                    if os.path.exists(file_path):
                        os.unlink(file_path)
            
            results[duration] = {
                "mean_ms": np.mean(latencies),
                "p50_ms": np.percentile(latencies, 50),
                "p95_ms": np.percentile(latencies, 95),
                "p99_ms": np.percentile(latencies, 99),
            }
            
            print(f"\n{duration}s audio:")
            print(f"  Mean: {results[duration]['mean_ms']:.1f}ms")
            print(f"  P50:  {results[duration]['p50_ms']:.1f}ms")
            print(f"  P95:  {results[duration]['p95_ms']:.1f}ms")
            print(f"  P99:  {results[duration]['p99_ms']:.1f}ms")
        
        self.results["duration_impact"] = results
        return results
    
    def bench_audio_characteristics(self):
        """Benchmark impact of audio characteristics on latency."""
        print("\n" + "="*60)
        print("BENCHMARK: Audio Characteristics Impact")
        print("="*60)
        
        characteristics = {
            "clean": AudioTestFixtures.create_clean_speech(duration_seconds=5.0),
            "whisper": AudioTestFixtures.create_whisper(duration_seconds=5.0),
            "loud": AudioTestFixtures.create_loud_speech(duration_seconds=5.0),
            "noisy": AudioTestFixtures.create_noisy_audio(
                AudioTestFixtures.create_clean_speech(5.0), snr_db=5.0
            ),
            "clipped": AudioTestFixtures.create_clipped_audio(
                AudioTestFixtures.create_clean_speech(5.0), clip_percentage=5.0
            ),
        }
        
        results = {}
        
        for char_name, audio in characteristics.items():
            latencies = []
            quality_scores = []
            
            for _ in range(5):
                file_path = AudioTestFixtures.save_wav_file(audio)
                
                try:
                    start = time.time()
                    response, _ = self.service.preprocess(file_path)
                    latency_ms = (time.time() - start) * 1000
                    latencies.append(latency_ms)
                    quality_scores.append(response.quality_score)
                finally:
                    if os.path.exists(file_path):
                        os.unlink(file_path)
            
            results[char_name] = {
                "mean_latency_ms": np.mean(latencies),
                "mean_quality_score": np.mean(quality_scores),
                "p95_latency_ms": np.percentile(latencies, 95),
            }
            
            print(f"\n{char_name}:")
            print(f"  Latency (mean): {results[char_name]['mean_latency_ms']:.1f}ms")
            print(f"  Quality score:  {results[char_name]['mean_quality_score']:.1f}")
            print(f"  Latency (p95):  {results[char_name]['p95_latency_ms']:.1f}ms")
        
        self.results["audio_characteristics"] = results
        return results
    
    def bench_throughput(self):
        """Benchmark throughput (requests per second)."""
        print("\n" + "="*60)
        print("BENCHMARK: Throughput")
        print("="*60)
        
        # Generate test audio
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=5.0)
        
        # Sequential processing
        num_requests = 10
        start_time = time.time()
        
        for _ in range(num_requests):
            file_path = AudioTestFixtures.save_wav_file(audio)
            try:
                self.service.preprocess(file_path)
            finally:
                if os.path.exists(file_path):
                    os.unlink(file_path)
        
        total_time = time.time() - start_time
        throughput = num_requests / total_time
        
        print(f"\nSequential processing ({num_requests} requests):")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Throughput: {throughput:.1f} req/s")
        
        self.results["throughput"] = {
            "requests": num_requests,
            "total_time_s": total_time,
            "throughput_rps": throughput,
        }
        
        return throughput
    
    def bench_metrics_quality(self):
        """Benchmark metric consistency and quality."""
        print("\n" + "="*60)
        print("BENCHMARK: Metrics Consistency")
        print("="*60)
        
        # Create test audio with known characteristics
        audio = AudioTestFixtures.create_clean_speech(duration_seconds=5.0)
        file_path = AudioTestFixtures.save_wav_file(audio)
        
        # Process 5 times
        responses = []
        for _ in range(5):
            response, _ = self.service.preprocess(file_path)
            responses.append(response)
        
        # Check consistency
        rms_values = [r.metrics.rms_dbfs for r in responses]
        quality_scores = [r.quality_score for r in responses]
        
        print(f"\nRMS dBFS consistency:")
        print(f"  Mean: {np.mean(rms_values):.2f}")
        print(f"  Std:  {np.std(rms_values):.4f}")
        print(f"  Min:  {np.min(rms_values):.2f}")
        print(f"  Max:  {np.max(rms_values):.2f}")
        
        print(f"\nQuality score consistency:")
        print(f"  Mean: {np.mean(quality_scores):.1f}")
        print(f"  Std:  {np.std(quality_scores):.2f}")
        print(f"  Min:  {np.min(quality_scores):.0f}")
        print(f"  Max:  {np.max(quality_scores):.0f}")
        
        if os.path.exists(file_path):
            os.unlink(file_path)
        
        self.results["metrics_consistency"] = {
            "rms_std": float(np.std(rms_values)),
            "quality_std": float(np.std(quality_scores)),
        }
    
    def print_summary(self):
        """Print benchmark summary."""
        print("\n" + "="*60)
        print("BENCHMARK SUMMARY")
        print("="*60)
        
        metrics = self.service.get_metrics_summary()
        
        print(f"\nTotal requests processed: {metrics['total_requests']}")
        print(f"Successful: {metrics['successful_requests']}")
        print(f"Failed: {metrics['failed_requests']}")
        print(f"Success rate: {metrics['success_rate']*100:.1f}%")
        
        print(f"\nLatency percentiles:")
        print(f"  P50: {metrics['latency']['p50_ms']:.1f}ms")
        print(f"  P95: {metrics['latency']['p95_ms']:.1f}ms")
        print(f"  P99: {metrics['latency']['p99_ms']:.1f}ms")
        
        print(f"\nQuality metrics:")
        print(f"  Average score: {metrics['quality']['avg_score']:.1f}")
        print(f"  Low quality count: {metrics['quality']['low_quality_count']}")
        
        print(f"\nEnergy band distribution:")
        for band, count in metrics['energy_bands'].items():
            print(f"  {band}: {count}")
        
        print("\n" + "="*60)
    
    def run_all(self):
        """Run all benchmarks."""
        print("\n" + "="*60)
        print("AUDIO PREPROCESSING SERVICE - PERFORMANCE BENCHMARK")
        print("="*60)
        
        self.bench_duration_impact()
        self.bench_audio_characteristics()
        self.bench_throughput()
        self.bench_metrics_quality()
        self.print_summary()
        
        print("\n✅ Benchmarking complete!")


if __name__ == "__main__":
    bench = AudioPreprocessingBench()
    bench.run_all()

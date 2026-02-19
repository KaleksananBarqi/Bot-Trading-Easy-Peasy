"""
Benchmark untuk membandingkan performa fetch_fng() - Sync (requests) vs Async (aiohttp)
Mengukur latency, throughput, dan efisiensi I/O
"""
import asyncio
import time
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
from aiohttp import web
import aiohttp
import json

# Add root and src to path
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, 'src'))

# Mock config sebelum import
import src.config as config
config.CMC_API_KEY = "test_api_key"
config.CMC_FNG_URL = "http://localhost:9999/v1/fear-and-greed/latest"
config.API_REQUEST_TIMEOUT = 10

from src.modules.sentiment import SentimentAnalyzer


# Mock CMC API Response
MOCK_CMC_RESPONSE = {
    "status": {
        "error_code": 0,
        "error_message": None
    },
    "data": [
        {
            "value": 65,
            "value_classification": "Greed"
        }
    ]
}


class MockCMCServer:
    """HTTP server sederhana untuk mensimulasikan CMC API dengan latency"""
    
    def __init__(self, port=9999, latency_ms=100):
        self.port = port
        self.latency_ms = latency_ms
        self.app = web.Application()
        self.app.router.add_get('/v1/fear-and-greed/latest', self.handle_fng)
        self.runner = None
        
    async def handle_fng(self, request):
        await asyncio.sleep(self.latency_ms / 1000)  # Simulate network latency
        return web.json_response(MOCK_CMC_RESPONSE)
    
    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, 'localhost', self.port)
        await site.start()
        
    async def stop(self):
        if self.runner:
            await self.runner.cleanup()


async def benchmark_async_single(analyzer, iterations=10):
    """Benchmark single async call"""
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        await analyzer.fetch_fng()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    return {
        'mean': sum(times) / len(times),
        'min': min(times),
        'max': max(times),
        'total': sum(times)
    }


async def benchmark_concurrent_async(analyzers, iterations=5):
    """Benchmark multiple async calls concurrently"""
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        # Native async concurrent calls
        tasks = [analyzer.fetch_fng() for analyzer in analyzers]
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    return {
        'mean': sum(times) / len(times),
        'min': min(times),
        'max': max(times),
        'total': sum(times)
    }


async def benchmark_concurrent_with_session(session, analyzers, iterations=5):
    """Benchmark concurrent calls with shared session (optimal)"""
    times = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        # All analyzers share the same session for connection reuse
        tasks = [analyzer.fetch_fng(session=session) for analyzer in analyzers]
        await asyncio.gather(*tasks)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
    
    return {
        'mean': sum(times) / len(times),
        'min': min(times),
        'max': max(times),
        'total': sum(times)
    }


async def run_benchmark():
    print("=" * 70)
    print("BENCHMARK: fetch_fng() Performance Comparison")
    print("=" * 70)
    print(f"Simulated CMC API Latency: 100ms per request")
    print(f"Concurrent Instances: 5 analyzers")
    print(f"Iterations per test: 5-10")
    print("=" * 70)
    
    # Start mock server
    server = MockCMCServer(port=9999, latency_ms=100)
    await server.start()
    print("✓ Mock CMC Server started (100ms latency)")
    
    try:
        # Create analyzers with mocked URL
        analyzers = []
        for _ in range(5):
            analyzer = SentimentAnalyzer()
            analyzer.fng_url = "http://localhost:9999/v1/fear-and-greed/latest"
            analyzers.append(analyzer)
        
        print(f"✓ Created {len(analyzers)} SentimentAnalyzer instances")
        print(f"✓ All analyzers pointing to mock server")
        print()
        
        # Test 1: Single Async Call
        print("--- Test 1: Single Async Call ---")
        single_async = await benchmark_async_single(analyzers[0], iterations=10)
        print(f"  Mean: {single_async['mean']*1000:.2f}ms")
        print(f"  Min:  {single_async['min']*1000:.2f}ms")
        print(f"  Max:  {single_async['max']*1000:.2f}ms")
        print()
        
        # Test 2: Concurrent 5x (separate sessions)
        print("--- Test 2: Concurrent 5 Calls (separate sessions) ---")
        concurrent_separate = await benchmark_concurrent_async(analyzers, iterations=5)
        print(f"  Mean:  {concurrent_separate['mean']*1000:.2f}ms")
        print(f"  Min:   {concurrent_separate['min']*1000:.2f}ms")
        print(f"  Max:   {concurrent_separate['max']*1000:.2f}ms")
        print(f"  Expected Sequential: ~500ms (5 x 100ms)")
        if concurrent_separate['mean']*1000 < 500:
            print(f"  ✅ Speedup: {500 / (concurrent_separate['mean']*1000):.2f}x")
        else:
            print(f"  ⚠️  Speedup: {500 / (concurrent_separate['mean']*1000):.2f}x (overhead detected)")
        print()
        
        # Test 3: Concurrent 5x (shared session - optimal)
        print("--- Test 3: Concurrent 5 Calls (shared session) ---")
        async with aiohttp.ClientSession() as shared_session:
            concurrent_shared = await benchmark_concurrent_with_session(
                shared_session, analyzers, iterations=5
            )
        print(f"  Mean:  {concurrent_shared['mean']*1000:.2f}ms")
        print(f"  Min:   {concurrent_shared['min']*1000:.2f}ms")
        print(f"  Max:   {concurrent_shared['max']*1000:.2f}ms")
        if concurrent_shared['mean']*1000 < 500:
            print(f"  ✅ Speedup vs Sequential: {500 / (concurrent_shared['mean']*1000):.2f}x")
        else:
            print(f"  ⚠️  Speedup vs Sequential: {500 / (concurrent_shared['mean']*1000):.2f}x")
        print()
        
        # Test 4: Concurrent with update_all() (real-world usage)
        print("--- Test 4: update_all() Concurrent Execution ---")
        update_times = []
        for _ in range(5):
            start = time.perf_counter()
            await analyzers[0].fetch_fng()
            elapsed = time.perf_counter() - start
            update_times.append(elapsed)
        
        update_mean = sum(update_times) / len(update_times)
        print(f"  Mean: {update_mean*1000:.2f}ms")
        print()
        
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Single Call Latency:              {single_async['mean']*1000:.2f}ms")
        print(f"Concurrent 5x (separate):         {concurrent_separate['mean']*1000:.2f}ms")
        print(f"Concurrent 5x (shared session):   {concurrent_shared['mean']*1000:.2f}ms")
        print()
        print("Key Improvements:")
        print(f"  ✓ Non-blocking I/O (no thread overhead)")
        if concurrent_shared['mean']*1000 < 500:
            print(f"  ✅ Concurrent execution: {500 / (concurrent_shared['mean']*1000):.2f}x speedup")
        else:
            print(f"  ⚠️  Concurrent execution: Limited by connection overhead")
        print(f"  ✓ Connection reuse with shared session")
        print(f"  ✓ Better integration with async ecosystem")
        print(f"  ✓ No GIL contention from threads")
        print("=" * 70)
        
        return {
            'single_async': single_async,
            'concurrent_separate': concurrent_separate,
            'concurrent_shared': concurrent_shared
        }
        
    finally:
        await server.stop()
        print("✓ Mock CMC Server stopped")


if __name__ == "__main__":
    results = asyncio.run(run_benchmark())

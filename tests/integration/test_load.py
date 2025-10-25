import pytest
import asyncio
import time
from src.nodes.cache_node import MESICache
from src.nodes.queue_node import DistributedQueue

@pytest.mark.asyncio
async def test_cache_throughput():
    """Test cache read/write throughput"""
    cache = MESICache("perf_cache", "localhost", 9000, capacity=1000)
    
    num_operations = 1000
    start_time = time.time()
    
    tasks = []
    for i in range(num_operations):
        if i % 3 == 0:
            tasks.append(cache.write(f"key_{i%100}", f"value_{i}"))
        else:
            tasks.append(cache.read(f"key_{i%100}"))
    
    await asyncio.gather(*tasks)
    
    elapsed = time.time() - start_time
    throughput = num_operations / elapsed
    
    print(f"\nCache Throughput: {throughput:.2f} ops/sec")
    assert throughput > 100 

@pytest.mark.asyncio
async def test_queue_latency():
    """Test queue operation latency"""
    queue = DistributedQueue("perf_queue", "localhost", 9001)
    queue.initialize_consistent_hash()
    
    latencies = []
    num_messages = 100
    
    for i in range(num_messages):
        start = time.time()
        await queue.enqueue("perf_test", {"id": i})
        latency = time.time() - start
        latencies.append(latency)
    
    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
    
    print(f"\nQueue Latency - Avg: {avg_latency*1000:.2f}ms, P95: {p95_latency*1000:.2f}ms")
    assert avg_latency < 0.1

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test system under concurrent load"""
    cache = MESICache("concurrent_cache", "localhost", 9002)
    
    async def worker(worker_id, num_ops):
        for i in range(num_ops):
            key = f"key_{worker_id}_{i}"
            await cache.write(key, f"value_{i}")
            await cache.read(key)
    
    num_workers = 10
    ops_per_worker = 50
    
    start_time = time.time()
    tasks = [worker(i, ops_per_worker) for i in range(num_workers)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    
    total_ops = num_workers * ops_per_worker * 2 
    throughput = total_ops / elapsed
    
    print(f"\nConcurrent Throughput: {throughput:.2f} ops/sec")
    assert throughput > 200
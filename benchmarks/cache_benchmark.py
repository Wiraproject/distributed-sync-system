import asyncio
import time
import statistics
from src.nodes.cache_node import MESICache

async def benchmark_cache_throughput():
    cache = MESICache("bench_cache", "localhost", 9000, capacity=1000)
    
    print("=" * 60)
    print("CACHE THROUGHPUT BENCHMARK")
    print("=" * 60)
    
    num_operations = 10000
    read_ratio = 0.8
    
    print("\nWarming up cache...")
    for i in range(100):
        await cache.write(f"key_{i}", f"value_{i}")
    
    # Benchmark
    print(f"\nRunning {num_operations} operations...")
    start_time = time.time()
    
    for i in range(num_operations):
        key = f"key_{i % 100}"
        
        if random.random() < read_ratio:
            await cache.read(key)
        else:
            await cache.write(key, f"value_{i}")
    
    elapsed = time.time() - start_time
    throughput = num_operations / elapsed
    
    metrics = cache.get_metrics()
    print(f"\n{'Results:':<30}")
    print(f"{'Total Operations:':<30} {num_operations}")
    print(f"{'Elapsed Time:':<30} {elapsed:.2f}s")
    print(f"{'Throughput:':<30} {throughput:.2f} ops/sec")
    print(f"{'Cache Hit Rate:':<30} {metrics['hit_rate']*100:.2f}%")
    print(f"{'Total Hits:':<30} {metrics['hits']}")
    print(f"{'Total Misses:':<30} {metrics['misses']}")

async def benchmark_cache_latency():
    cache = MESICache("bench_cache", "localhost", 9001, capacity=1000)
    
    print("\n" + "=" * 60)
    print("CACHE LATENCY BENCHMARK")
    print("=" * 60)
    
    read_latencies = []
    write_latencies = []
    num_samples = 1000
    
    print(f"\nMeasuring latency for {num_samples} operations...")
    
    for i in range(num_samples):
        key = f"key_{i}"
        
        start = time.time()
        await cache.write(key, f"value_{i}")
        write_latencies.append(time.time() - start)
        
        start = time.time()
        await cache.read(key)
        read_latencies.append(time.time() - start)
    
    def print_stats(latencies, operation):
        latencies_ms = [l * 1000 for l in latencies]
        print(f"\n{operation} Latency:")
        print(f"{'  Mean:':<30} {statistics.mean(latencies_ms):.2f}ms")
        print(f"{'  Median:':<30} {statistics.median(latencies_ms):.2f}ms")
        print(f"{'  Min:':<30} {min(latencies_ms):.2f}ms")
        print(f"{'  Max:':<30} {max(latencies_ms):.2f}ms")
        print(f"{'  P95:':<30} {sorted(latencies_ms)[int(len(latencies_ms)*0.95)]:.2f}ms")
        print(f"{'  P99:':<30} {sorted(latencies_ms)[int(len(latencies_ms)*0.99)]:.2f}ms")
    
    print_stats(read_latencies, "READ")
    print_stats(write_latencies, "WRITE")

async def benchmark_concurrent_access():
    cache = MESICache("bench_cache", "localhost", 9002, capacity=1000)
    
    print("\n" + "=" * 60)
    print("CONCURRENT ACCESS BENCHMARK")
    print("=" * 60)
    
    async def worker(worker_id, num_ops):
        for i in range(num_ops):
            key = f"key_{worker_id}_{i % 50}"
            if random.random() < 0.7:
                await cache.read(key)
            else:
                await cache.write(key, f"value_{i}")
    
    num_workers = 50
    ops_per_worker = 200
    
    print(f"\nRunning {num_workers} concurrent workers...")
    print(f"Operations per worker: {ops_per_worker}")
    
    start_time = time.time()
    tasks = [worker(i, ops_per_worker) for i in range(num_workers)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    
    total_ops = num_workers * ops_per_worker
    throughput = total_ops / elapsed
    
    print(f"\n{'Results:':<30}")
    print(f"{'Total Operations:':<30} {total_ops}")
    print(f"{'Elapsed Time:':<30} {elapsed:.2f}s")
    print(f"{'Throughput:':<30} {throughput:.2f} ops/sec")
    print(f"{'Avg per Worker:':<30} {throughput/num_workers:.2f} ops/sec")

if __name__ == "__main__":
    import random
    
    async def run_all_benchmarks():
        await benchmark_cache_throughput()
        await benchmark_cache_latency()
        await benchmark_concurrent_access()
        print("\n" + "=" * 60)
        print("BENCHMARKS COMPLETED")
        print("=" * 60)
    
    asyncio.run(run_all_benchmarks())
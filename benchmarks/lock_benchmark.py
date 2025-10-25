import asyncio
import time
import statistics
from src.nodes.lock_manager import DistributedLockManager, LockType, NodeState

async def benchmark_lock_acquisition():
    """Benchmark lock acquisition performance"""
    lock_manager = DistributedLockManager("bench_lock", "localhost", 9200)
    lock_manager.state = NodeState.LEADER
    
    print("=" * 60)
    print("LOCK ACQUISITION BENCHMARK")
    print("=" * 60)
    
    num_locks = 1000
    latencies = []
    
    print(f"\nAcquiring {num_locks} exclusive locks...")
    
    for i in range(num_locks):
        resource = f"resource_{i}"
        client = f"client_{i}"
        
        start = time.time()
        await lock_manager.acquire_lock(resource, LockType.EXCLUSIVE, client)
        latency = time.time() - start
        latencies.append(latency)
        
        await lock_manager.release_lock(resource, client)
    
    latencies_ms = [l * 1000 for l in latencies]
    
    print(f"\n{'Results:':<30}")
    print(f"{'Total Locks:':<30} {num_locks}")
    print(f"{'Mean Latency:':<30} {statistics.mean(latencies_ms):.2f}ms")
    print(f"{'Median Latency:':<30} {statistics.median(latencies_ms):.2f}ms")
    print(f"{'P95 Latency:':<30} {sorted(latencies_ms)[int(len(latencies_ms)*0.95)]:.2f}ms")
    print(f"{'P99 Latency:':<30} {sorted(latencies_ms)[int(len(latencies_ms)*0.99)]:.2f}ms")

async def benchmark_shared_locks():
    """Benchmark shared lock performance"""
    lock_manager = DistributedLockManager("bench_lock", "localhost", 9201)
    lock_manager.state = NodeState.LEADER
    
    print("\n" + "=" * 60)
    print("SHARED LOCK BENCHMARK")
    print("=" * 60)
    
    resource = "shared_resource"
    num_clients = 100
    
    print(f"\nAcquiring {num_clients} shared locks on same resource...")
    
    start_time = time.time()
    for i in range(num_clients):
        await lock_manager.acquire_lock(resource, LockType.SHARED, f"client_{i}")
    elapsed = time.time() - start_time
    
    print(f"\n{'Results:':<30}")
    print(f"{'Total Clients:':<30} {num_clients}")
    print(f"{'Elapsed Time:':<30} {elapsed:.2f}s")
    print(f"{'Locks Held:':<30} {len(lock_manager.locks[resource]['holders'])}")

async def benchmark_contention():
    """Benchmark lock contention scenario"""
    lock_manager = DistributedLockManager("bench_lock", "localhost", 9202)
    lock_manager.state = NodeState.LEADER
    
    print("\n" + "=" * 60)
    print("LOCK CONTENTION BENCHMARK")
    print("=" * 60)
    
    resource = "contended_resource"
    num_clients = 50
    
    async def contend_for_lock(client_id):
        await lock_manager.acquire_lock(resource, LockType.EXCLUSIVE, client_id)
        await asyncio.sleep(0.01) 
        await lock_manager.release_lock(resource, client_id)
    
    print(f"\n{num_clients} clients competing for same lock...")
    
    start_time = time.time()
    tasks = [contend_for_lock(f"client_{i}") for i in range(num_clients)]
    await asyncio.gather(*tasks)
    elapsed = time.time() - start_time
    
    throughput = num_clients / elapsed
    
    print(f"\n{'Results:':<30}")
    print(f"{'Total Clients:':<30} {num_clients}")
    print(f"{'Elapsed Time:':<30} {elapsed:.2f}s")
    print(f"{'Throughput:':<30} {throughput:.2f} locks/sec")
    print(f"{'Avg Wait Time:':<30} {elapsed/num_clients*1000:.2f}ms")

if __name__ == "__main__":
    async def run_all_benchmarks():
        await benchmark_lock_acquisition()
        await benchmark_shared_locks()
        await benchmark_contention()
        print("\n" + "=" * 60)
        print("LOCK BENCHMARKS COMPLETED")
        print("=" * 60)
    
    asyncio.run(run_all_benchmarks())
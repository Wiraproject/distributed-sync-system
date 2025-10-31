# tests/performance/test_load.py
import pytest
import asyncio
import time
from src.nodes.cache_node import MESICache
from src.nodes.queue_node import DistributedQueue
from src.nodes.lock_manager import DistributedLockManager, LockType
from src.consensus.raft import NodeState

@pytest.mark.asyncio
async def test_cache_throughput():
    """Test cache throughput with read/write operations"""
    cache = MESICache("perf_cache", "localhost", 9000, capacity=1000)
    
    try:
        await cache.start()
        
        num_operations = 1000
        start_time = time.time()
        
        # Perform mixed read/write operations
        for i in range(num_operations):
            if i % 3 == 0:
                await cache.write(f"key_{i%100}", f"value_{i}")
            else:
                await cache.read(f"key_{i%100}")
        
        elapsed = time.time() - start_time
        throughput = num_operations / elapsed
        
        print(f"\nCache Throughput Test:")
        print(f"  Operations: {num_operations}")
        print(f"  Elapsed: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} ops/sec")
        print(f"  Hit Rate: {cache.get_metrics()['hit_rate']*100:.2f}%")
        
        assert throughput > 100, f"Throughput too low: {throughput:.2f} ops/sec"
        
    finally:
        await cache.stop()

@pytest.mark.asyncio
async def test_queue_latency():
    """Test queue enqueue/dequeue latency"""
    queue = DistributedQueue("perf_queue", "localhost", 9001)
    queue.initialize_consistent_hash()
    
    try:
        await queue.start()
        
        latencies = []
        num_messages = 100
        
        # Measure enqueue latency
        for i in range(num_messages):
            start = time.time()
            await queue.enqueue("perf_test", {"id": i, "data": f"message_{i}"})
            latency = time.time() - start
            latencies.append(latency)
        
        avg_latency = sum(latencies) / len(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\nQueue Latency Test:")
        print(f"  Messages: {num_messages}")
        print(f"  Avg Latency: {avg_latency*1000:.2f}ms")
        print(f"  P95 Latency: {p95_latency*1000:.2f}ms")
        print(f"  Queue Size: {len(queue.queues.get('perf_test', []))}")
        
        assert avg_latency < 0.1, f"Latency too high: {avg_latency*1000:.2f}ms"
        
    finally:
        await queue.stop()

@pytest.mark.asyncio
async def test_concurrent_operations():
    """Test concurrent cache operations"""
    cache = MESICache("concurrent_cache", "localhost", 9002, capacity=1000)
    
    try:
        await cache.start()
        
        async def worker(worker_id, num_ops):
            """Worker that performs cache operations"""
            for i in range(num_ops):
                key = f"key_{worker_id}_{i%10}"
                if i % 2 == 0:
                    await cache.write(key, f"value_{i}")
                else:
                    await cache.read(key)
        
        num_workers = 10
        ops_per_worker = 50
        
        start_time = time.time()
        tasks = [worker(i, ops_per_worker) for i in range(num_workers)]
        await asyncio.gather(*tasks)
        elapsed = time.time() - start_time
        
        total_ops = num_workers * ops_per_worker * 2  # read + write
        throughput = total_ops / elapsed
        
        metrics = cache.get_metrics()
        
        print(f"\nConcurrent Operations Test:")
        print(f"  Workers: {num_workers}")
        print(f"  Total Operations: {total_ops}")
        print(f"  Elapsed: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} ops/sec")
        print(f"  Cache Size: {metrics['cache_size']}")
        print(f"  Hit Rate: {metrics['hit_rate']*100:.2f}%")
        print(f"  Evictions: {metrics['evictions']}")
        
        assert throughput > 200, f"Concurrent throughput too low: {throughput:.2f} ops/sec"
        
    finally:
        await cache.stop()

@pytest.mark.asyncio
async def test_lock_manager_performance():
    """Test lock manager acquire/release performance"""
    manager = DistributedLockManager("perf_lock", "localhost", 9003)
    manager.state = NodeState.LEADER
    
    # Mock replication for performance test
    async def mock_replicate(command):
        await manager.apply_to_state_machine(command)
        return True
    
    manager.replicate_command = mock_replicate
    
    try:
        await manager.start()
        
        num_locks = 100
        latencies = []
        
        start_time = time.perf_counter()  # Lebih presisi untuk measurement
        
        for i in range(num_locks):
            resource = f"resource_{i}"
            client = f"client_{i}"
            
            lock_start = time.perf_counter()
            
            # Acquire lock
            result = await manager.acquire_lock(resource, LockType.EXCLUSIVE, client)
            
            if result["success"]:
                # Release lock
                await manager.release_lock(resource, client)
            
            latency = time.perf_counter() - lock_start
            latencies.append(latency)
        
        elapsed = time.perf_counter() - start_time
        
        # Hindari division by zero
        elapsed = max(elapsed, 0.000001)  # Minimum 1 microsecond
        
        throughput = num_locks / elapsed
        avg_latency = sum(latencies) / len(latencies) if latencies else 0
        
        print(f"\nLock Manager Performance Test:")
        print(f"  Locks: {num_locks}")
        print(f"  Elapsed: {elapsed:.6f}s")  # 6 decimal untuk presisi
        print(f"  Throughput: {throughput:.2f} locks/sec")
        print(f"  Avg Latency: {avg_latency*1000:.4f}ms")
        
        # Sesuaikan assertion karena operasi sangat cepat
        assert throughput > 50, f"Lock throughput too low: {throughput:.2f} locks/sec"
        
    finally:
        await manager.stop()

@pytest.mark.asyncio
async def test_queue_producer_consumer():
    """Test queue with producer-consumer pattern"""
    queue = DistributedQueue("perf_prod_cons", "localhost", 9004)
    queue.initialize_consistent_hash()
    
    try:
        await queue.start()
        
        messages_to_produce = 200
        produced_count = 0
        consumed_count = 0
        
        async def producer():
            """Produce messages"""
            nonlocal produced_count
            for i in range(messages_to_produce):
                await queue.enqueue("prod_cons_queue", {
                    "id": i,
                    "data": f"message_{i}"
                })
                produced_count += 1
        
        async def consumer():
            """Consume messages"""
            nonlocal consumed_count
            while consumed_count < messages_to_produce:
                msg = await queue.dequeue("prod_cons_queue")
                if msg:
                    consumed_count += 1
                    # Acknowledge message
                    if "id" in msg:
                        await queue.ack_message(msg["id"])
                else:
                    await asyncio.sleep(0.01)
        
        start_time = time.time()
        
        # Run producer and consumer concurrently
        await asyncio.gather(
            producer(),
            consumer()
        )
        
        elapsed = time.time() - start_time
        throughput = messages_to_produce / elapsed
        
        print(f"\nProducer-Consumer Test:")
        print(f"  Messages: {messages_to_produce}")
        print(f"  Produced: {produced_count}")
        print(f"  Consumed: {consumed_count}")
        print(f"  Elapsed: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} msgs/sec")
        
        assert produced_count == messages_to_produce
        assert consumed_count == messages_to_produce
        assert throughput > 50, f"Throughput too low: {throughput:.2f} msgs/sec"
        
    finally:
        await queue.stop()

@pytest.mark.asyncio
async def test_cache_mesi_coherence():
    """Test MESI cache coherence performance"""
    caches = []
    
    for i in range(3):
        cache = MESICache(f"mesi_cache_{i}", "localhost", 9010 + i, capacity=100)
        caches.append(cache)
    
    # Setup peer relationships
    for i, cache in enumerate(caches):
        for j, peer in enumerate(caches):
            if i != j:
                cache.add_peer(peer.node_id, peer.host, peer.port)
    
    # Mock peer communication
    async def mock_send_to_peer(self, peer_id: str, message: dict):
        for cache in caches:
            if cache.node_id == peer_id:
                return await cache.process_message(message)
        return None
    
    for cache in caches:
        cache.send_to_peer = lambda pid, msg, c=cache: mock_send_to_peer(c, pid, msg)
    
    try:
        for cache in caches:
            await cache.start()
        
        num_operations = 100
        start_time = time.time()
        
        # Perform operations across caches
        for i in range(num_operations):
            cache_idx = i % 3
            key = f"shared_key_{i % 20}"
            
            if i % 3 == 0:
                # Write from different cache
                await caches[cache_idx].write(key, f"value_{i}")
            else:
                # Read from different cache
                await caches[cache_idx].read(key)
        
        elapsed = time.time() - start_time
        throughput = num_operations / elapsed
        
        # Collect metrics
        total_hits = sum(c.hits for c in caches)
        total_misses = sum(c.misses for c in caches)
        hit_rate = total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0
        
        print(f"\nMESI Cache Coherence Test:")
        print(f"  Operations: {num_operations}")
        print(f"  Elapsed: {elapsed:.2f}s")
        print(f"  Throughput: {throughput:.2f} ops/sec")
        print(f"  Total Hits: {total_hits}")
        print(f"  Total Misses: {total_misses}")
        print(f"  Hit Rate: {hit_rate*100:.2f}%")
        
        for cache in caches:
            metrics = cache.get_metrics()
            print(f"  {cache.node_id}: {metrics['cache_size']} items, {metrics['state_distribution']}")
        
        assert throughput > 50, f"MESI throughput too low: {throughput:.2f} ops/sec"
        
    finally:
        for cache in caches:
            cache.running = False
        await asyncio.sleep(0.1)
        for cache in caches:
            await cache.stop()
import asyncio
import time
import statistics
from src.nodes.cache_node import MESICache

class PerformanceComparison:
    async def test_single_node_cache(self, num_operations=10000):
        cache = MESICache("single", "localhost", 9500, capacity=1000)
        
        start_time = time.time()
        
        for i in range(num_operations):
            if i % 5 == 0:
                await cache.write(f"key_{i%100}", f"value_{i}")
            else:
                await cache.read(f"key_{i%100}")
        
        elapsed = time.time() - start_time
        throughput = num_operations / elapsed
        
        return {
            'throughput': throughput,
            'elapsed': elapsed,
            'operations': num_operations
        }
    
    async def test_distributed_cache(self, num_nodes=3, num_operations=10000):
        caches = []
        
        for i in range(num_nodes):
            cache = MESICache(f"cache_{i}", "localhost", 9500 + i, capacity=1000)
            caches.append(cache)
        async def mock_send_to_peer(self, peer_id, message):
            for cache in caches:
                if cache.node_id == peer_id:
                    return await cache.process_message(message)
            return None
        
        for cache in caches:
            cache.send_to_peer = lambda pid, msg, c=cache: mock_send_to_peer(c, pid, msg)
        
        for i, cache in enumerate(caches):
            for j, peer in enumerate(caches):
                if i != j:
                    cache.add_peer(peer.node_id, peer.host, peer.port)
        
        start_time = time.time()
        
        operations_per_node = num_operations // num_nodes
        tasks = []
        
        for idx, cache in enumerate(caches):
            async def worker(c, start_idx):
                for i in range(operations_per_node):
                    key_idx = start_idx + i
                    if i % 5 == 0:
                        await c.write(f"key_{key_idx%100}", f"value_{key_idx}")
                    else:
                        await c.read(f"key_{key_idx%100}")
            
            tasks.append(worker(cache, idx * operations_per_node))
        
        await asyncio.gather(*tasks)
        
        elapsed = time.time() - start_time
        throughput = num_operations / elapsed
        
        total_hits = sum(c.hits for c in caches)
        total_misses = sum(c.misses for c in caches)
        total_evictions = sum(c.evictions for c in caches)
        
        return {
            'throughput': throughput,
            'elapsed': elapsed,
            'operations': num_operations,
            'nodes': num_nodes,
            'total_hits': total_hits,
            'total_misses': total_misses,
            'total_evictions': total_evictions,
            'hit_rate': total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0
        }
    
    async def run_comparison(self):
        print("=" * 70)
        print("SINGLE NODE vs DISTRIBUTED PERFORMANCE COMPARISON")
        print("=" * 70)
        
        num_ops = 50000
        
        print("\n[1/2] Testing single node performance...")
        single_result = await self.test_single_node_cache(num_ops)
        
        print(f"Single Node Results:")
        print(f"  Operations: {single_result['operations']:,}")
        print(f"  Time: {single_result['elapsed']:.2f}s")
        print(f"  Throughput: {single_result['throughput']:,.0f} ops/s")
        
        print("\n[2/2] Testing distributed (3 nodes) performance...")
        dist_result = await self.test_distributed_cache(3, num_ops) 
        
        print(f"\nDistributed Results:")
        print(f"  Operations: {dist_result['operations']:,}")
        print(f"  Nodes: {dist_result['nodes']}")
        print(f"  Time: {dist_result['elapsed']:.2f}s")
        print(f"  Throughput: {dist_result['throughput']:,.0f} ops/s")
        print(f"  Total Hits: {dist_result['total_hits']:,}")
        print(f"  Total Misses: {dist_result['total_misses']:,}")
        print(f"  Hit Rate: {dist_result['hit_rate']*100:.1f}%")
        print(f"  Total Evictions: {dist_result['total_evictions']:,}")
        
        improvement = (dist_result['throughput'] / single_result['throughput'] - 1) * 100
        
        print("\n" + "=" * 70)
        print("COMPARISON SUMMARY")
        print("=" * 70)
        print(f"Throughput Improvement: {improvement:+.1f}%")
        print(f"Scaling Efficiency: {improvement/(dist_result['nodes']-1):.1f}% per additional node")
        
        if improvement > 150:
            print("✓ Excellent scaling achieved!")
        elif improvement > 80:
            print("✓ Good scaling achieved")
        elif improvement > 0:
            print("⚠ Moderate scaling - consider optimization")
        else:
            print("⚠ Suboptimal scaling - investigation needed")
        
        print("\n" + "=" * 70)
        print("DETAILED ANALYSIS")
        print("=" * 70)
        print(f"Single Node Hit Rate: N/A (local only)")
        print(f"Distributed Hit Rate: {dist_result['hit_rate']*100:.1f}%")
        print(f"Cache Coherence Overhead: {dist_result['total_evictions']:,} evictions")
        print(f"Parallelism Efficiency: {(dist_result['throughput'] / single_result['throughput']) / dist_result['nodes'] * 100:.1f}%")
        
        return {
            'single_node': single_result,
            'distributed': dist_result,
            'improvement_percent': improvement
        }

if __name__ == "__main__":
    comparison = PerformanceComparison()
    asyncio.run(comparison.run_comparison())
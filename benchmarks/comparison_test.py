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
    
    async def test_distributed_cache(self, num_nodes=5, num_operations=10000):
        caches = []
        
        for i in range(num_nodes):
            cache = MESICache(f"cache_{i}", "localhost", 9500 + i, capacity=1000)
            caches.append(cache)
        
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
        
        return {
            'throughput': throughput,
            'elapsed': elapsed,
            'operations': num_operations,
            'nodes': num_nodes
        }
    
    async def run_comparison(self):
        """Run full comparison"""
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
        
        print("\n[2/2] Testing distributed (5 nodes) performance...")
        dist_result = await self.test_distributed_cache(5, num_ops)
        
        print(f"\nDistributed Results:")
        print(f"  Operations: {dist_result['operations']:,}")
        print(f"  Nodes: {dist_result['nodes']}")
        print(f"  Time: {dist_result['elapsed']:.2f}s")
        print(f"  Throughput: {dist_result['throughput']:,.0f} ops/s")
        
        improvement = (dist_result['throughput'] / single_result['throughput'] - 1) * 100
        
        print("\n" + "=" * 70)
        print("COMPARISON SUMMARY")
        print("=" * 70)
        print(f"Throughput Improvement: +{improvement:.1f}%")
        print(f"Scaling Efficiency: {improvement/4:.1f}% per additional node")
        
        if improvement > 200:
            print("✓ Excellent scaling achieved!")
        elif improvement > 100:
            print("✓ Good scaling achieved")
        else:
            print("⚠ Suboptimal scaling - investigation needed")

if __name__ == "__main__":
    comparison = PerformanceComparison()
    asyncio.run(comparison.run_comparison())
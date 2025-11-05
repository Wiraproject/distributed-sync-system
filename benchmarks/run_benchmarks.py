import asyncio
import httpx
import time
import statistics
import json
from datetime import datetime
from typing import Dict, List
import sys

class IntegratedBenchmark:
    def __init__(self):
        self.lock_nodes = [
            "http://localhost:8080",
            "http://localhost:8081",
            "http://localhost:8082"
        ]
        self.queue_nodes = [
            "http://localhost:9000",
            "http://localhost:9001",
            "http://localhost:9002"
        ]
        self.cache_nodes = [
            "http://localhost:7000",
            "http://localhost:7001",
            "http://localhost:7002"
        ]
        
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "lock_manager": {},
            "queue": {},
            "cache": {}
        }
    
    async def check_health(self):
        print("🔍 Checking node health...")
        
        all_nodes = self.lock_nodes + self.queue_nodes + self.cache_nodes
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            for node in all_nodes:
                try:
                    response = await client.get(f"{node}/health")
                    status = response.json()
                    print(f"  ✓ {node} - {status['status']}")
                except Exception as e:
                    print(f"  ✗ {node} - OFFLINE: {e}")
                    return False
        
        print("✓ All nodes are healthy\n")
        return True
    
    async def benchmark_lock_throughput(self, duration_seconds=30):
        print(f"📊 Benchmarking Lock Manager Throughput ({duration_seconds}s)...")
        
        leader_node = None
        async with httpx.AsyncClient(timeout=10.0) as client:
            for node in self.lock_nodes:
                try:
                    response = await client.get(f"{node}/status")
                    status = response.json()
                    if status.get("is_leader"):
                        leader_node = node
                        print(f"  ✓ Found leader: {status['node_id']} at {node}")
                        break
                except:
                    continue
        
        if not leader_node:
            print("  ✗ No leader found! Aborting lock benchmark.")
            self.results["lock_manager"]["throughput"] = {
                "operations": 0, "elapsed": 0, "ops_per_sec": 0,
                "errors": 0, "error_rate": 0
            }
            return
        
        operations = 0
        errors = 0
        latencies = []
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            while time.time() - start_time < duration_seconds:
                resource = f"bench_resource_{operations % 100}"
                client_id = f"bench_client_{operations}"
                
                try:
                    op_start = time.time()
                    response = await client.post(
                        f"{leader_node}/locks/acquire",
                        json={
                            "resource": resource,
                            "client_id": client_id,
                            "lock_type": "exclusive",
                            "timeout_seconds": 5.0
                        }
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            latency = (time.time() - op_start) * 1000
                            latencies.append(latency)
                            operations += 1
                            
                            await client.post(
                                f"{leader_node}/locks/release",
                                json={
                                    "resource": resource,
                                    "client_id": client_id
                                }
                            )
                        else:
                            errors += 1
                    else:
                        errors += 1
                
                except Exception as e:
                    errors += 1
        
        elapsed = time.time() - start_time
        throughput = operations / elapsed if elapsed > 0 else 0
        
        latency_stats = {}
        if latencies:
            sorted_latencies = sorted(latencies)
            latency_stats = {
                "mean": statistics.mean(latencies),
                "median": statistics.median(latencies),
                "p95": sorted_latencies[int(len(sorted_latencies) * 0.95)],
                "p99": sorted_latencies[int(len(sorted_latencies) * 0.99)],
                "min": min(latencies),
                "max": max(latencies)
            }
        
        self.results["lock_manager"]["throughput"] = {
            "operations": operations,
            "elapsed": elapsed,
            "ops_per_sec": throughput,
            "errors": errors,
            "error_rate": errors / (operations + errors) if (operations + errors) > 0 else 0
        }
        
        self.results["lock_manager"]["latency"] = latency_stats
        
        print(f"  Operations: {operations}")
        print(f"  Throughput: {throughput:.2f} ops/sec")
        print(f"  Errors: {errors}")
        if latency_stats:
            print(f"  Mean Latency: {latency_stats['mean']:.2f}ms")
            print(f"  P95 Latency: {latency_stats['p95']:.2f}ms")
            print(f"  P99 Latency: {latency_stats['p99']:.2f}ms")
        print()
    
    async def benchmark_queue_throughput(self, duration_seconds=30):
        print(f"📊 Benchmarking Queue Throughput ({duration_seconds}s)...")
        
        node = self.queue_nodes[0]
        enqueued = 0
        dequeued = 0
        errors = 0
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            while time.time() - start_time < duration_seconds / 2:
                try:
                    response = await client.post(
                        f"{node}/queue/enqueue",
                        json={
                            "queue_name": "benchmark_queue",
                            "message": {"id": enqueued, "data": f"msg_{enqueued}"}
                        }
                    )
                    if response.status_code == 200:
                        enqueued += 1
                except:
                    errors += 1
            
            while time.time() - start_time < duration_seconds:
                try:
                    response = await client.post(
                        f"{node}/queue/dequeue",
                        json={"queue_name": "benchmark_queue"}
                    )
                    if response.status_code == 200:
                        result = response.json()
                        if result.get("success"):
                            dequeued += 1
                            if result.get("message_id"):
                                await client.post(
                                    f"{node}/queue/ack",
                                    json={"message_id": result["message_id"]}
                                )
                except:
                    errors += 1
        
        elapsed = time.time() - start_time
        throughput = (enqueued + dequeued) / elapsed
        
        self.results["queue"]["throughput"] = {
            "enqueued": enqueued,
            "dequeued": dequeued,
            "elapsed": elapsed,
            "ops_per_sec": throughput,
            "errors": errors
        }
        
        print(f"  Enqueued: {enqueued}")
        print(f"  Dequeued: {dequeued}")
        print(f"  Throughput: {throughput:.2f} ops/sec\n")
    
    async def benchmark_cache_performance(self, duration_seconds=30):
        print(f"📊 Benchmarking Cache Performance ({duration_seconds}s)...")
        
        node = self.cache_nodes[0]
        reads = 0
        writes = 0
        errors = 0
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            print("  Warming up cache...")
            warmup_keys = 20
            for i in range(warmup_keys):
                try:
                    await client.post(
                        f"{node}/cache",
                        json={"key": f"hot_key_{i}", "value": f"value_{i}"}
                    )
                except:
                    pass
            
            await asyncio.sleep(1)
            
            try:
                baseline_response = await client.get(f"{node}/cache/metrics")
                baseline = baseline_response.json()
                baseline_hits = baseline.get("hits", 0)
                baseline_misses = baseline.get("misses", 0)
            except:
                baseline_hits = 0
                baseline_misses = 0
            
            start_time = time.time()
            
            while time.time() - start_time < duration_seconds:
                if (reads + writes) % 10 == 0:
                    key = f"hot_key_{writes % warmup_keys}"
                    
                    try:
                        response = await client.post(
                            f"{node}/cache",
                            json={"key": key, "value": f"updated_value_{writes}"}
                        )
                        if response.status_code == 200:
                            writes += 1
                    except:
                        errors += 1
                else:
                    key = f"hot_key_{reads % warmup_keys}"
                    
                    try:
                        response = await client.get(f"{node}/cache/{key}")
                        if response.status_code == 200:
                            reads += 1
                    except:
                        errors += 1
            
            try:
                final_response = await client.get(f"{node}/cache/metrics")
                final_metrics = final_response.json()
                
                benchmark_hits = final_metrics.get("hits", 0) - baseline_hits
                benchmark_misses = final_metrics.get("misses", 0) - baseline_misses
                total_requests = benchmark_hits + benchmark_misses
                
                hit_rate = benchmark_hits / total_requests if total_requests > 0 else 0
                
                metrics = {
                    "hit_rate": hit_rate,
                    "hits": benchmark_hits,
                    "misses": benchmark_misses,
                    "cache_size": final_metrics.get("cache_size", 0),
                    "evictions": final_metrics.get("evictions", 0)
                }
            except Exception as e:
                print(f"  ⚠ Metrics error: {e}")
                metrics = {"hit_rate": 0, "hits": 0, "misses": 0}
        
        elapsed = time.time() - start_time
        total_ops = reads + writes
        throughput = total_ops / elapsed if elapsed > 0 else 0
        
        self.results["cache"]["performance"] = {
            "reads": reads,
            "writes": writes,
            "total_operations": total_ops,
            "elapsed": elapsed,
            "ops_per_sec": throughput,
            "hit_rate": metrics.get("hit_rate", 0),
            "benchmark_hits": metrics.get("hits", 0),
            "benchmark_misses": metrics.get("misses", 0),
            "cache_size": metrics.get("cache_size", 0),
            "evictions": metrics.get("evictions", 0),
            "errors": errors
        }
        
        print(f"  Reads: {reads}")
        print(f"  Writes: {writes}")
        print(f"  Throughput: {throughput:.2f} ops/sec")
        print(f"  Hit Rate: {metrics.get('hit_rate', 0)*100:.2f}%")
        print(f"  Benchmark Hits: {metrics.get('hits', 0)}, Misses: {metrics.get('misses', 0)}")
        print(f"  Cache Size: {metrics.get('cache_size', 0)}, Evictions: {metrics.get('evictions', 0)}\n")
    
    async def benchmark_scalability(self):
        print("📈 Benchmarking Scalability...")
        
        results = []
        
        for num_nodes in [1, 2, 3]:
            nodes_to_test = self.cache_nodes[:num_nodes]
            print(f"\n  Testing with {num_nodes} node(s)...")
            
            operations = 0
            start_time = time.time()
            duration = 10
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                while time.time() - start_time < duration:
                    node = nodes_to_test[operations % num_nodes]
                    key = f"scale_key_{operations % 100}"
                    
                    try:
                        if operations % 5 == 0:
                            await client.post(
                                f"{node}/cache",
                                json={"key": key, "value": f"val_{operations}"}
                            )
                        else:
                            await client.get(f"{node}/cache/{key}")
                        operations += 1
                    except:
                        pass
            
            elapsed = time.time() - start_time
            throughput = operations / elapsed if elapsed > 0 else 0
            
            results.append({
                "nodes": num_nodes,
                "operations": operations,
                "throughput": throughput,
                "efficiency": throughput / num_nodes if num_nodes > 0 else 0
            })
            
            print(f"    Throughput: {throughput:.2f} ops/sec")
            print(f"    Efficiency: {throughput / num_nodes:.2f} ops/sec/node")
        
        self.results["scalability"] = results
        print()
    
    def save_results(self, filename="benchmarks/results/benchmark_results.json"):
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"✓ Results saved to {filename}")
    
    async def run_all(self):
        """Run all benchmarks"""
        print("=" * 70)
        print("🚀 DISTRIBUTED SYSTEM BENCHMARK SUITE")
        print("=" * 70)
        print()
        
        if not await self.check_health():
            print("❌ Some nodes are not healthy. Please start all services first.")
            return False
        
        try:
            await self.benchmark_lock_throughput(duration_seconds=30)
            await self.benchmark_queue_throughput(duration_seconds=30)
            await self.benchmark_cache_performance(duration_seconds=30)
            await self.benchmark_scalability()
            
            self.save_results("benchmarks/results/benchmark_results.json")
            
            print()
            print("=" * 70)
            print("✅ ALL BENCHMARKS COMPLETED")
            print("=" * 70)
            
            return True
            
        except Exception as e:
            print(f"\n❌ Benchmark failed: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    import os
    
    os.makedirs("benchmarks/results", exist_ok=True)
    
    benchmark = IntegratedBenchmark()
    success = asyncio.run(benchmark.run_all())
    
    sys.exit(0 if success else 1)
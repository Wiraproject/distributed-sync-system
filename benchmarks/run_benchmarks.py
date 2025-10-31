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
    
    # ========== LOCK MANAGER BENCHMARKS ==========
    async def benchmark_lock_throughput(self, duration_seconds=30):
        print(f"📊 Benchmarking Lock Manager Throughput ({duration_seconds}s)...")
        
        node = self.lock_nodes[0]
        operations = 0
        errors = 0
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            while time.time() - start_time < duration_seconds:
                resource = f"bench_resource_{operations % 100}"
                client_id = f"bench_client_{operations}"
                
                try:
                    response = await client.post(
                        f"{node}/locks/acquire",
                        json={
                            "resource": resource,
                            "client_id": client_id,
                            "lock_type": "exclusive"
                        }
                    )
                    
                    if response.status_code == 200:
                        await client.post(
                            f"{node}/locks/release",
                            json={
                                "resource": resource,
                                "client_id": client_id
                            }
                        )
                        operations += 1
                    else:
                        errors += 1
                
                except Exception as e:
                    errors += 1
        
        elapsed = time.time() - start_time
        throughput = operations / elapsed
        
        self.results["lock_manager"]["throughput"] = {
            "operations": operations,
            "elapsed": elapsed,
            "ops_per_sec": throughput,
            "errors": errors,
            "error_rate": errors / (operations + errors) if operations + errors > 0 else 0
        }
        
        print(f"  Operations: {operations}")
        print(f"  Throughput: {throughput:.2f} ops/sec")
        print(f"  Errors: {errors}\n")
    
    async def benchmark_lock_latency(self, num_samples=1000):
        print(f"⏱️  Benchmarking Lock Latency ({num_samples} samples)...")
        
        node = self.lock_nodes[0]
        latencies = []
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for i in range(num_samples):
                resource = f"latency_resource_{i}"
                client_id = f"latency_client_{i}"
                
                start = time.time()
                try:
                    await client.post(
                        f"{node}/locks/acquire",
                        json={
                            "resource": resource,
                            "client_id": client_id,
                            "lock_type": "exclusive"
                        }
                    )
                    latency = (time.time() - start) * 1000  
                    latencies.append(latency)
                    
                    await client.post(
                        f"{node}/locks/release",
                        json={"resource": resource, "client_id": client_id}
                    )
                except Exception as e:
                    continue
        
        if latencies:
            sorted_latencies = sorted(latencies)
            self.results["lock_manager"]["latency"] = {
                "mean": statistics.mean(latencies),
                "median": statistics.median(latencies),
                "p95": sorted_latencies[int(len(sorted_latencies) * 0.95)],
                "p99": sorted_latencies[int(len(sorted_latencies) * 0.99)],
                "min": min(latencies),
                "max": max(latencies)
            }
            
            print(f"  Mean: {statistics.mean(latencies):.2f}ms")
            print(f"  P95: {sorted_latencies[int(len(sorted_latencies) * 0.95)]:.2f}ms")
            print(f"  P99: {sorted_latencies[int(len(sorted_latencies) * 0.99)]:.2f}ms\n")
    
    # ========== QUEUE BENCHMARKS ==========
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
    
    # ========== CACHE BENCHMARKS ==========
    async def benchmark_cache_performance(self, duration_seconds=30):
        print(f"📊 Benchmarking Cache Performance ({duration_seconds}s)...")
        
        node = self.cache_nodes[0]
        reads = 0
        writes = 0
        errors = 0
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            for i in range(50):
                await client.post(
                    f"{node}/cache",
                    json={"key": f"key_{i}", "value": f"value_{i}"}
                )
            
            while time.time() - start_time < duration_seconds:
                key = f"key_{reads % 100}"
                
                try:
                    if (reads + writes) % 5 == 0: 
                        response = await client.post(
                            f"{node}/cache",
                            json={"key": key, "value": f"value_{writes}"}
                        )
                        if response.status_code == 200:
                            writes += 1
                    else:
                        response = await client.get(f"{node}/cache/{key}")
                        if response.status_code == 200:
                            reads += 1
                except:
                    errors += 1
            
            metrics_response = await client.get(f"{node}/cache/metrics")
            metrics = metrics_response.json()
        
        elapsed = time.time() - start_time
        total_ops = reads + writes
        throughput = total_ops / elapsed
        
        self.results["cache"]["performance"] = {
            "reads": reads,
            "writes": writes,
            "total_operations": total_ops,
            "elapsed": elapsed,
            "ops_per_sec": throughput,
            "hit_rate": metrics.get("hit_rate", 0),
            "errors": errors
        }
        
        print(f"  Reads: {reads}")
        print(f"  Writes: {writes}")
        print(f"  Throughput: {throughput:.2f} ops/sec")
        print(f"  Hit Rate: {metrics.get('hit_rate', 0)*100:.2f}%\n")
    
    # ========== SCALABILITY TEST ==========
    
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
                    key = f"scale_key_{operations}"
                    
                    try:
                        if operations % 5 == 0:
                            # FIX: ubah /cache/set jadi /cache
                            await client.post(
                                f"{node}/cache",  # ← FIX: hapus /set
                                json={"key": key, "value": f"val_{operations}"}
                            )
                        else:
                            await client.get(f"{node}/cache/{key}")
                        operations += 1
                    except:
                        pass
            
            elapsed = time.time() - start_time
            throughput = operations / elapsed
            
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
        
    # ========== SAVE RESULTS ==========
    
    def save_results(self, filename="benchmark_results.json"):
        """Save results to JSON file"""
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
            await self.benchmark_lock_latency(num_samples=1000)
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
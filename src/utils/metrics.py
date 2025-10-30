import time
from collections import defaultdict
from typing import Dict, List

class MetricsCollector:
    def __init__(self):
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.counters: Dict[str, int] = defaultdict(int)
        
    def record_latency(self, operation: str, latency: float):
        self.metrics[f"{operation}_latency"].append(latency)
        
    def increment_counter(self, counter: str):
        self.counters[counter] += 1
        
    def get_summary(self) -> Dict:
        summary = {}
        
        for metric, values in self.metrics.items():
            if values:
                summary[metric] = {
                    "count": len(values),
                    "mean": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "p50": sorted(values)[len(values) // 2],
                    "p95": sorted(values)[int(len(values) * 0.95)],
                    "p99": sorted(values)[int(len(values) * 0.99)]
                }
                
        summary["counters"] = dict(self.counters)
        return summary
        
    def reset(self):
        self.metrics.clear()
        self.counters.clear()

class PerformanceMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.metrics = MetricsCollector()
        
    async def measure_operation(self, operation_name: str, coro):
        start = time.time()
        result = await coro
        latency = time.time() - start
        self.metrics.record_latency(operation_name, latency)
        return result
        
    def get_uptime(self) -> float:
        return time.time() - self.start_time
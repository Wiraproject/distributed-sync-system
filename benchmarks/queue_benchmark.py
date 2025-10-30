import asyncio
import time
import statistics
from src.nodes.queue_node import DistributedQueue

async def benchmark_queue_throughput():
    queue = DistributedQueue("bench_queue", "localhost", 9100)
    queue.initialize_consistent_hash()
    
    print("=" * 60)
    print("QUEUE THROUGHPUT BENCHMARK")
    print("=" * 60)
    
    num_messages = 5000
    queue_name = "benchmark_queue"
    
    print(f"\nEnqueuing {num_messages} messages...")
    start_time = time.time()
    
    for i in range(num_messages):
        await queue.enqueue(queue_name, {
            "id": i,
            "data": f"message_{i}",
            "timestamp": time.time()
        })
    
    enqueue_time = time.time() - start_time
    enqueue_throughput = num_messages / enqueue_time
    
    print(f"{'Enqueue Time:':<30} {enqueue_time:.2f}s")
    print(f"{'Enqueue Throughput:':<30} {enqueue_throughput:.2f} msgs/sec")
    
    print(f"\nDequeuing {num_messages} messages...")
    start_time = time.time()
    dequeued = 0
    
    for i in range(num_messages):
        msg = await queue.dequeue(queue_name)
        if msg:
            dequeued += 1
    
    dequeue_time = time.time() - start_time
    dequeue_throughput = dequeued / dequeue_time
    
    print(f"{'Dequeue Time:':<30} {dequeue_time:.2f}s")
    print(f"{'Dequeue Throughput:':<30} {dequeue_throughput:.2f} msgs/sec")
    print(f"{'Messages Dequeued:':<30} {dequeued}/{num_messages}")

async def benchmark_queue_latency():
    queue = DistributedQueue("bench_queue", "localhost", 9101)
    queue.initialize_consistent_hash()
    
    print("\n" + "=" * 60)
    print("QUEUE LATENCY BENCHMARK")
    print("=" * 60)
    
    num_samples = 1000
    queue_name = "latency_queue"
    enqueue_latencies = []
    dequeue_latencies = []
    
    print(f"\nMeasuring latency for {num_samples} operations...")
    
    for i in range(num_samples):
        start = time.time()
        msg_id = await queue.enqueue(queue_name, {"id": i, "data": f"msg_{i}"})
        enqueue_latencies.append(time.time() - start)
        
        start = time.time()
        msg = await queue.dequeue(queue_name)
        dequeue_latencies.append(time.time() - start)
    
    def print_latency_stats(latencies, operation):
        latencies_ms = [l * 1000 for l in latencies]
        print(f"\n{operation} Latency:")
        print(f"{'  Mean:':<30} {statistics.mean(latencies_ms):.2f}ms")
        print(f"{'  Median:':<30} {statistics.median(latencies_ms):.2f}ms")
        print(f"{'  P95:':<30} {sorted(latencies_ms)[int(len(latencies_ms)*0.95)]:.2f}ms")
        print(f"{'  P99:':<30} {sorted(latencies_ms)[int(len(latencies_ms)*0.99)]:.2f}ms")
    
    print_latency_stats(enqueue_latencies, "ENQUEUE")
    print_latency_stats(dequeue_latencies, "DEQUEUE")

async def benchmark_producer_consumer():
    queue = DistributedQueue("bench_queue", "localhost", 9102)
    queue.initialize_consistent_hash()
    
    print("\n" + "=" * 60)
    print("PRODUCER-CONSUMER BENCHMARK")
    print("=" * 60)
    
    queue_name = "prod_cons_queue"
    messages_per_producer = 100
    num_producers = 10
    num_consumers = 10
    
    produced_count = 0
    consumed_count = 0
    
    async def producer(producer_id):
        nonlocal produced_count
        for i in range(messages_per_producer):
            await queue.enqueue(queue_name, {
                "producer_id": producer_id,
                "message_id": i,
                "data": f"msg_{producer_id}_{i}"
            })
            produced_count += 1
    
    async def consumer(consumer_id):
        nonlocal consumed_count
        while consumed_count < num_producers * messages_per_producer:
            msg = await queue.dequeue(queue_name)
            if msg:
                consumed_count += 1
            else:
                await asyncio.sleep(0.01)
    
    print(f"\nRunning {num_producers} producers and {num_consumers} consumers...")
    
    start_time = time.time()
    
    producer_tasks = [producer(i) for i in range(num_producers)]
    consumer_tasks = [consumer(i) for i in range(num_consumers)]
    
    await asyncio.gather(*producer_tasks)
    await asyncio.gather(*consumer_tasks)
    
    elapsed = time.time() - start_time
    total_messages = num_producers * messages_per_producer
    throughput = total_messages / elapsed
    
    print(f"\n{'Results:':<30}")
    print(f"{'Total Messages:':<30} {total_messages}")
    print(f"{'Messages Produced:':<30} {produced_count}")
    print(f"{'Messages Consumed:':<30} {consumed_count}")
    print(f"{'Elapsed Time:':<30} {elapsed:.2f}s")
    print(f"{'Throughput:':<30} {throughput:.2f} msgs/sec")

if __name__ == "__main__":
    async def run_all_benchmarks():
        await benchmark_queue_throughput()
        await benchmark_queue_latency()
        await benchmark_producer_consumer()
        print("\n" + "=" * 60)
        print("QUEUE BENCHMARKS COMPLETED")
        print("=" * 60)
    
    asyncio.run(run_all_benchmarks())
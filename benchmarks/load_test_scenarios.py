from locust import HttpUser, task, between, events
import random
import json

class DistributedSystemUser(HttpUser):
    wait_time = between(0.1, 0.5)
    
    cache_nodes = ["http://localhost:7000", "http://localhost:7001", "http://localhost:7002"]
    queue_nodes = ["http://localhost:9000", "http://localhost:9001", "http://localhost:9002"]
    lock_nodes = ["http://localhost:8080", "http://localhost:8081", "http://localhost:8082"]
    
    def on_start(self):
        self.client_id = f"locust_user_{random.randint(1, 10000)}"
        
        for i in range(10):
            try:
                node = random.choice(self.cache_nodes)
                self.client.post(
                    f"{node}/cache",
                    json={"key": f"warmup_key_{i}", "value": f"warmup_value_{i}"},
                    name="/cache [POST]"
                )
            except:
                pass
    
    @task(3)
    def cache_read(self):
        node = random.choice(self.cache_nodes)
        key = f"key_{random.randint(1, 100)}"
        
        with self.client.get(
            f"{node}/cache/{key}",
            catch_response=True,
            name="/cache/{key} [GET]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")
    
    @task(1)
    def cache_write(self):
        node = random.choice(self.cache_nodes)
        key = f"key_{random.randint(1, 100)}"
        value = f"value_{random.randint(1, 1000)}"
        
        with self.client.post(
            f"{node}/cache",
            json={"key": key, "value": value},
            catch_response=True,
            name="/cache [POST]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")
    
    @task(2)
    def queue_enqueue(self):
        node = random.choice(self.queue_nodes)
        message = {
            "task": "process_data",
            "data": random.randint(1, 1000),
            "timestamp": str(random.random())
        }
        
        with self.client.post(
            f"{node}/queue/enqueue",
            json={"queue_name": "load_test_queue", "message": message},
            catch_response=True,
            name="/queue/enqueue [POST]"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")
    
    @task(2)
    def queue_dequeue(self):
        node = random.choice(self.queue_nodes)
        
        with self.client.post(
            f"{node}/queue/dequeue",
            json={"queue_name": "load_test_queue"},
            catch_response=True,
            name="/queue/dequeue [POST]"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and data.get("message_id"):
                    self.client.post(
                        f"{node}/queue/ack",
                        json={"message_id": data["message_id"]},
                        name="/queue/ack [POST]"
                    )
                response.success()
            else:
                response.failure(f"Failed with status {response.status_code}")
    
    @task(1)
    def lock_acquire_release(self):
        node = random.choice(self.lock_nodes)
        resource = f"resource_{random.randint(1, 20)}"
        
        # Acquire lock
        with self.client.post(
            f"{node}/locks/acquire",
            json={
                "resource": resource,
                "client_id": self.client_id,
                "lock_type": "exclusive"
            },
            catch_response=True,
            name="/locks/acquire [POST]"
        ) as response:
            if response.status_code == 200:
                response.success()
                
                self.client.post(
                    f"{node}/locks/release",
                    json={
                        "resource": resource,
                        "client_id": self.client_id
                    },
                    name="/locks/release [POST]"
                )
            else:
                response.failure(f"Failed to acquire lock: {response.status_code}")


class CacheHeavyUser(HttpUser):
    wait_time = between(0.05, 0.2)
    
    @task(8)
    def read_cache(self):
        node = random.choice(["http://localhost:7000", "http://localhost:7001", "http://localhost:7002"])
        key = f"key_{random.randint(1, 50)}"
        self.client.get(f"{node}/cache/{key}", name="/cache/{key} [GET]")
    
    @task(2)
    def write_cache(self):
        node = random.choice(["http://localhost:7000", "http://localhost:7001", "http://localhost:7002"])
        key = f"key_{random.randint(1, 50)}"
        self.client.post(
            f"{node}/cache",
            json={"key": key, "value": f"value_{random.randint(1, 1000)}"},
            name="/cache [POST]"
        )

class QueueHeavyUser(HttpUser):
    wait_time = between(0.1, 0.3)
    
    @task(1)
    def enqueue_message(self):
        node = random.choice(["http://localhost:9000", "http://localhost:9001", "http://localhost:9002"])
        self.client.post(
            f"{node}/queue/enqueue",
            json={
                "queue_name": "heavy_queue",
                "message": {"data": random.randint(1, 1000)}
            },
            name="/queue/enqueue [POST]"
        )
    
    @task(1)
    def dequeue_message(self):
        node = random.choice(["http://localhost:9000", "http://localhost:9001", "http://localhost:9002"])
        response = self.client.post(
            f"{node}/queue/dequeue",
            json={"queue_name": "heavy_queue"},
            name="/queue/dequeue [POST]"
        )
        if response.status_code == 200:
            data = response.json()
            if data.get("message_id"):
                self.client.post(
                    f"{node}/queue/ack",
                    json={"message_id": data["message_id"]},
                    name="/queue/ack [POST]"
                )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "="*70)
    print("🚀 LOAD TEST STARTING")
    print("="*70)
    print(f"Target: {environment.host if hasattr(environment, 'host') else 'Multiple nodes'}")
    print(f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}")
    print("="*70 + "\n")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n" + "="*70)
    print("✅ LOAD TEST COMPLETED")
    print("="*70)
    
    stats = environment.stats.total
    print(f"Total Requests: {stats.num_requests:,}")
    print(f"Failed Requests: {stats.num_failures:,}")
    print(f"Failure Rate: {stats.fail_ratio*100:.2f}%")
    print(f"Average Response Time: {stats.avg_response_time:.2f}ms")
    print(f"Min Response Time: {stats.min_response_time:.2f}ms")
    print(f"Max Response Time: {stats.max_response_time:.2f}ms")
    print(f"Requests/sec: {stats.total_rps:.2f}")
    print("="*70 + "\n")
    
    print("\n📊 PER-ENDPOINT STATISTICS:")
    print("-"*70)
    for name, stat in environment.stats.entries.items():
        if stat.num_requests > 0:
            print(f"\n{name}")
            print(f"  Requests: {stat.num_requests:,}")
            print(f"  Failures: {stat.num_failures:,}")
            print(f"  Avg: {stat.avg_response_time:.2f}ms")
            print(f"  P95: {stat.get_response_time_percentile(0.95):.2f}ms")
            print(f"  P99: {stat.get_response_time_percentile(0.99):.2f}ms")
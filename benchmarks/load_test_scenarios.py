from locust import User, task, between, events
import random

class DistributedSystemUser(User):
    wait_time = between(0.1, 0.5)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.node_hosts = [
            "http://localhost:8000",
            "http://localhost:8001",
            "http://localhost:8002"
        ]
    
    @task(3)
    def cache_read(self):
        node = random.choice(self.node_hosts)
        key = f"key_{random.randint(1, 100)}"
        pass
    
    @task(1)
    def cache_write(self):
        node = random.choice(self.node_hosts)
        key = f"key_{random.randint(1, 100)}"
        value = f"value_{random.randint(1, 1000)}"
        pass
    
    @task(2)
    def queue_operations(self):
        node = random.choice(self.node_hosts)
        
        if random.random() > 0.5:
            message = {
                "task": "process_data",
                "data": random.randint(1, 1000)
            }
        else:
            pass
    
    @task(1)
    def lock_operations(self):
        node = random.choice(self.node_hosts)
        resource = f"resource_{random.randint(1, 10)}"
        pass

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("Load test starting...")

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("Load test completed!")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failure rate: {environment.stats.total.fail_ratio*100:.2f}%")
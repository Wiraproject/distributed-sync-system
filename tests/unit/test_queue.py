import pytest
from src.nodes.queue_node import DistributedQueue, ConsistentHash

def test_consistent_hash_distribution():
    nodes = ["node_0", "node_1", "node_2"]
    ch = ConsistentHash(nodes)
    
    keys = [f"key_{i}" for i in range(100)]
    distribution = {node: 0 for node in nodes}
    
    for key in keys:
        node = ch.get_node(key)
        distribution[node] += 1
    
    for count in distribution.values():
        assert count > 20

def test_consistent_hash_node_removal():
    nodes = ["node_0", "node_1", "node_2"]
    ch = ConsistentHash(nodes)
    
    keys = [f"key_{i}" for i in range(100)]
    original_mapping = {key: ch.get_node(key) for key in keys}
    
    ch.remove_node("node_1")
    
    remapped = 0
    for key in keys:
        new_node = ch.get_node(key)
        if original_mapping[key] != new_node:
            remapped += 1
    
    assert remapped < 50 

@pytest.mark.asyncio
async def test_queue_enqueue_dequeue():
    queue = DistributedQueue("queue_node", "localhost", 8000)
    queue.initialize_consistent_hash()
    
    msg_id = await queue.enqueue("test_queue", {"data": "test_message"})
    assert msg_id is not None
    
    message = await queue.dequeue("test_queue")
    assert message is not None
    assert message["data"]["data"] == "test_message"

@pytest.mark.asyncio
async def test_queue_persistence():
    queue = DistributedQueue("queue_node", "localhost", 8000)
    queue.initialize_consistent_hash()
    
    for i in range(10):
        await queue.enqueue("test_queue", {"data": f"message_{i}"})
    
    assert len(queue.persistent_log) == 10
    
    queue.queues.clear()
    await queue.recover_from_log()
    
    assert len(queue.queues["test_queue"]) == 10
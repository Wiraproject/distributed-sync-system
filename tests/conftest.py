import pytest
import asyncio
import logging

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def setup_nodes():
    nodes = []
    
    from src.consensus.raft import RaftNode
    for i in range(3):
        node = RaftNode(f"test_node_{i}", "localhost", 7000 + i)
        nodes.append(node)
    
    for i, node in enumerate(nodes):
        for j, peer in enumerate(nodes):
            if i != j:
                node.add_peer(peer.node_id, peer.host, peer.port)
    
    for node in nodes:
        await node.start()
    
    yield nodes
    
    for node in nodes:
        await node.stop()

@pytest.fixture
def mock_redis():
    class MockRedis:
        def __init__(self):
            self.data = {}
        
        def get(self, key):
            return self.data.get(key)
        
        def set(self, key, value):
            self.data[key] = value
        
        def delete(self, key):
            if key in self.data:
                del self.data[key]
    
    return MockRedis()
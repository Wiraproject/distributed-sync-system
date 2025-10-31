import pytest
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

@pytest.fixture(scope="session")
def event_loop():
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    yield loop

    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except RuntimeError:
        pass
    finally:
        try:
            loop.close()
        except:
            pass

@pytest.fixture(autouse=True)
async def cleanup_tasks():
    yield
    
    try:
        loop = asyncio.get_running_loop()
        
        tasks = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in tasks:
            task.cancel()
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    except RuntimeError:
        pass

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
        node.running = False
    
    await asyncio.sleep(0.1)
    
    for node in nodes:
        await node.stop()

@pytest.fixture
def mock_redis():
    """Mock Redis for testing"""
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
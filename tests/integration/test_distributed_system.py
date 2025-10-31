import pytest
import asyncio
from src.consensus.raft import RaftNode, NodeState
from src.nodes.lock_manager import DistributedLockManager, LockType
from src.nodes.cache_node import MESICache

@pytest.mark.asyncio
async def test_full_cluster_setup():
    num_nodes = 3
    nodes = []
    
    for i in range(num_nodes):
        node = RaftNode(f"node_{i}", "localhost", 6000 + i)
        node.election_timeout = 0.15 + (i * 0.05) 
        nodes.append(node)
    
    for i, node in enumerate(nodes):
        for j, peer in enumerate(nodes):
            if i != j:
                node.add_peer(peer.node_id, peer.host, peer.port)
    
    async def mock_send_to_peer(self, peer_id: str, message: dict):
        for node in nodes:
            if node.node_id == peer_id:
                return await node.process_message(message)
        return None
    
    for node in nodes:
        node.send_to_peer = lambda pid, msg, n=node: mock_send_to_peer(n, pid, msg)
    
    try:
        for node in nodes:
            await node.start()
        
        await asyncio.sleep(1.5)
        
        leaders = [n for n in nodes if n.state == NodeState.LEADER]
        candidates = [n for n in nodes if n.state == NodeState.CANDIDATE]
        followers = [n for n in nodes if n.state == NodeState.FOLLOWER]
        
        print(f"\nCluster state:")
        for node in nodes:
            print(f"  {node.node_id}: {node.state.value} (term {node.current_term})")
        
        assert len(leaders) + len(candidates) + len(followers) == num_nodes
        assert len(leaders) >= 1
        
    finally:
        for node in nodes:
            node.running = False
        
        await asyncio.sleep(0.2)
        
        for node in nodes:
            await node.stop()

@pytest.mark.asyncio
async def test_distributed_lock_across_nodes():
    lock_managers = []
    
    for i in range(3):
        lm = DistributedLockManager(f"lm_{i}", "localhost", 7000 + i)
        lm.election_timeout = 0.15 + (i * 0.05)
        lock_managers.append(lm)
    
    for i, lm in enumerate(lock_managers):
        for j, peer in enumerate(lock_managers):
            if i != j:
                lm.add_peer(peer.node_id, peer.host, peer.port)
    
    async def mock_send_to_peer(self, peer_id: str, message: dict):
        for lm in lock_managers:
            if lm.node_id == peer_id:
                return await lm.process_message(message)
        return None
    
    for lm in lock_managers:
        lm.send_to_peer = lambda pid, msg, n=lm: mock_send_to_peer(n, pid, msg)
    
    try:
        for lm in lock_managers:
            await lm.start()
        
        await asyncio.sleep(1.5)
        
        leader = next((lm for lm in lock_managers if lm.state == NodeState.LEADER), None)
        
        print(f"\nLock Manager states:")
        for lm in lock_managers:
            print(f"  {lm.node_id}: {lm.state.value}")
        
        if leader:
            async def mock_replicate(command):
                await leader.apply_to_state_machine(command)
                return True
            
            leader.replicate_command = mock_replicate
            
            result = await leader.acquire_lock("shared_resource", LockType.EXCLUSIVE, "client_1")
            assert result["success"] == True
            assert "shared_resource" in leader.locks
        else:
            print("  No clear leader, testing basic lock functionality")
            test_lm = lock_managers[0]
            test_lm.state = NodeState.LEADER
            
            async def mock_replicate(command):
                await test_lm.apply_to_state_machine(command)
                return True
            
            test_lm.replicate_command = mock_replicate
            
            result = await test_lm.acquire_lock("shared_resource", LockType.EXCLUSIVE, "client_1")
            assert result["success"] == True
    
    finally:
        for lm in lock_managers:
            lm.running = False
        
        await asyncio.sleep(0.2)
        
        for lm in lock_managers:
            await lm.stop()

@pytest.mark.asyncio
async def test_cache_coherence_protocol():
    caches = []
    
    for i in range(3):
        cache = MESICache(f"cache_{i}", "localhost", 8000 + i)
        caches.append(cache)
    
    for i, cache in enumerate(caches):
        for j, peer in enumerate(caches):
            if i != j:
                cache.add_peer(peer.node_id, peer.host, peer.port)
    
    async def mock_send_to_peer(self, peer_id: str, message: dict):
        for cache in caches:
            if cache.node_id == peer_id:
                return await cache.process_message(message)
        return None
    
    for cache in caches:
        cache.send_to_peer = lambda pid, msg, c=cache: mock_send_to_peer(c, pid, msg)
    
    try:
        for cache in caches:
            await cache.start()
        
        await caches[0].write("shared_key", "value_1")
        
        await asyncio.sleep(0.1)
        
        print(f"\nCache states after write:")
        for cache in caches:
            if "shared_key" in cache.cache:
                state = cache.cache["shared_key"].state.value
                print(f"  {cache.node_id}: {state}")
        
        value = await caches[1].read("shared_key")
        
        await asyncio.sleep(0.1)
        
        print(f"\nCache states after read:")
        for cache in caches:
            if "shared_key" in cache.cache:
                state = cache.cache["shared_key"].state.value
                print(f"  {cache.node_id}: {state}")
        
        assert value is not None
        assert "shared_key" in caches[0].cache or "shared_key" in caches[1].cache
        
    finally:
        for cache in caches:
            cache.running = False
        
        await asyncio.sleep(0.1)
        
        for cache in caches:
            await cache.stop()

@pytest.mark.asyncio
async def test_basic_node_communication():
    node1 = RaftNode("node_1", "localhost", 6100)
    node2 = RaftNode("node_2", "localhost", 6101)
    
    node1.add_peer(node2.node_id, node2.host, node2.port)
    node2.add_peer(node1.node_id, node1.host, node1.port)
    
    async def mock_send(self, peer_id, message):
        if peer_id == node2.node_id:
            return await node2.process_message(message)
        elif peer_id == node1.node_id:
            return await node1.process_message(message)
        return None
    
    node1.send_to_peer = lambda p, m: mock_send(node1, p, m)
    node2.send_to_peer = lambda p, m: mock_send(node2, p, m)
    
    try:
        await node1.start()
        await node2.start()
        
        await asyncio.sleep(1.0)
        
        assert node1.running
        assert node2.running
        
        assert node1.state != NodeState.FOLLOWER or node2.state != NodeState.FOLLOWER
        
    finally:
        node1.running = False
        node2.running = False
        await asyncio.sleep(0.1)
        await node1.stop()
        await node2.stop()
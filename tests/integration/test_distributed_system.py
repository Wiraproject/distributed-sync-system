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
        nodes.append(node)
    
    for i, node in enumerate(nodes):
        for j, peer in enumerate(nodes):
            if i != j:
                node.add_peer(peer.node_id, peer.host, peer.port)
    
    for node in nodes:
        await node.start()
    
    await asyncio.sleep(1.0)
    
    leaders = [n for n in nodes if n.state == NodeState.LEADER]
    followers = [n for n in nodes if n.state == NodeState.FOLLOWER]
    
    assert len(leaders) == 1
    assert len(followers) == 2
    
    for node in nodes:
        await node.stop()

@pytest.mark.asyncio
async def test_distributed_lock_across_nodes():
    lock_managers = []
    
    for i in range(3):
        lm = DistributedLockManager(f"lm_{i}", "localhost", 7000 + i)
        lock_managers.append(lm)
    
    for i, lm in enumerate(lock_managers):
        for j, peer in enumerate(lock_managers):
            if i != j:
                lm.add_peer(peer.node_id, peer.host, peer.port)
    
    for lm in lock_managers:
        await lm.start()
    
    await asyncio.sleep(0.5)
    
    leader = next((lm for lm in lock_managers if lm.state == NodeState.LEADER), None)
    assert leader is not None
    
    result = await leader.acquire_lock("shared_resource", LockType.EXCLUSIVE, "client_1")
    assert result == True
    
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
    
    for cache in caches:
        await cache.start()
    
    await caches[0].write("shared_key", "value_1")
    
    await asyncio.sleep(0.1) 
    
    for cache in caches:
        await cache.stop()
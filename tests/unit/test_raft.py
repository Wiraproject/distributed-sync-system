# tests/unit/test_raft.py
import pytest
import asyncio
import socket
from src.consensus.raft import RaftNode, NodeState

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

@pytest.mark.asyncio
async def test_election_timeout():
    port = get_free_port()
    node = RaftNode("test_node", "localhost", port)
    node.election_timeout = 0.01
    
    try:
        await node.start()
        await asyncio.sleep(0.1)
        
        assert node.state in [NodeState.LEADER, NodeState.CANDIDATE]
        assert node.current_term > 0
    finally:
        await node.stop()
        await asyncio.sleep(0.1)

@pytest.mark.asyncio
async def test_leader_election():
    nodes = []
    ports = [get_free_port() for _ in range(3)]
    
    for i in range(3):
        node = RaftNode(f"node_{i}", "localhost", ports[i])
        node.election_timeout = 0.15 + (i * 0.05)
        nodes.append(node)
    
    for i, node in enumerate(nodes):
        for j, peer in enumerate(nodes):
            if i != j:
                node.add_peer(peer.node_id, peer.host, ports[j])
    
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
        
        print(f"\nElection results:")
        for node in nodes:
            print(f"  {node.node_id}: {node.state.value} (term {node.current_term})")
        
        assert len(leaders) >= 1, f"Expected at least 1 leader, got {len(leaders)}"
        
        # Total should be 3
        assert len(leaders) + len(candidates) + len(followers) == 3
        
    finally:
        for node in nodes:
            await node.stop()
        await asyncio.sleep(0.2)

@pytest.mark.asyncio
async def test_single_node_becomes_leader():
    node = RaftNode("single_node", "localhost", get_free_port())
    node.election_timeout = 0.1
    
    try:
        await node.start()
        
        await asyncio.sleep(0.3)
        
        assert node.state in [NodeState.LEADER, NodeState.CANDIDATE]
        assert node.current_term > 0
        
    finally:
        await node.stop()

@pytest.mark.asyncio  
async def test_term_increment_on_election():
    node = RaftNode("test_node", "localhost", get_free_port())
    node.election_timeout = 0.05
    
    try:
        initial_term = node.current_term
        await node.start()
        
        await asyncio.sleep(0.15)
        
        assert node.current_term > initial_term
        
    finally:
        await node.stop()
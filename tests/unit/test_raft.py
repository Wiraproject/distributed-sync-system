import pytest
import asyncio
from src.consensus.raft import RaftNode, NodeState

@pytest.mark.asyncio
async def test_raft_initialization():
    """Test Raft node initialization"""
    node = RaftNode("test_node", "localhost", 5000)
    assert node.state == NodeState.FOLLOWER
    assert node.current_term == 0
    assert node.voted_for is None

@pytest.mark.asyncio
async def test_election_timeout():
    """Test election timeout triggers candidate state"""
    node = RaftNode("test_node", "localhost", 5000)
    node.election_timeout = 0.01
    
    await node.start()
    await asyncio.sleep(0.05)
    
    assert node.state == NodeState.CANDIDATE
    assert node.current_term > 0
    
    await node.stop()

@pytest.mark.asyncio
async def test_vote_granting():
    """Test vote granting logic"""
    node = RaftNode("test_node", "localhost", 5000)
    
    vote_request = {
        "term": 1,
        "candidate_id": "candidate_1",
        "last_log_index": 0,
        "last_log_term": 0
    }
    
    response = await node.handle_request_vote(vote_request)
    
    assert response["vote_granted"] == True
    assert node.voted_for == "candidate_1"

@pytest.mark.asyncio
async def test_leader_election():
    """Test leader election with multiple nodes"""
    nodes = []
    for i in range(3):
        node = RaftNode(f"node_{i}", "localhost", 5000 + i)
        nodes.append(node)
    
    for i, node in enumerate(nodes):
        for j, peer in enumerate(nodes):
            if i != j:
                node.add_peer(peer.node_id, peer.host, peer.port)
    
    for node in nodes:
        await node.start()
    
    await asyncio.sleep(0.5)
    
    leaders = [n for n in nodes if n.state == NodeState.LEADER]
    assert len(leaders) == 1
    
    for node in nodes:
        await node.stop()
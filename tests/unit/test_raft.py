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
        await asyncio.sleep(0.05)
        
        assert node.state == NodeState.LEADER 
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
        nodes.append(node)
    
    for i, node in enumerate(nodes):
        for j, peer in enumerate(nodes):
            if i != j:
                node.add_peer(peer.node_id, peer.host, ports[j])
    
    try:
        for node in nodes:
            await node.start()
        
        await asyncio.sleep(0.5)
        
        leaders = [n for n in nodes if n.state == NodeState.LEADER]
        assert len(leaders) == 1
    finally:
        for node in nodes:
            await node.stop()
        await asyncio.sleep(0.1)
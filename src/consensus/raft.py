import asyncio
import random
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.nodes.base_node import BaseNode

class NodeState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

class LogEntry:
    def __init__(self, term: int, command: Any):
        self.term = term
        self.command = command
        self.timestamp = datetime.now()

class RaftNode(BaseNode):
    """Implementation Raft Consensus Algorithm"""
    
    def __init__(self, node_id: str, host: str, port: int):
        super().__init__(node_id, host, port)
        self.state = NodeState.FOLLOWER
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = []
        self.commit_index = 0
        self.last_applied = 0
        
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        self.election_timeout = random.uniform(150, 300) / 1000
        self.heartbeat_interval = 50 / 1000
        self.last_heartbeat = datetime.now()
        
    async def start(self):
        """Start Raft node"""
        await super().start()
        asyncio.create_task(self.run_raft())
        
    async def run_raft(self):
        """Main Raft loop"""
        while self.running:
            if self.state == NodeState.FOLLOWER:
                await self.run_follower()
            elif self.state == NodeState.CANDIDATE:
                await self.run_candidate()
            elif self.state == NodeState.LEADER:
                await self.run_leader()
            await asyncio.sleep(0.01)
            
    async def run_follower(self):
        """Follower behavior"""
        time_since_heartbeat = (datetime.now() - self.last_heartbeat).total_seconds()
        if time_since_heartbeat > self.election_timeout:
            self.logger.info(f"Election timeout, becoming candidate")
            self.state = NodeState.CANDIDATE
            
    async def run_candidate(self):
        """Candidate behavior - start election"""
        self.current_term += 1
        self.voted_for = self.node_id
        votes_received = 1
        
        self.logger.info(f"Starting election for term {self.current_term}")
        
        vote_tasks = []
        for peer_id in self.peers:
            vote_tasks.append(self.request_vote(peer_id))
            
        if vote_tasks:
            results = await asyncio.gather(*vote_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, dict) and result.get("vote_granted"):
                    votes_received += 1
        
        if votes_received > len(self.peers) / 2:
            self.logger.info(f"Won election with {votes_received} votes")
            self.state = NodeState.LEADER
            await self.become_leader()
        else:
            self.state = NodeState.FOLLOWER
            self.election_timeout = random.uniform(150, 300) / 1000
            
    async def run_leader(self):
        """Leader behavior - send heartbeats"""
        heartbeat_tasks = []
        for peer_id in self.peers:
            heartbeat_tasks.append(self.send_heartbeat(peer_id))
            
        if heartbeat_tasks:
            await asyncio.gather(*heartbeat_tasks, return_exceptions=True)
            
        await asyncio.sleep(self.heartbeat_interval)
        
    async def request_vote(self, peer_id: str) -> Dict:
        """Request vote from peer"""
        message = {
            "type": "request_vote",
            "term": self.current_term,
            "candidate_id": self.node_id,
            "last_log_index": len(self.log) - 1,
            "last_log_term": self.log[-1].term if self.log else 0
        }
        return await self.send_to_peer(peer_id, message) or {}
        
    async def send_heartbeat(self, peer_id: str):
        """Send heartbeat to follower"""
        message = {
            "type": "append_entries",
            "term": self.current_term,
            "leader_id": self.node_id,
            "entries": [],
            "leader_commit": self.commit_index
        }
        await self.send_to_peer(peer_id, message)
        
    async def become_leader(self):
        """Initialize leader state"""
        for peer_id in self.peers:
            self.next_index[peer_id] = len(self.log)
            self.match_index[peer_id] = 0
            
    async def process_message(self, message: Dict) -> Dict:
        """Process Raft messages"""
        msg_type = message.get("type")
        
        if msg_type == "request_vote":
            return await self.handle_request_vote(message)
        elif msg_type == "append_entries":
            return await self.handle_append_entries(message)
            
        return {"status": "unknown_message_type"}
        
    async def handle_request_vote(self, message: Dict) -> Dict:
        """Handle vote request"""
        term = message["term"]
        candidate_id = message["candidate_id"]
        
        if term > self.current_term:
            self.current_term = term
            self.state = NodeState.FOLLOWER
            self.voted_for = None
            
        vote_granted = False
        if term == self.current_term and (self.voted_for is None or self.voted_for == candidate_id):
            self.voted_for = candidate_id
            vote_granted = True
            
        return {
            "term": self.current_term,
            "vote_granted": vote_granted
        }
        
    async def handle_append_entries(self, message: Dict) -> Dict:
        """Handle append entries (heartbeat)"""
        term = message["term"]
        
        if term >= self.current_term:
            self.current_term = term
            self.state = NodeState.FOLLOWER
            self.last_heartbeat = datetime.now()
            
        return {
            "term": self.current_term,
            "success": True
        }
import asyncio
import random
import json
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime
from src.nodes.base_node import BaseNode

class NodeState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

class LogEntry:
    def __init__(self, term: int, command: Any, index: int = None):
        self.term = term
        self.command = command
        self.index = index
        self.timestamp = datetime.now()
    
    def to_dict(self):
        return {
            "term": self.term,
            "command": self.command,
            "index": self.index,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        entry = cls(data["term"], data["command"], data.get("index"))
        if "timestamp" in data:
            entry.timestamp = datetime.fromisoformat(data["timestamp"])
        return entry

class RaftNode(BaseNode):
    """Enhanced Raft Consensus Algorithm with Log Replication"""
    
    def __init__(self, node_id: str, host: str, port: int):
        super().__init__(node_id, host, port)
        
        # Persistent state
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = []
        
        # Volatile state
        self.state = NodeState.FOLLOWER
        self.commit_index = -1
        self.last_applied = -1
        
        # Leader state
        self.next_index: Dict[str, int] = {}
        self.match_index: Dict[str, int] = {}
        
        # Timing
        self.election_timeout = random.uniform(150, 300) / 1000
        self.heartbeat_interval = 50 / 1000
        self.last_heartbeat = datetime.now()
        
        # State machine
        self.state_machine: Dict = {}
        
        # Network partition detection
        self.partition_detected = False
        self.connected_peers: set = set()
        
    async def start(self):
        """Start Raft node"""
        await super().start()
        asyncio.create_task(self.run_raft())
        asyncio.create_task(self.apply_committed_entries())
        
    async def run_raft(self):
        """Main Raft loop"""
        while self.running:
            try:
                if self.state == NodeState.FOLLOWER:
                    await self.run_follower()
                elif self.state == NodeState.CANDIDATE:
                    await self.run_candidate()
                elif self.state == NodeState.LEADER:
                    await self.run_leader()
            except Exception as e:
                self.logger.error(f"Error in Raft loop: {e}")
            await asyncio.sleep(0.01)
            
    async def run_follower(self):
        """Follower behavior"""
        time_since_heartbeat = (datetime.now() - self.last_heartbeat).total_seconds()
        if time_since_heartbeat > self.election_timeout:
            self.logger.info(f"Election timeout ({time_since_heartbeat:.3f}s), becoming candidate")
            self.state = NodeState.CANDIDATE
            
    async def run_candidate(self):
        """Candidate behavior - start election"""
        self.current_term += 1
        self.voted_for = self.node_id
        self.last_heartbeat = datetime.now()
        votes_received = 1
        
        self.logger.info(f"Starting election for term {self.current_term}")
        
        # Request votes from all peers
        vote_tasks = []
        for peer_id in self.peers:
            vote_tasks.append(self.request_vote(peer_id))
            
        if vote_tasks:
            results = await asyncio.gather(*vote_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, dict):
                    if result.get("term", 0) > self.current_term:
                        # Found higher term, revert to follower
                        self.current_term = result["term"]
                        self.state = NodeState.FOLLOWER
                        self.voted_for = None
                        return
                    if result.get("vote_granted"):
                        votes_received += 1
        
        # Check if won election (majority)
        majority = (len(self.peers) + 1) // 2 + 1
        if votes_received >= majority:
            self.logger.info(f"Won election with {votes_received}/{len(self.peers)+1} votes")
            self.state = NodeState.LEADER
            await self.become_leader()
        else:
            self.logger.info(f"Lost election with {votes_received}/{len(self.peers)+1} votes")
            self.state = NodeState.FOLLOWER
            self.voted_for = None
            self.election_timeout = random.uniform(150, 300) / 1000
            
    async def run_leader(self):
        """Leader behavior - send heartbeats and replicate log"""
        self.connected_peers.clear()
        
        # Send AppendEntries to all peers
        append_tasks = []
        for peer_id in self.peers:
            append_tasks.append(self.send_append_entries(peer_id))
            
        if append_tasks:
            results = await asyncio.gather(*append_tasks, return_exceptions=True)
            
            # Update commit index based on responses
            for i, (peer_id, result) in enumerate(zip(self.peers.keys(), results)):
                if isinstance(result, dict):
                    if result.get("success"):
                        self.connected_peers.add(peer_id)
                        # Update match_index for successful replication
                        if "match_index" in result:
                            self.match_index[peer_id] = result["match_index"]
                    elif result.get("term", 0) > self.current_term:
                        # Higher term found, step down
                        self.current_term = result["term"]
                        self.state = NodeState.FOLLOWER
                        self.voted_for = None
                        return
        
        # Update commit index
        await self.update_commit_index()
        
        # Detect network partition
        majority = (len(self.peers) + 1) // 2 + 1
        if len(self.connected_peers) + 1 < majority:
            self.logger.warning(f"Network partition detected! Connected to {len(self.connected_peers)}/{len(self.peers)} peers")
            self.partition_detected = True
        else:
            self.partition_detected = False
            
        await asyncio.sleep(self.heartbeat_interval)
        
    async def request_vote(self, peer_id: str) -> Dict:
        """Request vote from peer"""
        last_log_index = len(self.log) - 1
        last_log_term = self.log[-1].term if self.log else 0
        
        message = {
            "type": "request_vote",
            "term": self.current_term,
            "candidate_id": self.node_id,
            "last_log_index": last_log_index,
            "last_log_term": last_log_term
        }
        
        response = await self.send_to_peer(peer_id, message)
        return response or {"vote_granted": False, "term": self.current_term}
        
    async def send_append_entries(self, peer_id: str) -> Dict:
        """Send AppendEntries RPC to follower"""
        next_idx = self.next_index.get(peer_id, len(self.log))
        prev_log_index = next_idx - 1
        prev_log_term = self.log[prev_log_index].term if prev_log_index >= 0 else 0
        
        # Get entries to send
        entries = []
        if next_idx < len(self.log):
            entries = [e.to_dict() for e in self.log[next_idx:]]
        
        message = {
            "type": "append_entries",
            "term": self.current_term,
            "leader_id": self.node_id,
            "prev_log_index": prev_log_index,
            "prev_log_term": prev_log_term,
            "entries": entries,
            "leader_commit": self.commit_index
        }
        
        response = await self.send_to_peer(peer_id, message)
        
        if response and response.get("success"):
            # Update next_index and match_index
            if entries:
                self.next_index[peer_id] = next_idx + len(entries)
                self.match_index[peer_id] = self.next_index[peer_id] - 1
            response["match_index"] = self.match_index.get(peer_id, -1)
        elif response and not response.get("success"):
            # Decrement next_index and retry
            self.next_index[peer_id] = max(0, next_idx - 1)
            
        return response or {"success": False, "term": self.current_term}
        
    async def become_leader(self):
        """Initialize leader state"""
        self.logger.info(f"Became leader for term {self.current_term}")
        
        # Initialize next_index and match_index
        for peer_id in self.peers:
            self.next_index[peer_id] = len(self.log)
            self.match_index[peer_id] = -1
        
        # Send initial empty AppendEntries (heartbeat)
        tasks = [self.send_append_entries(peer_id) for peer_id in self.peers]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def update_commit_index(self):
        """Update commit index based on majority replication"""
        if self.state != NodeState.LEADER:
            return
        
        # Find highest index replicated on majority
        for n in range(len(self.log) - 1, self.commit_index, -1):
            if self.log[n].term == self.current_term:
                replicated_count = 1  # Leader has it
                for peer_id in self.peers:
                    if self.match_index.get(peer_id, -1) >= n:
                        replicated_count += 1
                
                majority = (len(self.peers) + 1) // 2 + 1
                if replicated_count >= majority:
                    self.commit_index = n
                    self.logger.debug(f"Updated commit_index to {n}")
                    break
    
    async def apply_committed_entries(self):
        """Apply committed log entries to state machine"""
        while self.running:
            if self.last_applied < self.commit_index:
                self.last_applied += 1
                entry = self.log[self.last_applied]
                
                # Apply to state machine
                await self.apply_to_state_machine(entry.command)
                self.logger.debug(f"Applied entry {self.last_applied}: {entry.command}")
            
            await asyncio.sleep(0.01)
    
    async def apply_to_state_machine(self, command: Dict):
        """Apply command to state machine - override in subclasses"""
        pass
    
    async def replicate_command(self, command: Dict) -> bool:
        """Replicate command across cluster"""
        if self.state != NodeState.LEADER:
            return False
        
        if self.partition_detected:
            self.logger.warning("Cannot replicate: network partition detected")
            return False
        
        # Add to log
        entry = LogEntry(self.current_term, command, len(self.log))
        self.log.append(entry)
        
        self.logger.info(f"Replicating command: {command}")
        
        # Wait for replication to majority
        max_wait = 1.0  # 1 second timeout
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < max_wait:
            if self.commit_index >= entry.index:
                return True
            await asyncio.sleep(0.05)
        
        self.logger.warning(f"Command replication timeout: {command}")
        return False
        
    async def process_message(self, message: Dict) -> Dict:
        """Process Raft messages"""
        msg_type = message.get("type")
        
        if msg_type == "request_vote":
            return await self.handle_request_vote(message)
        elif msg_type == "append_entries":
            return await self.handle_append_entries(message)
            
        return {"status": "unknown_message_type"}
        
    async def handle_request_vote(self, message: Dict) -> Dict:
        """Handle RequestVote RPC"""
        term = message["term"]
        candidate_id = message["candidate_id"]
        last_log_index = message["last_log_index"]
        last_log_term = message["last_log_term"]
        
        # Update term if higher
        if term > self.current_term:
            self.current_term = term
            self.state = NodeState.FOLLOWER
            self.voted_for = None
        
        vote_granted = False
        
        # Check if can vote for candidate
        if term == self.current_term:
            if self.voted_for is None or self.voted_for == candidate_id:
                # Check if candidate's log is at least as up-to-date
                my_last_log_index = len(self.log) - 1
                my_last_log_term = self.log[-1].term if self.log else 0
                
                log_ok = (last_log_term > my_last_log_term or 
                         (last_log_term == my_last_log_term and last_log_index >= my_last_log_index))
                
                if log_ok:
                    self.voted_for = candidate_id
                    self.last_heartbeat = datetime.now()
                    vote_granted = True
                    self.logger.info(f"Voted for {candidate_id} in term {term}")
        
        return {
            "term": self.current_term,
            "vote_granted": vote_granted
        }
        
    async def handle_append_entries(self, message: Dict) -> Dict:
        """Handle AppendEntries RPC"""
        term = message["term"]
        leader_id = message["leader_id"]
        prev_log_index = message["prev_log_index"]
        prev_log_term = message["prev_log_term"]
        entries = message["entries"]
        leader_commit = message["leader_commit"]
        
        # Update term if higher
        if term > self.current_term:
            self.current_term = term
            self.state = NodeState.FOLLOWER
            self.voted_for = None
        
        # Reset election timer
        if term == self.current_term:
            self.state = NodeState.FOLLOWER
            self.last_heartbeat = datetime.now()
        
        # Reply false if term < currentTerm
        if term < self.current_term:
            return {"term": self.current_term, "success": False}
        
        # Check if log contains entry at prev_log_index with prev_log_term
        if prev_log_index >= 0:
            if prev_log_index >= len(self.log) or self.log[prev_log_index].term != prev_log_term:
                return {"term": self.current_term, "success": False}
        
        # Append new entries
        if entries:
            insert_index = prev_log_index + 1
            
            # Delete conflicting entries
            if insert_index < len(self.log):
                self.log = self.log[:insert_index]
            
            # Append new entries
            for entry_dict in entries:
                entry = LogEntry.from_dict(entry_dict)
                self.log.append(entry)
            
            self.logger.debug(f"Appended {len(entries)} entries from {leader_id}")
        
        # Update commit index
        if leader_commit > self.commit_index:
            self.commit_index = min(leader_commit, len(self.log) - 1)
        
        return {"term": self.current_term, "success": True}
    
    def is_leader(self) -> bool:
        """Check if this node is the leader"""
        return self.state == NodeState.LEADER and not self.partition_detected
    
    def get_leader_id(self) -> Optional[str]:
        """Get current leader ID"""
        if self.state == NodeState.LEADER:
            return self.node_id
        return None 
from enum import Enum
from collections import defaultdict
from typing import Dict, List
from src.consensus.raft import RaftNode, NodeState

class LockType(Enum):
    SHARED = "shared"
    EXCLUSIVE = "exclusive"

class DistributedLockManager(RaftNode):
    """Distributed Lock Manager using Raft"""
    def __init__(self, node_id: str, host: str, port: int):
        super().__init__(node_id, host, port)
        self.locks: Dict[str, Dict] = {}
        self.wait_queue: Dict[str, List] = defaultdict(list)
        
    async def acquire_lock(self, resource: str, lock_type: LockType, client_id: str) -> bool:
        """Acquire lock on resource"""
        if self.state != NodeState.LEADER:
            return False
            
        if resource not in self.locks:
            self.locks[resource] = {
                "type": lock_type,
                "holders": {client_id}
            }
            self.logger.info(f"Lock acquired: {resource} by {client_id} ({lock_type.value})")
            return True
            
        current_lock = self.locks[resource]
        
        if lock_type == LockType.SHARED and current_lock["type"] == LockType.SHARED:
            current_lock["holders"].add(client_id)
            return True
            
        self.wait_queue[resource].append({
            "client_id": client_id,
            "lock_type": lock_type
        })
        return False
        
    async def release_lock(self, resource: str, client_id: str) -> bool:
        """Release lock on resource"""
        if self.state != NodeState.LEADER:
            return False
            
        if resource not in self.locks:
            return False
            
        lock = self.locks[resource]
        if client_id in lock["holders"]:
            lock["holders"].remove(client_id)
            self.logger.info(f"Lock released: {resource} by {client_id}")
            
            if not lock["holders"]:
                del self.locks[resource]
                await self.process_wait_queue(resource)
                
            return True
        return False
        
    async def process_wait_queue(self, resource: str):
        """Process waiting lock requests"""
        if resource not in self.wait_queue or not self.wait_queue[resource]:
            return
            
        next_request = self.wait_queue[resource].pop(0)
        await self.acquire_lock(
            resource, 
            next_request["lock_type"], 
            next_request["client_id"]
        )
        
    async def detect_deadlock(self) -> List[str]:
        """Detect deadlocks in distributed system"""
        wait_for_graph = defaultdict(set)
        
        for resource, waiters in self.wait_queue.items():
            if resource in self.locks:
                holders = self.locks[resource]["holders"]
                for waiter in waiters:
                    for holder in holders:
                        wait_for_graph[waiter["client_id"]].add(holder)
        
        deadlocks = []
        visited = set()
        
        def has_cycle(node, path):
            if node in path:
                return path[path.index(node):]
            if node in visited:
                return None
                
            visited.add(node)
            path.append(node)
            
            for neighbor in wait_for_graph.get(node, []):
                cycle = has_cycle(neighbor, path.copy())
                if cycle:
                    return cycle
            return None
            
        for node in wait_for_graph:
            if node not in visited:
                cycle = has_cycle(node, [])
                if cycle:
                    deadlocks.append(" -> ".join(cycle))
                    
        return deadlocks
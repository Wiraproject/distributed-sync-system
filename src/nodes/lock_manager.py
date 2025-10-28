from enum import Enum
from collections import defaultdict
from typing import Dict, List, Optional, Set
from datetime import datetime, timedelta
import asyncio
from src.consensus.raft import RaftNode, NodeState

class LockType(Enum):
    SHARED = "shared"
    EXCLUSIVE = "exclusive"

class LockRequest:
    def __init__(self, resource: str, lock_type: LockType, client_id: str, timestamp: datetime = None):
        self.resource = resource
        self.lock_type = lock_type
        self.client_id = client_id
        self.timestamp = timestamp or datetime.now()
        self.timeout = None
    
    def to_dict(self):
        return {
            "resource": self.resource,
            "lock_type": self.lock_type.value,
            "client_id": self.client_id,
            "timestamp": self.timestamp.isoformat(),
            "timeout": self.timeout.isoformat() if self.timeout else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        req = cls(
            data["resource"],
            LockType(data["lock_type"]),
            data["client_id"],
            datetime.fromisoformat(data["timestamp"])
        )
        if data.get("timeout"):
            req.timeout = datetime.fromisoformat(data["timeout"])
        return req

class DistributedLockManager(RaftNode):
    """Enhanced Distributed Lock Manager with Raft Consensus"""
    def __init__(self, node_id: str, host: str, port: int):
        super().__init__(node_id, host, port)
        
        self.locks: Dict[str, Dict] = {} 
        self.wait_queue: Dict[str, List[LockRequest]] = defaultdict(list)
        
        self.lock_graph: Dict[str, Set[str]] = defaultdict(set)
        
        self.lock_timeouts: Dict[str, Dict[str, datetime]] = defaultdict(dict) 
        
        self.lock_acquisition_times: List[float] = []
        self.deadlock_count = 0
        
    async def start(self):
        """Start lock manager"""
        await super().start()
        asyncio.create_task(self.cleanup_expired_locks())
        asyncio.create_task(self.periodic_deadlock_detection())
        
    async def acquire_lock(self, resource: str, lock_type: LockType, client_id: str, 
                          timeout_seconds: float = None) -> Dict:
        """
        Acquire lock on resource
        
        Returns:
            Dict with keys: success (bool), message (str), lock_id (str optional)
        """
        if not self.is_leader():
            return {
                "success": False,
                "message": "Not the leader",
                "leader_id": self.get_leader_id()
            }
        
        if self.partition_detected:
            return {
                "success": False,
                "message": "Network partition detected - cannot guarantee consistency"
            }
        
        request = LockRequest(resource, lock_type, client_id)
        if timeout_seconds:
            request.timeout = datetime.now() + timedelta(seconds=timeout_seconds)
        
        can_acquire, reason = self._can_acquire_lock(resource, lock_type, client_id)
        
        if can_acquire:
            command = {
                "operation": "acquire_lock",
                "request": request.to_dict()
            }
            
            success = await self.replicate_command(command)
            
            if success:
                self.logger.info(f"Lock acquired: {resource} by {client_id} ({lock_type.value})")
                return {
                    "success": True,
                    "message": "Lock acquired",
                    "lock_id": f"{resource}:{client_id}"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to replicate lock acquisition"
                }
        else:
            self.wait_queue[resource].append(request)
            self._update_lock_graph(client_id, resource)
            
            self.logger.info(f"Lock request queued: {resource} by {client_id} ({lock_type.value}) - {reason}")
            return {
                "success": False,
                "message": f"Lock unavailable: {reason}",
                "queued": True,
                "position": len(self.wait_queue[resource])
            }
    
    def _can_acquire_lock(self, resource: str, lock_type: LockType, client_id: str) -> tuple:
        """
        Check if lock can be acquired
        
        Returns:
            (can_acquire: bool, reason: str)
        """
        if resource not in self.locks:
            return True, "Resource available"
        
        current_lock = self.locks[resource]
        
        if client_id in current_lock["holders"]:
            return True, "Client already holds lock"
        
        if lock_type == LockType.SHARED and current_lock["type"] == LockType.SHARED:
            return True, "Compatible lock type"
        
        holders = ", ".join(current_lock["holders"])
        return False, f"Resource locked by: {holders}"
    
    async def release_lock(self, resource: str, client_id: str) -> Dict:
        """Release lock on resource"""
        if not self.is_leader():
            return {
                "success": False,
                "message": "Not the leader",
                "leader_id": self.get_leader_id()
            }
        
        if resource not in self.locks:
            return {
                "success": False,
                "message": "Lock not found"
            }
        
        lock = self.locks[resource]
        if client_id not in lock["holders"]:
            return {
                "success": False,
                "message": "Client does not hold this lock"
            }
        
        command = {
            "operation": "release_lock",
            "resource": resource,
            "client_id": client_id
        }
        
        success = await self.replicate_command(command)
        
        if success:
            self.logger.info(f"Lock released: {resource} by {client_id}")
            return {
                "success": True,
                "message": "Lock released"
            }
        else:
            return {
                "success": False,
                "message": "Failed to replicate lock release"
            }
    
    async def apply_to_state_machine(self, command: Dict):
        """Apply lock operations to state machine"""
        operation = command.get("operation")
        
        if operation == "acquire_lock":
            request = LockRequest.from_dict(command["request"])
            self._apply_lock_acquisition(request)
            
        elif operation == "release_lock":
            resource = command["resource"]
            client_id = command["client_id"]
            self._apply_lock_release(resource, client_id)
    
    def _apply_lock_acquisition(self, request: LockRequest):
        """Apply lock acquisition to state"""
        resource = request.resource
        
        if resource not in self.locks:
            self.locks[resource] = {
                "type": request.lock_type,
                "holders": {request.client_id},
                "timestamp": request.timestamp
            }
        else:
            self.locks[resource]["holders"].add(request.client_id)
        
        if request.timeout:
            self.lock_timeouts[resource][request.client_id] = request.timeout
        
        if resource in self.wait_queue:
            self.wait_queue[resource] = [
                r for r in self.wait_queue[resource] 
                if r.client_id != request.client_id
            ]
    
    def _apply_lock_release(self, resource: str, client_id: str):
        """Apply lock release to state"""
        if resource in self.locks:
            lock = self.locks[resource]
            lock["holders"].discard(client_id)
            
            if resource in self.lock_timeouts:
                self.lock_timeouts[resource].pop(client_id, None)
            
            if not lock["holders"]:
                del self.locks[resource]
                asyncio.create_task(self.process_wait_queue(resource))
            
            self._remove_from_lock_graph(client_id)
    
    async def process_wait_queue(self, resource: str):
        """Process waiting lock requests"""
        if resource not in self.wait_queue or not self.wait_queue[resource]:
            return
        
        while self.wait_queue[resource]:
            next_request = self.wait_queue[resource][0]
            
            can_acquire, _ = self._can_acquire_lock(
                resource, 
                next_request.lock_type, 
                next_request.client_id
            )
            
            if can_acquire:
                self.wait_queue[resource].pop(0)
                
                command = {
                    "operation": "acquire_lock",
                    "request": next_request.to_dict()
                }
                await self.replicate_command(command)
                
                self.logger.info(f"Processed queued lock request: {resource} for {next_request.client_id}")
                
                if next_request.lock_type == LockType.EXCLUSIVE:
                    break
            else:
                break
    
    async def detect_deadlock(self) -> List[List[str]]:
        """
        Detect deadlocks using cycle detection in wait-for graph
        
        Returns:
            List of deadlock cycles, each cycle is a list of client_ids
        """
        deadlocks = []
        visited = set()
        rec_stack = set()
        
        def dfs(node: str, path: List[str]) -> Optional[List[str]]:
            if node in rec_stack:
                cycle_start = path.index(node)
                return path[cycle_start:]
            
            if node in visited:
                return None
            
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.lock_graph.get(node, []):
                cycle = dfs(neighbor, path.copy())
                if cycle:
                    return cycle
            
            rec_stack.remove(node)
            return None
        
        for client in list(self.lock_graph.keys()):
            if client not in visited:
                cycle = dfs(client, [])
                if cycle:
                    deadlocks.append(cycle)
                    self.deadlock_count += 1
        
        return deadlocks
    
    def _update_lock_graph(self, client_id: str, resource: str):
        """Update wait-for graph when client waits for resource"""
        if resource in self.locks:
            holders = self.locks[resource]["holders"]
            self.lock_graph[client_id].update(holders)
    
    def _remove_from_lock_graph(self, client_id: str):
        """Remove client from wait-for graph"""
        self.lock_graph.pop(client_id, None)
        
        for waiting_client in self.lock_graph:
            self.lock_graph[waiting_client].discard(client_id)
    
    async def resolve_deadlock(self, cycle: List[str]) -> Dict:
        """
        Resolve deadlock by aborting youngest transaction
        
        Returns:
            Dict with resolution details
        """
        if not cycle:
            return {"success": False, "message": "No cycle provided"}
        
        victim = None
        latest_timestamp = None
        
        for resource, waiters in self.wait_queue.items():
            for waiter in waiters:
                if waiter.client_id in cycle:
                    if latest_timestamp is None or waiter.timestamp > latest_timestamp:
                        latest_timestamp = waiter.timestamp
                        victim = waiter.client_id
        
        if victim:
            for resource in list(self.wait_queue.keys()):
                self.wait_queue[resource] = [
                    r for r in self.wait_queue[resource] 
                    if r.client_id != victim
                ]

            self._remove_from_lock_graph(victim)
            
            self.logger.warning(f"Deadlock resolved: aborted client {victim} from cycle {' -> '.join(cycle)}")
            
            return {
                "success": True,
                "message": "Deadlock resolved",
                "victim": victim,
                "cycle": cycle
            }
        
        return {"success": False, "message": "Could not find victim to abort"}
    
    async def periodic_deadlock_detection(self):
        """Periodically check for and resolve deadlocks"""
        while self.running:
            await asyncio.sleep(5)
            
            if self.is_leader():
                deadlocks = await self.detect_deadlock()
                
                if deadlocks:
                    self.logger.warning(f"Detected {len(deadlocks)} deadlock(s)")
                    
                    for cycle in deadlocks:
                        await self.resolve_deadlock(cycle)
    
    async def cleanup_expired_locks(self):
        """Clean up locks that have exceeded their timeout"""
        while self.running:
            await asyncio.sleep(1) 
            
            if not self.is_leader():
                continue
            
            current_time = datetime.now()
            expired = []
            
            for resource, timeouts in list(self.lock_timeouts.items()):
                for client_id, timeout in list(timeouts.items()):
                    if current_time > timeout:
                        expired.append((resource, client_id))
            
            for resource, client_id in expired:
                self.logger.info(f"Lock timeout expired: {resource} by {client_id}")
                await self.release_lock(resource, client_id)
    
    def get_lock_status(self, resource: Optional[str] = None) -> Dict:
        """Get current lock status"""
        if resource:
            if resource in self.locks:
                lock = self.locks[resource]
                return {
                    "resource": resource,
                    "type": lock["type"].value,
                    "holders": list(lock["holders"]),
                    "timestamp": lock["timestamp"].isoformat(),
                    "waiting": len(self.wait_queue.get(resource, []))
                }
            return {"resource": resource, "status": "available"}
        
        return {
            "locks": {
                res: {
                    "type": lock["type"].value,
                    "holders": list(lock["holders"]),
                    "timestamp": lock["timestamp"].isoformat(),
                    "waiting": len(self.wait_queue.get(res, []))
                }
                for res, lock in self.locks.items()
            },
            "total_locks": len(self.locks),
            "total_waiting": sum(len(q) for q in self.wait_queue.values())
        }
    
    def get_metrics(self) -> Dict:
        """Get lock manager metrics"""
        return {
            "active_locks": len(self.locks),
            "waiting_requests": sum(len(q) for q in self.wait_queue.values()),
            "deadlocks_detected": self.deadlock_count,
            "is_leader": self.is_leader(),
            "current_term": self.current_term,
            "partition_detected": self.partition_detected,
            "raft_state": self.state.value
        }
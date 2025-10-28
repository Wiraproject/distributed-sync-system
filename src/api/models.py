from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class LockTypeEnum(str, Enum):
    """Lock type enumeration"""
    SHARED = "shared"
    EXCLUSIVE = "exclusive"

class NodeStateEnum(str, Enum):
    """Raft node state"""
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"

class LockAcquireRequest(BaseModel):
    """Request to acquire a lock"""
    resource: str = Field(..., description="Resource identifier to lock", example="user:123")
    client_id: str = Field(..., description="Client requesting the lock", example="client_1")
    lock_type: LockTypeEnum = Field(default=LockTypeEnum.EXCLUSIVE, description="Type of lock")
    timeout_seconds: Optional[float] = Field(None, description="Lock timeout in seconds", example=30.0)
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "resource": "database:users",
                    "client_id": "service_a",
                    "lock_type": "exclusive",
                    "timeout_seconds": 60.0
                }
            ]
        }
    }

class LockAcquireResponse(BaseModel):
    """Response from lock acquisition"""
    success: bool = Field(..., description="Whether lock was acquired")
    message: str = Field(..., description="Status message")
    lock_id: Optional[str] = Field(None, description="Lock identifier if successful")
    queued: Optional[bool] = Field(None, description="Whether request was queued")
    position: Optional[int] = Field(None, description="Position in queue if queued")
    leader_id: Optional[str] = Field(None, description="Leader node ID for redirect")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Lock acquired",
                    "lock_id": "database:users:service_a"
                }
            ]
        }
    }

class LockReleaseRequest(BaseModel):
    """Request to release a lock"""
    resource: str = Field(..., description="Resource identifier to unlock")
    client_id: str = Field(..., description="Client releasing the lock")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "resource": "database:users",
                    "client_id": "service_a"
                }
            ]
        }
    }

class LockReleaseResponse(BaseModel):
    """Response from lock release"""
    success: bool = Field(..., description="Whether lock was released")
    message: str = Field(..., description="Status message")
    leader_id: Optional[str] = Field(None, description="Leader node ID for redirect")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "message": "Lock released"
                }
            ]
        }
    }

class LockStatusResponse(BaseModel):
    """Lock status information"""
    resource: str = Field(..., description="Resource identifier")
    type: Optional[str] = Field(None, description="Lock type (shared/exclusive)")
    holders: Optional[List[str]] = Field(None, description="Current lock holders")
    timestamp: Optional[str] = Field(None, description="Lock acquisition timestamp")
    waiting: Optional[int] = Field(None, description="Number of waiting requests")
    status: Optional[str] = Field(None, description="Status if lock is available")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "resource": "database:users",
                    "type": "exclusive",
                    "holders": ["service_a"],
                    "timestamp": "2025-01-28T10:30:00",
                    "waiting": 2
                }
            ]
        }
    }

class NodeStatusResponse(BaseModel):
    """Node status and Raft state"""
    node_id: str = Field(..., description="Node identifier")
    state: NodeStateEnum = Field(..., description="Current Raft state")
    is_leader: bool = Field(..., description="Whether this node is the leader")
    current_term: int = Field(..., description="Current Raft term")
    partition_detected: bool = Field(..., description="Whether network partition is detected")
    peers: List[str] = Field(..., description="List of peer node IDs")
    commit_index: int = Field(..., description="Highest log entry known to be committed")
    last_applied: int = Field(..., description="Highest log entry applied to state machine")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "node_id": "node_0",
                    "state": "leader",
                    "is_leader": True,
                    "current_term": 5,
                    "partition_detected": False,
                    "peers": ["node_1", "node_2"],
                    "commit_index": 42,
                    "last_applied": 42
                }
            ]
        }
    }

class MetricsResponse(BaseModel):
    """System metrics"""
    active_locks: int = Field(..., description="Number of active locks")
    waiting_requests: int = Field(..., description="Number of waiting lock requests")
    deadlocks_detected: int = Field(..., description="Total deadlocks detected")
    is_leader: bool = Field(..., description="Whether this node is leader")
    current_term: int = Field(..., description="Current Raft term")
    partition_detected: bool = Field(..., description="Network partition detected")
    raft_state: str = Field(..., description="Current Raft state")

class DeadlockCycle(BaseModel):
    """Deadlock cycle information"""
    cycle_id: int = Field(..., description="Cycle identifier")
    clients: List[str] = Field(..., description="List of client IDs in cycle")
    path: str = Field(..., description="String representation of cycle path")

class DeadlockDetectionResponse(BaseModel):
    """Deadlock detection result"""
    deadlocks_found: int = Field(..., description="Number of deadlocks found")
    cycles: List[DeadlockCycle] = Field(..., description="List of deadlock cycles")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "deadlocks_found": 1,
                    "cycles": [
                        {
                            "cycle_id": 0,
                            "clients": ["client_1", "client_2", "client_3"],
                            "path": "client_1 -> client_2 -> client_3 -> client_1"
                        }
                    ]
                }
            ]
        }
    }

class DeadlockResolutionResponse(BaseModel):
    """Deadlock resolution result"""
    success: bool = Field(..., description="Whether deadlock was resolved")
    message: str = Field(..., description="Resolution message")
    victim: Optional[str] = Field(None, description="Client ID that was aborted")
    cycle: Optional[List[str]] = Field(None, description="Resolved cycle")

class ErrorResponse(BaseModel):
    """Error response"""
    error: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    details: Optional[dict] = Field(None, description="Additional error details")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "error": "Lock acquisition failed",
                    "status_code": 400,
                    "details": {"reason": "Resource already locked"}
                }
            ]
        }
    }

class AddPeerRequest(BaseModel):
    """Request to add peer node"""
    peer_id: str = Field(..., description="Peer node identifier")
    host: str = Field(..., description="Peer hostname/IP")
    port: int = Field(..., description="Peer port number")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "peer_id": "node_3",
                    "host": "192.168.1.103",
                    "port": 8003
                }
            ]
        }
    }

class PeerInfo(BaseModel):
    """Peer node information"""
    peer_id: str = Field(..., description="Peer identifier")
    host: str = Field(..., description="Peer hostname/IP")
    port: int = Field(..., description="Peer port")

class PeerListResponse(BaseModel):
    """List of peer nodes"""
    peers: List[PeerInfo] = Field(..., description="List of peers")
    total_peers: int = Field(..., description="Total number of peers")
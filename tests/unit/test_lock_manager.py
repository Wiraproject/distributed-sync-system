import pytest
from src.nodes.lock_manager import DistributedLockManager, LockType
from src.consensus.raft import NodeState


@pytest.mark.asyncio
async def test_acquire_exclusive_lock():
    manager = DistributedLockManager("lock_mgr", "localhost", 8000)
    manager.state = NodeState.LEADER
    
    result = await manager.acquire_lock("resource_1", LockType.EXCLUSIVE, "client_1")
    assert result == True
    assert "resource_1" in manager.locks

@pytest.mark.asyncio
async def test_shared_locks():
    manager = DistributedLockManager("lock_mgr", "localhost", 8000)
    manager.state = NodeState.LEADER
    
    result1 = await manager.acquire_lock("resource_1", LockType.SHARED, "client_1")
    assert result1 == True
    
    result2 = await manager.acquire_lock("resource_1", LockType.SHARED, "client_2")
    assert result2 == True
    
    assert len(manager.locks["resource_1"]["holders"]) == 2

@pytest.mark.asyncio
async def test_exclusive_blocks_shared():
    manager = DistributedLockManager("lock_mgr", "localhost", 8000)
    manager.state = NodeState.LEADER
    
    await manager.acquire_lock("resource_1", LockType.EXCLUSIVE, "client_1")
    
    result = await manager.acquire_lock("resource_1", LockType.SHARED, "client_2")
    assert result == False
    assert len(manager.wait_queue["resource_1"]) == 1

@pytest.mark.asyncio
async def test_lock_release():
    manager = DistributedLockManager("lock_mgr", "localhost", 8000)
    manager.state = NodeState.LEADER
    
    await manager.acquire_lock("resource_1", LockType.EXCLUSIVE, "client_1")
    result = await manager.release_lock("resource_1", "client_1")
    
    assert result == True
    assert "resource_1" not in manager.locks

@pytest.mark.asyncio
async def test_deadlock_detection():
    manager = DistributedLockManager("lock_mgr", "localhost", 8000)
    manager.state = NodeState.LEADER
    
    await manager.acquire_lock("resource_1", LockType.EXCLUSIVE, "client_1")
    await manager.acquire_lock("resource_2", LockType.EXCLUSIVE, "client_2")
    
    await manager.acquire_lock("resource_1", LockType.EXCLUSIVE, "client_2")
    await manager.acquire_lock("resource_2", LockType.EXCLUSIVE, "client_1")
    
    deadlocks = await manager.detect_deadlock()
    assert len(deadlocks) > 0
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from src.api.models import (
    LockAcquireRequest, LockAcquireResponse,
    LockReleaseRequest, LockReleaseResponse,
    LockStatusResponse, NodeStatusResponse,
)
from src.nodes.lock_manager import DistributedLockManager, LockType

lock_manager: Optional[DistributedLockManager] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global lock_manager

    import os
    node_id = os.getenv("NODE_ID", "node_0")
    host = os.getenv("NODE_HOST", "0.0.0.0")
    port = int(os.getenv("NODE_PORT", "8000"))
    
    logging.info(f"Starting Lock Manager Node: {node_id}")
    
    lock_manager = DistributedLockManager(node_id, host, port)
    
    peer_nodes = os.getenv("PEER_NODES", "")
    if peer_nodes:
        for peer in peer_nodes.split(","):
            parts = peer.split(":")
            if len(parts) == 3:
                peer_id = parts[0]
                peer_host = parts[1]
                peer_port = int(parts[2])
                lock_manager.add_peer(peer_id, peer_host, peer_port)
                logging.info(f"Added peer: {peer_id} at {peer_host}:{peer_port}")
    
    await lock_manager.start()
    logging.info("Lock Manager started successfully")

    yield
    
    logging.info("Shutting down Lock Manager")
    await lock_manager.stop()

app = FastAPI(
    title="Distributed Lock Manager API",
    description="REST API for distributed lock management using Raft consensus",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logging.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "node_id": lock_manager.node_id if lock_manager else "unknown",
        "is_running": lock_manager.running if lock_manager else False
    }

# ========== Lock Manager Endpoints ==========
@app.get("/status",
         response_model=NodeStatusResponse,
         tags=["Status"])
async def get_node_status():
    if not lock_manager:
        raise HTTPException(status_code=503, detail="Lock manager not initialized")
    
    return NodeStatusResponse(
        node_id=lock_manager.node_id,
        state=lock_manager.state.value,
        is_leader=lock_manager.is_leader(),
        current_term=lock_manager.current_term,
        partition_detected=lock_manager.partition_detected,
        peers=list(lock_manager.peers.keys()),
        commit_index=lock_manager.commit_index,
        last_applied=lock_manager.last_applied
    )

@app.get("/metrics", tags=["Metrics"])
async def get_metrics():
    """Get lock manager metrics"""
    if not lock_manager:
        raise HTTPException(status_code=503, detail="Lock manager not initialized")
    
    return lock_manager.get_metrics()

@app.post("/locks/acquire", 
          response_model=LockAcquireResponse,
          tags=["Locks"],
          status_code=status.HTTP_200_OK)
async def acquire_lock(request: LockAcquireRequest):
    if not lock_manager:
        raise HTTPException(status_code=503, detail="Lock manager not initialized")
    
    lock_type = LockType.SHARED if request.lock_type == "shared" else LockType.EXCLUSIVE
    
    result = await lock_manager.acquire_lock(
        resource=request.resource,
        lock_type=lock_type,
        client_id=request.client_id,
        timeout_seconds=request.timeout_seconds
    )
    
    if result["success"]:
        return LockAcquireResponse(**result)
    elif result.get("queued"):
        return LockAcquireResponse(**result)
    else:
        if result.get("leader_id"):
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                detail=f"Not the leader. Redirect to: {result['leader_id']}",
                headers={"Location": f"/locks/acquire"}
            )
        raise HTTPException(status_code=400, detail=result["message"])

@app.post("/locks/release",
          response_model=LockReleaseResponse,
          tags=["Locks"])
async def release_lock(request: LockReleaseRequest):
    if not lock_manager:
        raise HTTPException(status_code=503, detail="Lock manager not initialized")
    
    result = await lock_manager.release_lock(
        resource=request.resource,
        client_id=request.client_id
    )
    
    if result["success"]:
        return LockReleaseResponse(**result)
    else:
        if result.get("leader_id"):
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                detail=f"Not the leader. Redirect to: {result['leader_id']}"
            )
        raise HTTPException(status_code=400, detail=result["message"])

@app.get("/locks/{resource}",
         response_model=LockStatusResponse,
         tags=["Locks"])
async def get_lock_status(resource: str):
    if not lock_manager:
        raise HTTPException(status_code=503, detail="Lock manager not initialized")
    
    status_data = lock_manager.get_lock_status(resource)
    return LockStatusResponse(**status_data)

@app.get("/locks", tags=["Locks"])
async def get_all_locks():
    if not lock_manager:
        raise HTTPException(status_code=503, detail="Lock manager not initialized")
    
    return lock_manager.get_lock_status()


@app.post("/internal/message", tags=["Internal"])
async def handle_internal_message(message: dict):
    if not lock_manager:
        raise HTTPException(status_code=503, detail="Lock manager not initialized")
    
    try:
        response = await lock_manager.process_message(message)
        return response
    except Exception as e:
        logging.error(f"Error processing internal message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv("API_PORT", "8080"))
    
    uvicorn.run(
        "src.api.lock_manager_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
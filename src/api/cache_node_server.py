from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from typing import Optional

from src.api.models import (
    CacheGetRequest, CacheGetResponse,
    CacheSetRequest, CacheSetResponse,
    CacheDeleteRequest, CacheDeleteResponse,
    CacheMetricsResponse, CacheStatusResponse
)
from src.nodes.cache_node import MESICache

# Global cache instance
cache_manager: Optional[MESICache] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global cache_manager
    
    import os
    node_id = os.getenv("NODE_ID", "cache_0")
    host = os.getenv("NODE_HOST", "0.0.0.0")
    port = int(os.getenv("NODE_PORT", "7000"))
    capacity = int(os.getenv("CACHE_CAPACITY", "100"))
    
    logging.info(f"Starting Distributed Cache Node: {node_id}")
    
    cache_manager = MESICache(node_id, host, port, capacity)
    
    # Add peers
    peer_nodes = os.getenv("PEER_NODES", "")
    if peer_nodes:
        for peer in peer_nodes.split(","):
            parts = peer.split(":")
            if len(parts) == 3:
                peer_id = parts[0]
                peer_host = parts[1]
                peer_port = int(parts[2])
                cache_manager.add_peer(peer_id, peer_host, peer_port)
                logging.info(f"Added peer: {peer_id} at {peer_host}:{peer_port}")
    
    await cache_manager.start()
    
    logging.info(f"Cache Manager started (capacity: {capacity})")
    
    yield
    
    logging.info("Shutting down Cache Manager")
    await cache_manager.stop()

# Create FastAPI app
app = FastAPI(
    title="Distributed Cache System API",
    description="REST API for distributed cache with MESI coherence protocol",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "node_id": cache_manager.node_id if cache_manager else "unknown",
        "is_running": cache_manager.running if cache_manager else False,
        "type": "cache"
    }

# ========== Cache Endpoints ==========

@app.post("/cache/get", 
          response_model=CacheGetResponse,
          tags=["Cache"])
async def get_cache(request: CacheGetRequest):
    """
    Get value from distributed cache
    
    - **key**: Cache key to retrieve
    
    Implements MESI protocol for cache coherence.
    """
    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache manager not initialized")
    
    try:
        value = await cache_manager.read(request.key)
        
        # Check if it was a hit or miss
        is_hit = request.key in cache_manager.cache and \
                cache_manager.cache[request.key].state.value != "I"
        
        # Get MESI state
        state = None
        if request.key in cache_manager.cache:
            state = cache_manager.cache[request.key].state.value
        
        return CacheGetResponse(
            success=value is not None,
            key=request.key,
            value=value,
            hit=is_hit,
            state=state
        )
    except Exception as e:
        logging.error(f"Cache get error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cache/set",
          response_model=CacheSetResponse,
          tags=["Cache"])
async def set_cache(request: CacheSetRequest):
    """
    Set value in distributed cache
    
    - **key**: Cache key
    - **value**: Value to cache
    
    Invalidates the key in all other cache nodes (MESI protocol).
    """
    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache manager not initialized")
    
    try:
        success = await cache_manager.write(request.key, request.value)
        
        return CacheSetResponse(
            success=success,
            key=request.key,
            message=f"Value cached successfully in state MODIFIED"
        )
    except Exception as e:
        logging.error(f"Cache set error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cache/delete",
          response_model=CacheDeleteResponse,
          tags=["Cache"])
async def delete_cache(request: CacheDeleteRequest):
    """
    Delete key from distributed cache
    
    Removes key from this cache and invalidates in all peer caches.
    """
    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache manager not initialized")
    
    try:
        success = await cache_manager.delete(request.key)
        
        return CacheDeleteResponse(
            success=success,
            key=request.key,
            message=f"Key deleted successfully" if success else "Key not found"
        )
    except Exception as e:
        logging.error(f"Cache delete error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cache/status/{key}",
         response_model=CacheStatusResponse,
         tags=["Cache"])
async def get_key_status(key: str):
    """
    Get MESI status of a specific key
    
    Shows whether key exists, its MESI state, and last access time.
    """
    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache manager not initialized")
    
    try:
        status_info = cache_manager.get_key_status(key)
        
        # Query peers to see who else has this key
        nodes_holding = [cache_manager.node_id] if status_info["exists"] else []
        
        for peer_id in cache_manager.peers:
            response = await cache_manager.send_to_peer(peer_id, {
                "type": "cache_status",
                "key": key
            })
            if response and response.get("exists"):
                nodes_holding.append(peer_id)
        
        return CacheStatusResponse(
            key=key,
            exists=status_info["exists"],
            state=status_info["state"],
            last_access=status_info["last_access"],
            nodes_holding=nodes_holding
        )
    except Exception as e:
        logging.error(f"Status error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cache/metrics",
         response_model=CacheMetricsResponse,
         tags=["Metrics"])
async def get_cache_metrics():
    """
    Get cache performance metrics
    
    Returns hit rate, miss rate, cache size, and eviction count.
    """
    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache manager not initialized")
    
    metrics = cache_manager.get_metrics()
    return CacheMetricsResponse(**metrics)

@app.get("/cache/all",
         tags=["Cache"])
async def get_all_cache_keys():
    """Get all cached keys with their MESI states"""
    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache manager not initialized")
    
    cache_data = {}
    for key, line in cache_manager.cache.items():
        cache_data[key] = {
            "state": line.state.value,
            "last_access": line.last_access.isoformat(),
            "data": str(line.data)[:100]  # Truncate for display
        }
    
    return {
        "node_id": cache_manager.node_id,
        "cache_size": len(cache_manager.cache),
        "capacity": cache_manager.capacity,
        "keys": cache_data
    }

@app.post("/internal/message", tags=["Internal"])
async def handle_internal_message(message: dict):
    """Internal endpoint for inter-node communication"""
    if not cache_manager:
        raise HTTPException(status_code=503, detail="Cache manager not initialized")
    
    try:
        # Handle cache_status query
        if message.get("type") == "cache_status":
            key = message.get("key")
            status = cache_manager.get_key_status(key)
            return status
        
        # Handle other MESI protocol messages
        response = await cache_manager.process_message(message)
        return response
    except Exception as e:
        logging.error(f"Error processing internal message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv("API_PORT", "7000"))
    
    uvicorn.run(
        "src.api.cache_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
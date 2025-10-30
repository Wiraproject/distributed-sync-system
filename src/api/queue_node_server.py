from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager
from typing import Optional

from src.api.models import (
    QueueEnqueueRequest, QueueEnqueueResponse,
    QueueDequeueRequest, QueueDequeueResponse,
    QueueAckRequest, QueueAckResponse,
    QueueStatusResponse
)
from src.nodes.queue_node import DistributedQueue

queue_manager: Optional[DistributedQueue] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global queue_manager
    
    import os
    node_id = os.getenv("NODE_ID", "node_0")
    host = os.getenv("NODE_HOST", "0.0.0.0")
    port = int(os.getenv("NODE_PORT", "8000"))
    
    logging.info(f"Starting Distributed Queue Node: {node_id}")
    
    queue_manager = DistributedQueue(node_id, host, port)
    
    peer_nodes = os.getenv("PEER_NODES", "")
    if peer_nodes:
        for peer in peer_nodes.split(","):
            parts = peer.split(":")
            if len(parts) == 3:
                peer_id = parts[0]
                peer_host = parts[1]
                peer_port = int(parts[2])
                queue_manager.add_peer(peer_id, peer_host, peer_port)
                logging.info(f"Added peer: {peer_id} at {peer_host}:{peer_port}")
    
    await queue_manager.start()
    queue_manager.initialize_consistent_hash()
    await queue_manager.recover_from_log()
    
    logging.info("Queue Manager started successfully")
    yield
    
    logging.info("Shutting down Queue Manager")
    await queue_manager.stop()

app = FastAPI(
    title="Distributed Queue System API",
    description="REST API for distributed queue with consistent hashing",
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

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "node_id": queue_manager.node_id if queue_manager else "unknown",
        "is_running": queue_manager.running if queue_manager else False,
        "type": "queue"
    }

# ========== Queue Endpoints ==========
@app.post("/queue/enqueue", 
          response_model=QueueEnqueueResponse,
          tags=["Queue"])
async def enqueue_message(request: QueueEnqueueRequest):
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not initialized")
    
    try:
        message_id = await queue_manager.enqueue(request.queue_name, request.message)
        
        target_node = queue_manager.consistent_hash.get_node(request.queue_name)
        
        return QueueEnqueueResponse(
            success=True,
            message_id=message_id,
            queue_name=request.queue_name,
            node_id=target_node
        )
    except Exception as e:
        logging.error(f"Enqueue error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/queue/dequeue",
          response_model=QueueDequeueResponse,
          tags=["Queue"])
async def dequeue_message(request: QueueDequeueRequest):
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not initialized")
    
    try:
        message_data = await queue_manager.dequeue(request.queue_name)
        
        if message_data:
            return QueueDequeueResponse(
                success=True,
                message=message_data.get("data"),
                message_id=message_data.get("id"),
                delivery_time=message_data.get("delivery_time")
            )
        else:
            return QueueDequeueResponse(
                success=False,
                message=None,
                message_id=None
            )
    except Exception as e:
        logging.error(f"Dequeue error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/queue/ack",
          response_model=QueueAckResponse,
          tags=["Queue"])
async def acknowledge_message(request: QueueAckRequest):
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not initialized")
    
    try:
        success = await queue_manager.ack_message(request.message_id)
        
        if success:
            return QueueAckResponse(
                success=True,
                message=f"Message {request.message_id} acknowledged"
            )
        else:
            return QueueAckResponse(
                success=False,
                message=f"Message {request.message_id} not found or already processed"
            )
    except Exception as e:
        logging.error(f"ACK error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/queue/status/{queue_name}",
         response_model=QueueStatusResponse,
         tags=["Queue"])
async def get_queue_status(queue_name: str):
    """Get status of a specific queue"""
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not initialized")
    
    target_node = queue_manager.consistent_hash.get_node(queue_name)
    
    if target_node == queue_manager.node_id:
        size = len(queue_manager.queues.get(queue_name, []))
        in_flight = len([msg for msg in queue_manager.in_flight.values() 
                        if msg.get("queue") == queue_name])
        
        return QueueStatusResponse(
            queue_name=queue_name,
            size=size,
            in_flight=in_flight,
            node_id=queue_manager.node_id
        )
    else:
        response = await queue_manager.send_to_peer(target_node, {
            "type": "queue_status",
            "queue": queue_name
        })
        
        if response:
            return QueueStatusResponse(**response)
        else:
            raise HTTPException(status_code=503, detail=f"Cannot reach node {target_node}")

@app.get("/queue/all",
         tags=["Queue"])
async def get_all_queues():
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not initialized")
    
    queues_info = {}
    for queue_name, messages in queue_manager.queues.items():
        in_flight_count = len([msg for msg in queue_manager.in_flight.values() 
                              if msg.get("queue") == queue_name])
        queues_info[queue_name] = {
            "size": len(messages),
            "in_flight": in_flight_count
        }
    
    return {
        "node_id": queue_manager.node_id,
        "queues": queues_info,
        "total_queues": len(queues_info),
        "total_messages": sum(q["size"] for q in queues_info.values()),
        "total_in_flight": sum(q["in_flight"] for q in queues_info.values())
    }

@app.post("/internal/message", tags=["Internal"])
async def handle_internal_message(message: dict):
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not initialized")
    
    try:
        response = await queue_manager.process_message(message)
        return response
    except Exception as e:
        logging.error(f"Error processing internal message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    import os
    
    port = int(os.getenv("API_PORT", "8080"))
    
    uvicorn.run(
        "src.api.queue_node_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )
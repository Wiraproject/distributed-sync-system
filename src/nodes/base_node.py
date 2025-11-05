import asyncio
import logging
from typing import Dict, Optional
import httpx

class BaseNode:
    def __init__(self, node_id: str, host: str, port: int):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.peers: Dict[str, tuple] = {}
        self.running = False
        self.logger = logging.getLogger(f"Node-{node_id}")
        
        self.http_client: Optional[httpx.AsyncClient] = None
        
    async def start(self):
        self.running = True
        
        self.http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(5.0, connect=2.0),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0
            ),
            http2=False 
        )
        
        self.logger.info(f"Node {self.node_id} logic has started with connection pooling.")
        
    async def stop(self):
        self.running = False
        
        if self.http_client:
            await self.http_client.aclose()
            self.logger.info(f"HTTP client closed for {self.node_id}")
        
        self.logger.info(f"Node {self.node_id} has stopped.")
        
    async def process_message(self, message: Dict) -> Dict:
        self.logger.debug(f"BaseNode process_message called with: {message}")
        return {"status": "ok", "message": "processed by base node"}
        
    async def send_to_peer(self, peer_id: str, message: Dict) -> Optional[Dict]:
        if peer_id not in self.peers:
            self.logger.error(f"Peer '{peer_id}' not found in the peer list.")
            return None
            
        host, port = self.peers[peer_id]
        url = f"http://{host}:{port}/internal/message"
        
        try:
            if not self.http_client:
                self.logger.error("HTTP client not initialized")
                return None
            
            response = await self.http_client.post(url, json=message)
            response.raise_for_status()
            return response.json()
            
        except httpx.TimeoutException:
            self.logger.warning(f"Timeout sending message to peer {peer_id} at {url}")
            return None
        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error {e.response.status_code} from peer {peer_id}")
            return None
        except httpx.RequestError as e:
            self.logger.error(f"Failed to send message to peer {peer_id} at {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error sending to {peer_id}: {e}")
            return None
            
    def add_peer(self, peer_id: str, host: str, port: int):
        self.peers[peer_id] = (host, port)
        self.logger.info(f"Added peer {peer_id} at {host}:{port}")
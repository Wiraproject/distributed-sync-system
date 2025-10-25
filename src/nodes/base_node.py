import asyncio
import json
import logging
from typing import Dict, Optional

class BaseNode:
    """Base class untuk semua distributed nodes"""
    def __init__(self, node_id: str, host: str, port: int):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.peers: Dict[str, tuple] = {} 
        self.running = False
        self.server = None
        self.logger = logging.getLogger(f"Node-{node_id}")
        
    async def start(self):
        """Start node server"""
        self.running = True
        self.server = await asyncio.start_server(
            self.handle_connection, self.host, self.port
        )
        self.logger.info(f"Node {self.node_id} started on {self.host}:{self.port}")
        
    async def stop(self):
        """Stop node server"""
        self.running = False
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        self.logger.info(f"Node {self.node_id} stopped")
        
    async def handle_connection(self, reader, writer):
        """Handle incoming connections"""
        try:
            data = await reader.read(4096)
            message = json.loads(data.decode())
            response = await self.process_message(message)
            
            writer.write(json.dumps(response).encode())
            await writer.drain()
        except Exception as e:
            self.logger.error(f"Error handling connection: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            
    async def process_message(self, message: Dict) -> Dict:
        """Process incoming message - to be overridden"""
        return {"status": "ok"}
        
    async def send_to_peer(self, peer_id: str, message: Dict) -> Optional[Dict]:
        """Send message to peer node"""
        if peer_id not in self.peers:
            return None
            
        host, port = self.peers[peer_id]
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.write(json.dumps(message).encode())
            await writer.drain()
            
            data = await reader.read(4096)
            response = json.loads(data.decode())
            
            writer.close()
            await writer.wait_closed()
            return response
        except Exception as e:
            self.logger.error(f"Error sending to peer {peer_id}: {e}")
            return None
            
    def add_peer(self, peer_id: str, host: str, port: int):
        """Add peer node"""
        self.peers[peer_id] = (host, port)
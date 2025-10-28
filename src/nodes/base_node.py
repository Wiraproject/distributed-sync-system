import asyncio
import logging
from typing import Dict, Optional
import httpx

class BaseNode:
    """Base class untuk semua distributed nodes"""
    def __init__(self, node_id: str, host: str, port: int):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.peers: Dict[str, tuple] = {}
        self.running = False
        self.logger = logging.getLogger(f"Node-{node_id}")

    async def start(self):
        """Start node's background tasks (if any). This no longer starts a separate server."""
        self.running = True
        self.logger.info(f"Node {self.node_id} logic has started.")

    async def stop(self):
        """Stop node's background tasks."""
        self.running = False
        self.logger.info(f"Node {self.node_id} has stopped.")

    async def process_message(self, message: Dict) -> Dict:
        """
        Process an incoming message received via the internal API endpoint.
        This method is designed to be overridden by child classes (e.g., RaftNode).
        """
        self.logger.debug(f"BaseNode process_message called with: {message}")
        return {"status": "ok", "message": "processed by base node"}

    async def send_to_peer(self, peer_id: str, message: Dict) -> Optional[Dict]:
        """Send a message to a peer node using its internal HTTP API endpoint."""
        if peer_id not in self.peers:
            self.logger.error(f"Peer '{peer_id}' not found in the peer list.")
            return None

        host, port = self.peers[peer_id]
        url = f"http://{host}:{port}/internal/message"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(url, json=message)
                response.raise_for_status()
                return response.json()
        except httpx.RequestError as e:
            self.logger.error(f"Failed to send message to peer {peer_id} at {url}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"An unexpected error occurred when sending to {peer_id}: {e}")
            return None

    def add_peer(self, peer_id: str, host: str, port: int):
        """Adds a peer node to the list of known peers."""
        self.peers[peer_id] = (host, port)
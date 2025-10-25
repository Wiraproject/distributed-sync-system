import hashlib
from collections import defaultdict, deque
from typing import List, Dict, Any, Optional
from datetime import datetime
from src.nodes.base_node import BaseNode

class ConsistentHash:
    """Consistent Hashing implementation"""
    def __init__(self, nodes: List[str], virtual_nodes: int = 150):
        self.virtual_nodes = virtual_nodes
        self.ring = {}
        self.sorted_keys = []
        
        for node in nodes:
            self.add_node(node)
            
    def _hash(self, key: str) -> int:
        return int(hashlib.md5(key.encode()).hexdigest(), 16)
        
    def add_node(self, node: str):
        for i in range(self.virtual_nodes):
            virtual_key = f"{node}:{i}"
            hash_key = self._hash(virtual_key)
            self.ring[hash_key] = node
            
        self.sorted_keys = sorted(self.ring.keys())
        
    def remove_node(self, node: str):
        for i in range(self.virtual_nodes):
            virtual_key = f"{node}:{i}"
            hash_key = self._hash(virtual_key)
            if hash_key in self.ring:
                del self.ring[hash_key]
                
        self.sorted_keys = sorted(self.ring.keys())
        
    def get_node(self, key: str) -> str:
        if not self.ring:
            return None
            
        hash_key = self._hash(key)
        
        for ring_key in self.sorted_keys:
            if hash_key <= ring_key:
                return self.ring[ring_key]
                
        return self.ring[self.sorted_keys[0]]

class DistributedQueue(BaseNode):
    """Distributed Queue with Consistent Hashing"""
    
    def __init__(self, node_id: str, host: str, port: int):
        super().__init__(node_id, host, port)
        self.queues: Dict[str, deque] = defaultdict(deque)
        self.persistent_log: List[Dict] = []
        self.consistent_hash = None
        self.message_id_counter = 0
        
    def initialize_consistent_hash(self):
        """Initialize consistent hashing with all nodes"""
        nodes = [self.node_id] + list(self.peers.keys())
        self.consistent_hash = ConsistentHash(nodes)
        
    async def enqueue(self, queue_name: str, message: Any) -> str:
        """Add message to queue"""
        msg_id = f"{self.node_id}-{self.message_id_counter}"
        self.message_id_counter += 1
        
        target_node = self.consistent_hash.get_node(queue_name)
        
        message_data = {
            "id": msg_id,
            "queue": queue_name,
            "data": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if target_node == self.node_id:
            self.queues[queue_name].append(message_data)
            self.persistent_log.append(message_data)
        else:
            await self.send_to_peer(target_node, {
                "type": "enqueue",
                "data": message_data
            })
            
        self.logger.info(f"Message {msg_id} enqueued to {queue_name}")
        return msg_id
        
    async def dequeue(self, queue_name: str) -> Optional[Dict]:
        """Remove and return message from queue"""
        target_node = self.consistent_hash.get_node(queue_name)
        
        if target_node == self.node_id:
            if queue_name in self.queues and self.queues[queue_name]:
                message = self.queues[queue_name].popleft()
                self.logger.info(f"Message {message['id']} dequeued from {queue_name}")
                return message
            return None
        else:
            response = await self.send_to_peer(target_node, {
                "type": "dequeue",
                "queue": queue_name
            })
            return response.get("message") if response else None
            
    async def process_message(self, message: Dict) -> Dict:
        """Process queue operations"""
        msg_type = message.get("type")
        
        if msg_type == "enqueue":
            data = message["data"]
            self.queues[data["queue"]].append(data)
            self.persistent_log.append(data)
            return {"status": "ok", "id": data["id"]}
            
        elif msg_type == "dequeue":
            queue_name = message["queue"]
            msg = await self.dequeue(queue_name)
            return {"status": "ok", "message": msg}
            
        return {"status": "unknown_operation"}
        
    async def recover_from_log(self):
        """Recover queue state from persistent log"""
        self.logger.info("Recovering from persistent log...")
        for entry in self.persistent_log:
            queue_name = entry["queue"]
            self.queues[queue_name].append(entry)
        self.logger.info(f"Recovered {len(self.persistent_log)} messages")
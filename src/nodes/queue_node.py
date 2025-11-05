import hashlib
from collections import defaultdict, deque
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import os
import asyncio
import aiofiles
from src.nodes.base_node import BaseNode

class ConsistentHash:
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
        
    def get_node(self, key: str) -> Optional[str]:
        if not self.ring:
            return None
            
        hash_key = self._hash(key)
        
        for ring_key in self.sorted_keys:
            if hash_key <= ring_key:
                return self.ring[ring_key]
                
        return self.ring[self.sorted_keys[0]]

class DistributedQueue(BaseNode):
    def __init__(self, node_id: str, host: str, port: int, immediate_mode: bool = False):
        super().__init__(node_id, host, port)
        self.queues: Dict[str, deque] = defaultdict(deque)
        
        self.log_path = f"logs/{self.node_id}_queue.log"
        os.makedirs("logs", exist_ok=True)
        
        self.consistent_hash = None
        self.message_id_counter = 0
        
        self.in_flight: Dict[str, Dict] = {}
        self.visibility_timeout = timedelta(seconds=30)
        
        self.immediate_mode = immediate_mode
        
        self.wal_buffer = []
        self.wal_buffer_size = 0
        self.wal_max_buffer = 1024 * 1024
        self.wal_flush_interval = 0.1 
        self.wal_lock = asyncio.Lock()
        
        self.enqueue_batch = []
        self.batch_size = 50
        self.batch_timeout = 0.01  
        
    def initialize_consistent_hash(self):
        nodes = [self.node_id] + list(self.peers.keys())
        self.consistent_hash = ConsistentHash(nodes)
        self.logger.info(f"Consistent hash ring initialized with nodes: {nodes}")
    
    async def start(self):
        await super().start()
        
        if not self.immediate_mode:
            asyncio.create_task(self._flush_wal_periodically())
            asyncio.create_task(self._process_enqueue_batches())
            asyncio.create_task(self._check_in_flight_timeouts())
    
    async def _append_to_log(self, data: Dict):
        async with self.wal_lock:
            entry = json.dumps(data) + '\n'
            self.wal_buffer.append(entry)
            self.wal_buffer_size += len(entry)
            
            if self.immediate_mode or self.wal_buffer_size >= self.wal_max_buffer:
                await self._flush_wal()
    
    async def _flush_wal(self):
        if not self.wal_buffer:
            return
        
        try:
            async with aiofiles.open(self.log_path, mode='a') as f:
                await f.writelines(self.wal_buffer)
            
            self.wal_buffer.clear()
            self.wal_buffer_size = 0
        except Exception as e:
            self.logger.error(f"Failed to flush WAL: {e}")
    
    async def _flush_wal_periodically(self):
        while self.running:
            await asyncio.sleep(self.wal_flush_interval)
            async with self.wal_lock:
                await self._flush_wal()
    
    async def _process_enqueue_batches(self):
        while self.running:
            await asyncio.sleep(self.batch_timeout)
            
            if not self.enqueue_batch:
                continue
            
            batch = self.enqueue_batch[:self.batch_size]
            self.enqueue_batch = self.enqueue_batch[self.batch_size:]
            
            for message_data in batch:
                queue_name = message_data["queue"]
                self.queues[queue_name].append(message_data)
                await self._append_to_log({"type": "ENQUEUE", "payload": message_data})
    
    async def enqueue(self, queue_name: str, message: Any) -> str:
        self.message_id_counter += 1
        msg_id = f"{self.node_id}-{self.message_id_counter}"
        
        if not self.consistent_hash:
            raise RuntimeError("Consistent hash not initialized.")
            
        target_node = self.consistent_hash.get_node(queue_name)
        
        message_data = {
            "id": msg_id,
            "queue": queue_name,
            "data": message,
            "timestamp": datetime.now().isoformat()
        }
        
        if target_node == self.node_id:
            if self.immediate_mode:
                await self._local_enqueue(message_data)
            else:
                self.enqueue_batch.append(message_data)
                
                if len(self.enqueue_batch) >= self.batch_size:
                    asyncio.create_task(self._process_enqueue_batches())
        else:
            asyncio.create_task(self.send_to_peer(target_node, {
                "type": "enqueue",
                "data": message_data
            }))
            
        self.logger.info(f"Message {msg_id} routed to node {target_node} for queue {queue_name}")
        return msg_id
    
    async def _local_enqueue(self, message_data: Dict):
        queue_name = message_data["queue"]
        self.queues[queue_name].append(message_data)
        await self._append_to_log({"type": "ENQUEUE", "payload": message_data})
    
    async def dequeue(self, queue_name: str) -> Optional[Dict]:
        if not self.consistent_hash:
            raise RuntimeError("Consistent hash not initialized.")
            
        target_node = self.consistent_hash.get_node(queue_name)
        
        if target_node == self.node_id:
            return self._local_dequeue(queue_name)
        else:
            response = await self.send_to_peer(target_node, {
                "type": "dequeue",
                "queue": queue_name
            })
            return response.get("message") if response else None
    
    def _local_dequeue(self, queue_name: str) -> Optional[Dict]:
        if queue_name in self.queues and self.queues[queue_name]:
            message = self.queues[queue_name].popleft()
            msg_id = message['id']
            
            message['delivery_time'] = datetime.now().isoformat()
            message['visibility_timeout'] = (datetime.now() + self.visibility_timeout).isoformat()
            self.in_flight[msg_id] = message
            
            self.logger.info(f"Message {msg_id} delivered from {queue_name}, awaiting acknowledgement.")
            return message
        return None
    
    async def ack_message(self, msg_id: str) -> bool:
        if msg_id in self.in_flight:
            del self.in_flight[msg_id]
            await self._append_to_log({"type": "ACK", "msg_id": msg_id})
            self.logger.info(f"Message {msg_id} acknowledged and permanently removed.")
            return True
        self.logger.warning(f"ACK received for unknown or timed-out message ID: {msg_id}")
        return False
    
    async def _check_in_flight_timeouts(self):
        while self.running:
            await asyncio.sleep(5)
            
            current_time = datetime.now()
            expired = []
            
            for msg_id, message in list(self.in_flight.items()):
                timeout_str = message.get('visibility_timeout')
                if timeout_str:
                    timeout = datetime.fromisoformat(timeout_str)
                    if current_time > timeout:
                        expired.append((msg_id, message))
            
            for msg_id, message in expired:
                del self.in_flight[msg_id]
                queue_name = message['queue']
                
                message.pop('delivery_time', None)
                message.pop('visibility_timeout', None)
                self.queues[queue_name].append(message)
                
                self.logger.warning(f"Message {msg_id} timed out, requeued to {queue_name}")
        
    async def process_message(self, message: Dict) -> Dict:
        msg_type = message.get("type")
        
        if msg_type == "enqueue":
            data = message["data"]
            await self._local_enqueue(data)
            return {"status": "ok", "id": data["id"]}
            
        elif msg_type == "dequeue":
            queue_name = message["queue"]
            msg = self._local_dequeue(queue_name)
            return {"status": "ok", "message": msg}
        
        elif msg_type == "queue_status": 
            queue_name = message["queue"]
            size = len(self.queues.get(queue_name, []))
            in_flight = len([m for m in self.in_flight.values() if m.get("queue") == queue_name])
            return {
                "queue_name": queue_name,
                "size": size,
                "in_flight": in_flight,
                "node_id": self.node_id
            }
            
        return {"status": "unknown_operation"}
        
    async def recover_from_log(self):
        self.logger.info(f"Recovering queue state from {self.log_path}...")
        temp_queues = defaultdict(dict)
        acked_ids = set()
        
        try:
            async with aiofiles.open(self.log_path, mode='r') as f:
                async for line in f:
                    if not line.strip(): 
                        continue
                    log_entry = json.loads(line)
                    
                    if log_entry['type'] == 'ENQUEUE':
                        msg = log_entry['payload']
                        temp_queues[msg['queue']][msg['id']] = msg
                    elif log_entry['type'] == 'ACK':
                        acked_ids.add(log_entry['msg_id'])
            
            recovered_count = 0
            for queue_name, messages in temp_queues.items():
                for msg_id, msg_data in messages.items():
                    if msg_id not in acked_ids:
                        self.queues[queue_name].append(msg_data)
                        recovered_count += 1
            
            self.logger.info(f"Recovery complete. Recovered {recovered_count} active messages.")
        except FileNotFoundError:
            self.logger.warning(f"Log file not found at {self.log_path}, starting with a fresh state.")
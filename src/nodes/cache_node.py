import asyncio
from enum import Enum
from collections import OrderedDict
from typing import Dict, Any, Optional
from datetime import datetime
from src.nodes.base_node import BaseNode

class CacheState(Enum):
    MODIFIED = "M"
    EXCLUSIVE = "E"
    SHARED = "S"
    INVALID = "I"

class CacheLine:
    def __init__(self, data: Any, state: CacheState = CacheState.INVALID):
        self.data = data
        self.state = state
        self.last_access = datetime.now()

class MESICache(BaseNode):
    """MESI Cache Coherence Protocol Implementation"""
    def __init__(self, node_id: str, host: str, port: int, capacity: int = 100):
        super().__init__(node_id, host, port)
        self.cache: OrderedDict[str, CacheLine] = OrderedDict()
        self.capacity = capacity
        self.hits = 0
        self.misses = 0
        self.evictions = 0 
        
    async def read(self, key: str) -> Optional[Any]:
        """Read from cache with MESI protocol"""
        if key in self.cache:
            line = self.cache[key]
            
            if line.state != CacheState.INVALID:
                self.hits += 1
                line.last_access = datetime.now()
                self.cache.move_to_end(key)
                
                if line.state == CacheState.MODIFIED:
                    await self.broadcast_read_request(key)
                    line.state = CacheState.SHARED
                    
                return line.data
                
        self.misses += 1
        data = await self.fetch_from_memory(key)
        
        if data is not None:
            await self.cache_data(key, data, CacheState.SHARED)
            
        return data
        
    async def write(self, key: str, value: Any) -> bool:
        """Write to cache with MESI protocol"""
        await self.broadcast_invalidate(key)
        
        if key in self.cache:
            line = self.cache[key]
            line.data = value
            line.state = CacheState.MODIFIED
            line.last_access = datetime.now()
            self.cache.move_to_end(key)
        else:
            await self.cache_data(key, value, CacheState.MODIFIED)
            
        return True
        
    async def cache_data(self, key: str, data: Any, state: CacheState):
        """Add data to cache with LRU eviction"""
        if len(self.cache) >= self.capacity:
            evicted_key, evicted_line = self.cache.popitem(last=False)
            
            if evicted_line.state == CacheState.MODIFIED:
                await self.write_back_to_memory(evicted_key, evicted_line.data)
                
            self.evictions += 1 
            self.logger.info(f"Evicted {evicted_key} from cache (total: {self.evictions})")
            
        self.cache[key] = CacheLine(data, state)
        
    async def broadcast_read_request(self, key: str):
        """Notify other caches of read"""
        message = {
            "type": "cache_read",
            "key": key,
            "node_id": self.node_id
        }
        
        tasks = [self.send_to_peer(peer_id, message) for peer_id in self.peers]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def broadcast_invalidate(self, key: str):
        """Invalidate key in all other caches"""
        message = {
            "type": "cache_invalidate",
            "key": key,
            "node_id": self.node_id
        }
        
        tasks = [self.send_to_peer(peer_id, message) for peer_id in self.peers]
        await asyncio.gather(*tasks, return_exceptions=True)
        
    async def process_message(self, message: Dict) -> Dict:
        """Process cache coherence messages"""
        msg_type = message.get("type")
        
        if msg_type == "cache_read":
            key = message["key"]
            if key in self.cache and self.cache[key].state == CacheState.MODIFIED:
                self.cache[key].state = CacheState.SHARED
                return {"status": "ok", "data": self.cache[key].data}
                
        elif msg_type == "cache_invalidate":
            key = message["key"]
            if key in self.cache:
                self.cache[key].state = CacheState.INVALID
                
        return {"status": "ok"}
        
    async def fetch_from_memory(self, key: str) -> Optional[Any]:
        """Simulate fetching from main memory"""
        await asyncio.sleep(0.01)
        return f"data_for_{key}"
        
    async def write_back_to_memory(self, key: str, data: Any):
        """Simulate writing back to main memory"""
        await asyncio.sleep(0.01)
        self.logger.info(f"Wrote back {key} to memory")
        
    def get_metrics(self) -> Dict:
        """Get cache performance metrics"""
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "cache_size": len(self.cache),
            "capacity": self.capacity,
            "evictions": self.evictions
        }
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if key in self.cache:
            # Broadcast invalidation first
            await self.broadcast_invalidate(key)
            
            # Remove from local cache
            del self.cache[key]
            self.logger.info(f"Deleted {key} from cache")
            return True
        return False
    
    def get_key_status(self, key: str) -> Dict:
        """Get status of a specific key"""
        if key in self.cache:
            line = self.cache[key]
            return {
                "key": key,
                "exists": True,
                "state": line.state.value,
                "last_access": line.last_access.isoformat()
            }
        return {
            "key": key,
            "exists": False,
            "state": None,
            "last_access": None
        }
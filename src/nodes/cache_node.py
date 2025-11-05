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
        self.created_at = datetime.now()

class MESICache(BaseNode):
    def __init__(self, node_id: str, host: str, port: int, capacity: int = 100):
        super().__init__(node_id, host, port)
        self.cache: OrderedDict[str, CacheLine] = OrderedDict()
        self.capacity = capacity
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        self.read_count = 0
        self.write_count = 0
        self.invalidation_count = 0
        
    async def read(self, key: str) -> Optional[Any]:
        self.read_count += 1
        
        if key in self.cache:
            line = self.cache[key]
            
            if line.state != CacheState.INVALID:
                self.hits += 1
                line.last_access = datetime.now()
                self.cache.move_to_end(key)
                
                self.logger.debug(f"Cache HIT: {key} (state: {line.state.value})")
                return line.data
        
        self.misses += 1
        self.logger.debug(f"Cache MISS: {key}")
        
        peer_data, peer_id = await self.fetch_from_peers(key)
        
        if peer_data is not None:
            await self.cache_data(key, peer_data, CacheState.SHARED)
            self.logger.info(f"Fetched {key} from peer {peer_id}, cached as SHARED")
            return peer_data
        
        data = await self.fetch_from_memory(key)
        
        if data is not None:
            await self.cache_data(key, data, CacheState.EXCLUSIVE)
            self.logger.info(f"Fetched {key} from memory, cached as EXCLUSIVE")
            
        return data
        
    async def write(self, key: str, value: Any) -> bool:
        self.write_count += 1
        
        await self.broadcast_invalidate(key)
        
        # Update local cache
        if key in self.cache:
            line = self.cache[key]
            old_state = line.state.value
            line.data = value
            line.state = CacheState.MODIFIED
            line.last_access = datetime.now()
            self.cache.move_to_end(key)
            self.logger.info(f"Updated {key}: {old_state} → M (local write)")
        else:
            await self.cache_data(key, value, CacheState.MODIFIED)
            self.logger.info(f"Cached new key {key} as MODIFIED")
            
        return True
        
    async def cache_data(self, key: str, data: Any, state: CacheState):
        if len(self.cache) >= self.capacity:
            evicted_key, evicted_line = self.cache.popitem(last=False)
            
            if evicted_line.state == CacheState.MODIFIED:
                await self.write_back_to_memory(evicted_key, evicted_line.data)
                
            self.evictions += 1
            self.logger.info(f"Evicted {evicted_key} (state: {evicted_line.state.value})")
            
        self.cache[key] = CacheLine(data, state)
        self.logger.debug(f"Cached {key} with state {state.value}")
        
    async def fetch_from_peers(self, key: str) -> tuple[Optional[Any], Optional[str]]:
        message = {
            "type": "cache_read_request",
            "key": key,
            "node_id": self.node_id
        }
        
        tasks = []
        peer_ids = list(self.peers.keys())
        
        for peer_id in peer_ids:
            tasks.append(self.send_to_peer(peer_id, message))
        
        if not tasks:
            return None, None
        
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            for peer_id, response in zip(peer_ids, responses):
                if isinstance(response, dict) and response.get("has_data"):
                    data = response.get("data")
                    peer_state = response.get("state")
                    
                    self.logger.info(f"Peer {peer_id} provided {key} (state: {peer_state})")
                    return data, peer_id
                    
        except Exception as e:
            self.logger.error(f"Error fetching from peers: {e}")
        
        return None, None
        
    async def broadcast_invalidate(self, key: str):
        self.invalidation_count += 1
        
        message = {
            "type": "cache_invalidate",
            "key": key,
            "node_id": self.node_id
        }
        
        tasks = [self.send_to_peer(peer_id, message) for peer_id in self.peers]
        
        if tasks:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in responses if isinstance(r, dict) and r.get("status") == "ok")
            self.logger.debug(f"Broadcasted invalidate for {key} ({success_count}/{len(tasks)} peers acknowledged)")
        
    async def process_message(self, message: Dict) -> Dict:
        msg_type = message.get("type")
        
        if msg_type == "cache_read_request":
            key = message["key"]
            requester = message["node_id"]
            
            if key in self.cache:
                line = self.cache[key]
                
                if line.state == CacheState.MODIFIED:
                    await self.write_back_to_memory(key, line.data)
                    old_state = line.state.value
                    line.state = CacheState.SHARED
                    self.logger.info(f"Remote read for {key} from {requester}: {old_state} → S (wrote back)")
                    return {
                        "status": "ok",
                        "has_data": True,
                        "data": line.data,
                        "state": "S"
                    }
                
                elif line.state == CacheState.EXCLUSIVE:
                    old_state = line.state.value
                    line.state = CacheState.SHARED
                    self.logger.info(f"Remote read for {key} from {requester}: {old_state} → S")
                    return {
                        "status": "ok",
                        "has_data": True,
                        "data": line.data,
                        "state": "S"
                    }
                
                elif line.state == CacheState.SHARED:
                    self.logger.debug(f"Remote read for {key} from {requester}: S → S")
                    return {
                        "status": "ok",
                        "has_data": True,
                        "data": line.data,
                        "state": "S"
                    }
                
                elif line.state == CacheState.INVALID:
                    return {"status": "ok", "has_data": False}
            
            return {"status": "ok", "has_data": False}
                
        elif msg_type == "cache_invalidate":
            key = message["key"]
            writer = message["node_id"]
            
            if key in self.cache:
                old_state = self.cache[key].state.value
                self.cache[key].state = CacheState.INVALID
                self.logger.info(f"Invalidated {key} due to write from {writer}: {old_state} → I")
            
            return {"status": "ok"}
        
        elif msg_type == "cache_status":
            key = message.get("key")
            if key in self.cache:
                line = self.cache[key]
                return {
                    "status": "ok",
                    "exists": True,
                    "state": line.state.value,
                    "last_access": line.last_access.isoformat()
                }
            return {"status": "ok", "exists": False, "state": None}
            
        return {"status": "ok"}
        
    async def fetch_from_memory(self, key: str) -> Optional[Any]:
        await asyncio.sleep(0.01)
        return f"data_for_{key}"
        
    async def write_back_to_memory(self, key: str, data: Any):
        await asyncio.sleep(0.01)
        self.logger.info(f"Wrote back {key} to memory: {data}")
        
    async def delete(self, key: str) -> bool:
        if key in self.cache:
            await self.broadcast_invalidate(key)
            
            line = self.cache[key]
            if line.state == CacheState.MODIFIED:
                await self.write_back_to_memory(key, line.data)
            
            del self.cache[key]
            self.logger.info(f"Deleted {key} from cache")
            return True
        return False
    
    def get_key_status(self, key: str) -> Dict:
        if key in self.cache:
            line = self.cache[key]
            return {
                "key": key,
                "exists": True,
                "state": line.state.value,
                "last_access": line.last_access.isoformat(),
                "created_at": line.created_at.isoformat(),
                "data_preview": str(line.data)[:100]
            }
        return {
            "key": key,
            "exists": False,
            "state": None,
            "last_access": None,
            "created_at": None
        }
        
    def get_metrics(self) -> Dict:
        total_requests = self.hits + self.misses
        hit_rate = self.hits / total_requests if total_requests > 0 else 0
        
        state_count = {
            "M": 0,
            "E": 0,
            "S": 0,
            "I": 0
        }
        for line in self.cache.values():
            state_count[line.state.value] += 1
        
        return {
            "node_id": self.node_id,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 4),
            "cache_size": len(self.cache),
            "capacity": self.capacity,
            "evictions": self.evictions,
            "state_distribution": state_count,
            "read_count": self.read_count,
            "write_count": self.write_count,
            "invalidation_count": self.invalidation_count
        }
    
    async def clear_cache(self):
        for key, line in list(self.cache.items()):
            if line.state == CacheState.MODIFIED:
                await self.write_back_to_memory(key, line.data)
        
        self.cache.clear()
        self.logger.info("Cache cleared")
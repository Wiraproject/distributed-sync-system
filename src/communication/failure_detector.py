import logging
import asyncio
import time
from typing import Dict, Set, Callable

class FailureDetector:
    """Phi Accrual Failure Detector"""
    def __init__(self, node_id: str, threshold: float = 8.0):
        self.node_id = node_id
        self.threshold = threshold
        self.heartbeat_history: Dict[str, list] = {}
        self.last_heartbeat: Dict[str, float] = {}
        self.suspected_nodes: Set[str] = set()
        self.callbacks: list = []
        self.window_size = 100
        self.logger = logging.getLogger(f"FailureDetector-{node_id}")
        
    def record_heartbeat(self, peer_id: str):
        """Record heartbeat from peer"""
        current_time = time.time()
        
        if peer_id not in self.heartbeat_history:
            self.heartbeat_history[peer_id] = []
        
        if peer_id in self.last_heartbeat:
            interval = current_time - self.last_heartbeat[peer_id]
            self.heartbeat_history[peer_id].append(interval)
            
            if len(self.heartbeat_history[peer_id]) > self.window_size:
                self.heartbeat_history[peer_id].pop(0)
        
        self.last_heartbeat[peer_id] = current_time
        
        if peer_id in self.suspected_nodes:
            self.suspected_nodes.remove(peer_id)
            self.logger.info(f"Node {peer_id} recovered")
            self._trigger_callbacks("recovery", peer_id)
    
    def calculate_phi(self, peer_id: str) -> float:
        """Calculate phi value for peer"""
        if peer_id not in self.last_heartbeat:
            return float('inf')
        
        if peer_id not in self.heartbeat_history or len(self.heartbeat_history[peer_id]) < 2:
            return 0.0
        
        intervals = self.heartbeat_history[peer_id]
        mean_interval = sum(intervals) / len(intervals)
        variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
        std_dev = variance ** 0.5
        
        if std_dev == 0:
            return 0.0
        
        time_since_last = time.time() - self.last_heartbeat[peer_id]
        
        import math
        phi = -math.log10(1 - self._cdf(time_since_last, mean_interval, std_dev))
        
        return phi
    
    def _cdf(self, x: float, mean: float, std_dev: float) -> float:
        """Cumulative distribution function for normal distribution"""
        import math
        z = (x - mean) / std_dev
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))
    
    def is_suspected(self, peer_id: str) -> bool:
        """Check if peer is suspected to have failed"""
        phi = self.calculate_phi(peer_id)
        
        if phi > self.threshold and peer_id not in self.suspected_nodes:
            self.suspected_nodes.add(peer_id)
            self.logger.warning(f"Node {peer_id} suspected (phi={phi:.2f})")
            self._trigger_callbacks("suspicion", peer_id)
            return True
        
        return peer_id in self.suspected_nodes
    
    def get_live_nodes(self, all_peers: list) -> list:
        """Get list of live (non-suspected) nodes"""
        return [peer for peer in all_peers if not self.is_suspected(peer)]
    
    def register_callback(self, callback: Callable):
        """Register callback for failure/recovery events"""
        self.callbacks.append(callback)
    
    def _trigger_callbacks(self, event_type: str, peer_id: str):
        """Trigger registered callbacks"""
        for callback in self.callbacks:
            try:
                callback(event_type, peer_id)
            except Exception as e:
                self.logger.error(f"Error in callback: {e}")
    
    async def monitor_loop(self, peers: list, check_interval: float = 1.0):
        """Continuous monitoring loop"""
        while True:
            for peer_id in peers:
                self.is_suspected(peer_id)
            
            await asyncio.sleep(check_interval)
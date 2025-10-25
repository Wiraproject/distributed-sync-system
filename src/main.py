import asyncio
import logging
import os

from src.nodes.lock_manager import DistributedLockManager
from src.nodes.queue_node import DistributedQueue
from src.nodes.cache_node import MESICache
from src.utils.config import SystemConfig
from src.utils.metrics import PerformanceMonitor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class DistributedSystemController:
    """Main controller untuk distributed system"""
    
    def __init__(self, node_id: str, port: int):
        self.node_id = node_id
        self.port = port
        
        self.lock_manager = DistributedLockManager(
            f"{node_id}_lock", 
            "0.0.0.0", 
            port
        )
        self.queue_node = DistributedQueue(
            f"{node_id}_queue",
            "0.0.0.0",
            port + 100
        )
        self.cache_node = MESICache(
            f"{node_id}_cache",
            "0.0.0.0",
            port + 200,
            capacity=int(os.getenv("CACHE_SIZE", "100"))
        )
        
        self.monitor = PerformanceMonitor()
        self.logger = logging.getLogger(f"Controller-{node_id}")
        
    async def start(self):
        """Start all components"""
        self.logger.info(f"Starting distributed system node: {self.node_id}")
        
        await self.lock_manager.start()
        await self.queue_node.start()
        await self.cache_node.start()
        
        self.queue_node.initialize_consistent_hash()
        
        self.logger.info("All components started successfully")
        
    async def stop(self):
        """Stop all components"""
        self.logger.info("Stopping distributed system...")
        
        await self.lock_manager.stop()
        await self.queue_node.stop()
        await self.cache_node.stop()
        
        self.logger.info("Shutdown complete")
        
    async def connect_peers(self, peer_nodes: list):
        """Connect to peer nodes"""
        for peer in peer_nodes:
            node_id, host, port = peer.split(':')
            port = int(port)
            
            self.lock_manager.add_peer(f"{node_id}_lock", host, port)
            self.queue_node.add_peer(f"{node_id}_queue", host, int(port) + 100)
            self.cache_node.add_peer(f"{node_id}_cache", host, int(port) + 200)
            
        self.logger.info(f"Connected to {len(peer_nodes)} peers")
        
    async def run_health_check(self):
        """Periodic health check"""
        while True:
            try:
                if hasattr(self.lock_manager, 'state'):
                    self.logger.info(f"Raft State: {self.lock_manager.state.value}")
                    self.logger.info(f"Term: {self.lock_manager.current_term}")
                
                cache_metrics = self.cache_node.get_metrics()
                self.logger.info(f"Cache Hit Rate: {cache_metrics['hit_rate']*100:.2f}%")
                
                metrics_summary = self.monitor.metrics.get_summary()
                self.logger.info(f"System Uptime: {self.monitor.get_uptime():.2f}s")
                
            except Exception as e:
                self.logger.error(f"Health check error: {e}")
                
            await asyncio.sleep(30) 

async def main():
    """Main entry point"""
    node_id = os.getenv("NODE_ID", "node_0")
    port = int(os.getenv("NODE_PORT", "5000"))
    peer_nodes_str = os.getenv("PEER_NODES", "")
    
    peer_nodes = []
    if peer_nodes_str:
        peer_nodes = peer_nodes_str.split(',')
    
    controller = DistributedSystemController(node_id, port)
    
    try:
        await controller.start()
        
        if peer_nodes:
            await controller.connect_peers(peer_nodes)
        
        health_task = asyncio.create_task(controller.run_health_check())
        
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await controller.stop()

if __name__ == "__main__":
    asyncio.run(main())
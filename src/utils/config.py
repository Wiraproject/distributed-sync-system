import os
from dataclasses import dataclass
from typing import List

@dataclass
class NodeConfig:
    node_id: str
    host: str
    port: int

@dataclass
class SystemConfig:
    nodes: List[NodeConfig]
    redis_host: str
    redis_port: int
    log_level: str
    
    @classmethod
    def from_env(cls):
        num_nodes = int(os.getenv("NUM_NODES", "3"))
        base_port = int(os.getenv("BASE_PORT", "8000"))
        
        nodes = []
        for i in range(num_nodes):
            nodes.append(NodeConfig(
                node_id=f"node_{i}",
                host="localhost",
                port=base_port + i
            ))
            
        return cls(
            nodes=nodes,
            redis_host=os.getenv("REDIS_HOST", "localhost"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )
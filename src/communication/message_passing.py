import asyncio
import logging
from typing import Dict, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Message:
    msg_id: str
    msg_type: str
    sender_id: str
    receiver_id: str
    payload: Dict
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "payload": self.payload,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        return cls(**data)

class MessageBus:
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.handlers: Dict[str, Callable] = {}
        self.logger = logging.getLogger(f"MessageBus-{node_id}")
        self.message_counter = 0
        
    def register_handler(self, msg_type: str, handler: Callable):
        self.handlers[msg_type] = handler
        self.logger.info(f"Registered handler for {msg_type}")
        
    async def send_message(self, receiver_id: str, msg_type: str, payload: Dict) -> Optional[Dict]:
        self.message_counter += 1
        
        message = Message(
            msg_id=f"{self.node_id}-{self.message_counter}",
            msg_type=msg_type,
            sender_id=self.node_id,
            receiver_id=receiver_id,
            payload=payload,
            timestamp=datetime.now().isoformat()
        )
        
        self.logger.debug(f"Sending {msg_type} to {receiver_id}")
        
        await asyncio.sleep(0.001)
        
        return {"status": "sent", "msg_id": message.msg_id}
        
    async def handle_message(self, message_data: Dict) -> Dict:
        try:
            message = Message.from_dict(message_data)
            
            if message.msg_type in self.handlers:
                handler = self.handlers[message.msg_type]
                result = await handler(message)
                return {"status": "ok", "result": result}
            else:
                self.logger.warning(f"No handler for message type: {message.msg_type}")
                return {"status": "error", "message": "Unknown message type"}
                
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            return {"status": "error", "message": str(e)}
    
    async def broadcast(self, msg_type: str, payload: Dict, peer_ids: list):
        tasks = []
        for peer_id in peer_ids:
            tasks.append(self.send_message(peer_id, msg_type, payload))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if isinstance(r, dict) and r.get("status") == "sent")
        self.logger.info(f"Broadcast {msg_type} to {success_count}/{len(peer_ids)} peers")
        
        return success_count
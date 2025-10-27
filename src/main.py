import asyncio
import logging
import os
import sys

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def main():
    """Simplified main for testing"""
    logger = logging.getLogger("Main")
    
    node_id = os.getenv("NODE_ID", "node_0")
    port = int(os.getenv("NODE_PORT", "8000"))
    
    logger.info(f"=" * 60)
    logger.info(f"Starting Distributed Sync System")
    logger.info(f"Node ID: {node_id}")
    logger.info(f"Port: {port}")
    logger.info(f"=" * 60)
    
    # Simple placeholder - just keep running
    logger.info("Node initialized successfully!")
    logger.info("System is running... (Press Ctrl+C to stop)")
    
    try:
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == "__main__":
    asyncio.run(main())
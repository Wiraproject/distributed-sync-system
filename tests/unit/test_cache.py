import pytest
from src.nodes.cache_node import MESICache, CacheState

@pytest.mark.asyncio
async def test_cache_read_miss():
    """Test cache miss scenario"""
    cache = MESICache("cache_node", "localhost", 8000)
    
    data = await cache.read("key_1")
    
    assert data is not None
    assert cache.misses == 1
    assert "key_1" in cache.cache

@pytest.mark.asyncio
async def test_cache_read_hit():
    """Test cache hit scenario"""
    cache = MESICache("cache_node", "localhost", 8000)
    
    # First read (miss)
    await cache.read("key_1")
    
    # Second read (hit)
    data = await cache.read("key_1")
    
    assert cache.hits == 1
    assert cache.misses == 1

@pytest.mark.asyncio
async def test_cache_write():
    """Test cache write operation"""
    cache = MESICache("cache_node", "localhost", 8000)
    
    result = await cache.write("key_1", "value_1")
    
    assert result == True
    assert "key_1" in cache.cache
    assert cache.cache["key_1"].state == CacheState.MODIFIED

@pytest.mark.asyncio
async def test_cache_lru_eviction():
    """Test LRU cache eviction"""
    cache = MESICache("cache_node", "localhost", 8000, capacity=3)
    
    # Fill cache
    await cache.write("key_1", "value_1")
    await cache.write("key_2", "value_2")
    await cache.write("key_3", "value_3")
    
    await cache.write("key_4", "value_4")
    
    assert "key_1" not in cache.cache
    assert len(cache.cache) == 3

@pytest.mark.asyncio
async def test_cache_metrics():
    """Test cache metrics collection"""
    cache = MESICache("cache_node", "localhost", 8000)
    
    await cache.read("key_1")
    await cache.read("key_1")
    await cache.read("key_2")
    
    metrics = cache.get_metrics()
    
    assert metrics["hits"] == 1
    assert metrics["misses"] == 2
    assert 0 <= metrics["hit_rate"] <= 1

@pytest.mark.asyncio
async def test_mesi_state_transitions():
    """Test MESI state transitions"""
    cache = MESICache("cache_node", "localhost", 8000)
    
    # Write creates MODIFIED state
    await cache.write("key_1", "value_1")
    assert cache.cache["key_1"].state == CacheState.MODIFIED
    
    await cache.read("key_1")
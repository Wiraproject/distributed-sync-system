# Distributed Synchronization System

Sistem sinkronisasi terdistribusi yang mengimplementasikan **Raft Consensus**, **Distributed Locking**, **Distributed Queue**, dan **Cache Coherence (MESI Protocol)**.

## 📋 Fitur Utama

### 1. Distributed Lock Manager
- ✅ Implementasi **Raft Consensus Algorithm** untuk leader election
- ✅ Support untuk **Shared** dan **Exclusive** locks
- ✅ **Deadlock detection** untuk distributed environment
- ✅ Handle network partition scenarios
- ✅ Minimum 3 nodes dengan komunikasi peer-to-peer

### 2. Distributed Queue System
- ✅ **Consistent Hashing** untuk distribusi pesan
- ✅ Multiple producers dan consumers
- ✅ **Message persistence** dan recovery
- ✅ Handle node failure tanpa kehilangan data
- ✅ **At-least-once delivery** guarantee

### 3. Distributed Cache Coherence
- ✅ **MESI Protocol** (Modified, Exclusive, Shared, Invalid)
- ✅ Multiple cache nodes
- ✅ Cache invalidation dan update propagation
- ✅ **LRU replacement policy**
- ✅ Performance monitoring dan metrics collection

### 4. Containerization
- ✅ Dockerfile untuk setiap komponen
- ✅ Docker Compose untuk orchestration
- ✅ Dynamic node scaling
- ✅ Environment configuration

## 🏗️ Arsitektur Sistem

```
┌───────────────────────────────────────────────────────┐
│                 Client Applications                   │
└───────────────┬─────────────────────┬─────────────────┘
                │                     │
        ┌───────▼───────┐     ┌───────▼──────┐
        │  Lock Manager │     │ Queue System │
        │  (Raft-based) │     │ (Consistent  │
        └───────┬───────┘     │   Hashing)   │
                │             └──────┬───────┘
                │                    │
        ┌───────▼────────────────────▼───────┐
        │       Distributed Cache Nodes      │
        │           (MESI Protocol)          │
        └─────────────────┬──────────────────┘
                          │
                  ┌───────▼────────┐
                  │  Redis Backend │
                  │ (State Storage)│
                  └────────────────┘
```

## 🚀 Quick Start

### Prerequisite
```bash
# Install Python 3.8+
python --version

# Install Docker & Docker Compose
docker --version
docker-compose --version
```

### 1. Setup Environment
```bash
# Clone repository
git clone <repository-url>
cd distributed-sync-system

# Copy environment template
cp .env.example .env

# Install dependencies
pip install -r requirements.txt
```

### 2. Run dengan Docker Compose
```bash
# Start semua services
docker-compose -f docker/docker-compose.yml up -d

# Check logs
docker-compose -f docker/docker-compose.yml logs -f

# Scale nodes (tambah node_3, node_4)
docker-compose -f docker/docker-compose.yml up -d --scale node=5

# Stop services
docker-compose -f docker/docker-compose.yml down
```

### 3. Run Manual (Development)
```bash
# Terminal 1: Start Node 0
export NODE_ID=node_0 NODE_PORT=5000
python -m src.main

# Terminal 2: Start Node 1
export NODE_ID=node_1 NODE_PORT=5001
python -m src.main

# Terminal 3: Start Node 2
export NODE_ID=node_2 NODE_PORT=5002
python -m src.main
```

## 🧪 Testing

### Unit Tests
```bash
# Run all unit tests
pytest tests/unit/ -v

# Run with coverage
pytest tests/unit/ --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_raft.py -v
```

### Integration Tests
```bash
# Run integration tests
pytest tests/integration/ -v

# Test distributed system behavior
pytest tests/integration/test_distributed_system.py -v
```

### Performance Tests
```bash
# Run load tests
pytest tests/performance/ -v

# Run with detailed output
pytest tests/performance/test_load.py -v -s
```

### Load Testing dengan Locust
```bash
# Start Locust web interface
locust -f benchmarks/load_test_scenarios.py

# Open browser: http://localhost:8089
# Set users, spawn rate, dan mulai test
```

## 📊 Benchmarks

### Cache Performance
```python
python benchmarks/cache_benchmark.py
```

### Queue Performance
```python
python benchmarks/queue_benchmark.py
```

### Lock Manager Performance
```python
python benchmarks/lock_benchmark.py
```

## 🔬 Algoritma dan Protokol

### 1. Raft Consensus
**Leader Election:**
- Nodes mulai sebagai Follower
- Election timeout trigger kandidasi
- Candidate request votes dari peers
- Majority votes → Leader
- Leader sends heartbeats

**Log Replication:**
- Leader accepts commands
- Replicates to followers
- Commits when majority acknowledges

### 2. Consistent Hashing
```python
# Virtual nodes untuk load balancing
hash_ring = ConsistentHash(nodes, virtual_nodes=150)

# Key distribution
node = hash_ring.get_node(key)

# Minimal redistribution saat node gagal
hash_ring.remove_node(failed_node)
```

### 3. MESI Cache Coherence

**States:**
- **Modified (M)**: Cache memiliki data terbaru, memory stale
- **Exclusive (E)**: Cache memiliki data, sama dengan memory
- **Shared (S)**: Multiple caches memiliki data
- **Invalid (I)**: Cache line tidak valid

**Transitions:**
```
Read Miss:  I → S
Read Hit:   S → S, E → E, M → M
Write:      * → M (invalidate others)
Invalidate: * → I
```

## 🔐 Security Considerations

### Network Security
- Gunakan TLS untuk inter-node communication (production)
- Implement authentication tokens
- Rate limiting untuk API endpoints

### Data Security
- Encrypt sensitive data di cache
- Secure Redis dengan password
- Use Docker secrets untuk credentials

## 🚨 Failure Scenarios

### 1. Node Failure
**Deteksi:**
- Heartbeat timeout
- TCP connection failed
- No response to requests

**Recovery:**
- Leader election jika leader gagal
- Redistribute queue messages
- Invalidate cache entries

### 2. Network Partition
**Split Brain Prevention:**
- Raft requires majority consensus
- Minority partition cannot make progress
- Automatic reconciliation saat partition resolved

**Testing:**
```bash
# Simulate network partition
docker network disconnect distributed_net node_2

# Wait for re-election
sleep 5

# Reconnect
docker network connect distributed_net node_2
```

### 3. Data Loss Prevention
**Queue Persistence:**
- Write-ahead log untuk messages
- Periodic snapshots
- Recovery on restart

**Cache Write-back:**
- Modified cache lines written to memory before eviction
- Graceful shutdown flushes dirty data


## 👥 Authors

- **Wiranto** 
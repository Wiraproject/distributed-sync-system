# Distributed Synchronization System

Sistem sinkronisasi terdistribusi yang menyediakan **Distributed Lock Manager**, **Message Queue**, dan **Distributed Cache** dengan fault tolerance menggunakan algoritma Raft consensus.

---

## 📖 Deskripsi

**Distributed Synchronization System** adalah platform yang dirancang untuk mengelola sinkronisasi data dan koordinasi antar node dalam sistem terdistribusi. Sistem ini memastikan konsistensi data, high availability, dan fault tolerance melalui implementasi algoritma konsensus dan protokol cache coherence.

### Komponen Utama

1. **Distributed Lock Manager**
   - Manajemen lock (shared/exclusive) untuk akses resource
   - Konsensus menggunakan Raft algorithm
   - Deadlock detection dan automatic resolution
   - Leader election dan failover otomatis

2. **Distributed Queue System**
   - Message queue dengan consistent hashing
   - Persistent storage dengan Write-Ahead Logging (WAL)
   - At-least-once delivery guarantee
   - Load balancing otomatis antar node

3. **Distributed Cache System**
   - Cache coherence dengan MESI protocol
   - LRU eviction policy
   - Automatic invalidation pada write
   - Multi-node consistency

---

## ✨ Fitur Utama

### 🔒 Lock Management
- **Shared & Exclusive Locks**: Support untuk multiple readers atau single writer
- **Deadlock Detection**: Deteksi dan resolusi deadlock secara otomatis menggunakan wait-for graph
- **Lock Timeout**: Automatic lock release setelah timeout
- **Queue Management**: Waiting queue untuk lock requests yang tertunda
- **Fault Tolerance**: Replikasi state menggunakan Raft consensus

### 📬 Message Queue
- **Consistent Hashing**: Distribusi message merata dengan minimal redistribution
- **Persistence**: Write-Ahead Log untuk durability
- **Acknowledgment**: Explicit ACK untuk message completion
- **In-Flight Tracking**: Monitoring message yang sedang diproses
- **Auto Recovery**: Restore message dari log setelah node restart

### 💾 Distributed Cache
- **MESI Protocol**: Cache coherence untuk konsistensi multi-node
  - **M (Modified)**: Dirty data, exclusive ownership
  - **E (Exclusive)**: Clean data, exclusive ownership
  - **S (Shared)**: Clean data, multiple readers
  - **I (Invalid)**: Data tidak valid atau tidak ada
- **LRU Eviction**: Least Recently Used policy untuk memory management
- **Broadcast Invalidation**: Otomatis invalidate cache di semua node saat write
- **Write-Back**: Lazy write ke memory untuk performa optimal

### 🛡️ Fault Tolerance
- **Raft Consensus**: Leader election dan log replication
- **Network Partition Detection**: Deteksi split-brain scenario
- **Automatic Failover**: Seamless leader transition (200-300ms downtime)
- **Data Replication**: Majority quorum untuk write operations

---

## 🏗️ Arsitektur

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   CLIENT APPLICATIONS                   │
└────────────┬────────────────┬────────────────┬──────────┘
             │                │                │
             ▼                ▼                ▼
    ┌────────────────┐ ┌────────────┐ ┌────────────────┐
    │ Lock Manager   │ │   Queue    │ │     Cache      │
    │  (Port 8080+)  │ │(Port 9000+)│ │  (Port 7000+)  │
    └────────┬───────┘ └──────┬─────┘ └────────┬───────┘
             │                │                 │
             └────────────────┼─────────────────┘
                              │
             ┌────────────────▼─────────────────┐
             │   DISTRIBUTED NODE CLUSTER       │
             │                                  │
             │  ┌────────┐  ┌────────┐  ┌────────┐
             │  │ Node 0 │◄─┤ Node 1 │◄─┤ Node 2 │
             │  │(Leader)│  │(Follow)│  │(Follow)│
             │  └────────┘  └────────┘  └────────┘
             │                                  │
             │     Raft Consensus Layer         │
             └──────────────────────────────────┘
```

### Teknologi Stack

- **Backend Framework**: FastAPI (Python 3.11+)
- **Consensus Algorithm**: Raft
- **Cache Protocol**: MESI
- **Hashing**: Consistent Hashing (MD5)
- **Persistence**: File-based WAL
- **Communication**: HTTP/REST + Internal RPC
- **Containerization**: Docker + Docker Compose
- **Optional**: Redis (shared state storage)

### Algoritma & Protokol

1. **Raft Consensus**
   - Leader election dengan randomized timeout (150-300ms)
   - Log replication dengan AppendEntries RPC
   - Safety guarantees (election safety, log matching, leader completeness)

2. **MESI Cache Coherence**
   - State machine untuk cache consistency
   - Invalidation-based protocol
   - Write-back untuk Modified entries

3. **Consistent Hashing**
   - 150 virtual nodes per physical node
   - MD5 hash function
   - Minimal key remapping saat node add/remove

---

## 🚀 Cara Menjalankan

### Prerequisites

Pastikan Anda sudah menginstall:
- **Python 3.11+** (`python --version`)
- **Docker** dan **Docker Compose** (`docker --version`, `docker-compose --version`)
- **Git** (`git --version`)

---

### 1. Clone Repository

```bash
git clone https://github.com/Wiraproject/distributed-sync-system.git
cd distributed-sync-system
```

---

### 2. Deployment dengan Docker Compose (Recommended)

#### a. Build Docker Images

```bash
docker-compose -f docker/docker-compose.yml build
```

#### b. Start All Services

```bash
docker-compose -f docker/docker-compose.yml up -d  
```

Ini akan menjalankan:
- **3 Lock Manager nodes** (ports 8080, 8081, 8082)
- **3 Queue nodes** (ports 9000, 9001, 9002)
- **3 Cache nodes** (ports 7000, 7001, 7002)
- **Redis** (port 6379)

#### c. Verify Services

```bash
# Check running containers
docker-compose -f docker/docker-compose.yml ps

# Check logs
docker-compose -f docker/docker-compose.yml logs

# Test health endpoints
curl http://localhost:8080/health  # Lock Manager
curl http://localhost:7000/health  # Cache
curl http://localhost:9000/health  # Queue
```

Expected response:
```json
{
  "status": "healthy",
  "node_id": "node_0",
  "is_running": true,
  "type": "lock_manager"
}
```

#### d. Check Raft Status

```bash
curl http://localhost:8080/status
```

Expected response:
```json
{
  "node_id": "node_0",
  "state": "leader",
  "is_leader": true,
  "current_term": 1,
  "partition_detected": false,
  "peers": ["node_1", "node_2"],
  "commit_index": 0,
  "last_applied": 0
}
```

---

### 3. Manual Installation (Development Mode)

#### a. Setup Python Environment

```bash
# Create virtual environment
python -m venv venv

# Activate (Linux/Mac)
source venv/bin/activate

# Activate (Windows)
.\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### b. Start Redis (Optional)

```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

#### c. Configure Environment

```bash
cp .env.example .env
nano .env
```

Edit `.env`:
```bash
NODE_ID=node_0
NODE_HOST=localhost
NODE_PORT=8080
API_PORT=8080
PEER_NODES=node_1:localhost:8081,node_2:localhost:8082
LOG_LEVEL=INFO
```

#### d. Start Nodes Manually

**Terminal 1 - Lock Manager Node 0**:
```bash
export NODE_ID=node_0
export API_PORT=8080
export PEER_NODES=node_1:localhost:8081,node_2:localhost:8082
python -m uvicorn src.api.lock_manager_server:app --host 0.0.0.0 --port 8080
```

**Terminal 2 - Lock Manager Node 1**:
```bash
export NODE_ID=node_1
export API_PORT=8081
export PEER_NODES=node_0:localhost:8080,node_2:localhost:8082
python -m uvicorn src.api.lock_manager_server:app --host 0.0.0.0 --port 8081
```

**Terminal 3 - Lock Manager Node 2**:
```bash
export NODE_ID=node_2
export API_PORT=8082
export PEER_NODES=node_0:localhost:8080,node_1:localhost:8081
python -m uvicorn src.api.lock_manager_server:app --host 0.0.0.0 --port 8082
```

Ulangi proses serupa untuk **Cache nodes** (port 7000-7002) dan **Queue nodes** (port 9000-9002).

---

## 📚 Penggunaan API

### Lock Manager

#### Acquire Lock
```bash
curl -X POST http://localhost:8080/locks/acquire \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "database:users",
    "client_id": "service_a",
    "lock_type": "exclusive",
    "timeout_seconds": 60
  }'
```

Response:
```json
{
  "success": true,
  "message": "Lock acquired",
  "lock_id": "database:users:service_a"
}
```

#### Release Lock
```bash
curl -X POST http://localhost:8080/locks/release \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "database:users",
    "client_id": "service_a"
  }'
```

#### Check Lock Status
```bash
curl http://localhost:8080/locks/database:users
```

---

### Queue System

#### Enqueue Message
```bash
curl -X POST http://localhost:9000/queue/enqueue \
  -H "Content-Type: application/json" \
  -d '{
    "queue_name": "orders",
    "message": {"order_id": 123, "customer": "John Doe"}
  }'
```

Response:
```json
{
  "success": true,
  "message_id": "queue_0-1",
  "queue_name": "orders",
  "node_id": "queue_0"
}
```

#### Dequeue Message
```bash
curl -X POST http://localhost:9000/queue/dequeue \
  -H "Content-Type: application/json" \
  -d '{"queue_name": "orders"}'
```

Response:
```json
{
  "success": true,
  "message": {"order_id": 123, "customer": "John Doe"},
  "message_id": "queue_0-1",
  "delivery_time": "2025-01-28T10:30:00"
}
```

#### Acknowledge Message
```bash
curl -X POST http://localhost:9000/queue/ack \
  -H "Content-Type: application/json" \
  -d '{"message_id": "queue_0-1"}'
```

---

### Cache System

#### Write to Cache
```bash
curl -X POST http://localhost:7000/cache \
  -H "Content-Type: application/json" \
  -d '{
    "key": "user:123",
    "value": {"name": "Alice", "age": 30}
  }'
```

Response:
```json
{
  "success": true,
  "key": "user:123",
  "message": "Value cached successfully in state MODIFIED"
}
```

#### Read from Cache
```bash
curl http://localhost:7000/cache/user:123
```

Response:
```json
{
  "success": true,
  "key": "user:123",
  "value": {"name": "Alice", "age": 30},
  "hit": true,
  "state": "M"
}
```

#### Get Cache Metrics
```bash
curl http://localhost:7000/cache/metrics
```

Response:
```json
{
  "node_id": "cache_0",
  "hits": 150,
  "misses": 50,
  "hit_rate": 0.75,
  "cache_size": 80,
  "capacity": 100,
  "evictions": 10,
  "state_distribution": {"M": 20, "E": 30, "S": 25, "I": 5}
}
```

---

## 🧪 Testing

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest tests/ -v

# Run specific test categories
pytest tests/unit/ -v              # Unit tests
pytest tests/integration/ -v       # Integration tests
pytest tests/performance/ -v       # Performance tests

# Run with coverage
pytest --cov=src --cov-report=html
```

### Run Benchmarks

```bash
# Run integrated benchmarks
python benchmarks/run_benchmarks.py

# Run specific component benchmarks
python benchmarks/lock_benchmark.py
python benchmarks/cache_benchmark.py
python benchmarks/queue_benchmark.py

python -m benchmarks.comparison_test 

# Generate performance reports
python benchmarks/generate_reports.py --output ./reports 
```

### Load Testing with Locust

```bash
# Install Locust
pip install locust

# Run load test
locust -f benchmarks/load_test_scenarios.py --web-host=localhost

# Open browser: http://localhost:8089
```

---

## 📊 Monitoring

### Health Checks

```bash
# Check all services
./scripts/health_check.sh

# Or manually
for port in 8080 8081 8082; do
  curl -s http://localhost:$port/health | jq '.'
done
```

### View Logs

```bash
# All services
docker-compose -f docker/docker-compose.yml logs

# Specific service
docker-compose -f docker/docker-compose.yml logs node_0

# Tail last 100 lines
docker-compose -f docker/docker-compose.yml logs --tail=100
```

### Metrics

```bash
# Lock Manager metrics
curl http://localhost:8080/metrics

# Cache metrics
curl http://localhost:7000/cache/metrics

# Queue status
curl http://localhost:9000/queue/all
```

---

## 🛠️ Management Commands

### Start/Stop Services

```bash
# Start all services
docker-compose -f docker/docker-compose.yml up -d

# Stop all services
docker-compose -f docker/docker-compose.yml down

# Restart specific service
docker-compose -f docker/docker-compose.yml restart node_0

# Scale services
docker-compose -f docker/docker-compose.yml up -d --scale node=5
```

### View Service Status

```bash
# Container status
docker-compose -f docker/docker-compose.yml ps

# Resource usage
docker stats

# Network inspection
docker network inspect distributed_net
```

### Clean Up

```bash
# Stop and remove containers, networks
docker-compose -f docker/docker-compose.yml down

# Remove volumes (data will be lost!)
docker-compose -f docker/docker-compose.yml down -v

# Remove images
docker rmi $(docker images -q distributed-sync)
```

---

## 📖 Dokumentasi Lengkap

- **[Architecture Documentation](docs/architecture.md)** - Detail arsitektur sistem, algoritma, dan protokol
- **[API Specification](docs/api_spec.yaml)** - OpenAPI specification untuk semua endpoints
- **[Deployment Guide](docs/deployment_guide.md)** - Panduan deployment production, troubleshooting, tuning

---

## 👥 Authors

**Distributed Systems Team**
- Email: wiirantooo@gmail.com
- GitHub: [@Wiraproject](https://github.com/Wiraproject)
- Youtube: https://youtu.be/yUYwwmBudR0?feature=shared

---
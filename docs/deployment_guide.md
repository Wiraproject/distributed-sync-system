# Deployment Guide

## 📋 Table of Contents
1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Deployment Methods](#deployment-methods)
5. [Monitoring & Maintenance](#monitoring--maintenance)
6. [Troubleshooting](#troubleshooting)
7. [Performance Tuning](#performance-tuning)
8. [Security Considerations](#security-considerations)

---

## ✅ Prerequisites

### System Requirements

**Hardware (Minimum per Node)**:
- CPU: 2 cores
- RAM: 2 GB
- Disk: 10 GB SSD
- Network: 1 Gbps

**Hardware (Recommended Production)**:
- CPU: 4+ cores
- RAM: 8 GB
- Disk: 50 GB SSD (for logs)
- Network: 10 Gbps

### Software Dependencies

```bash
# Python 3.11+
python --version  # Should be 3.11 or higher

# Docker & Docker Compose
docker --version  # 24.0+
docker-compose --version  # 2.20+

# Redis (for production deployment)
redis-cli --version  # 7.0+

# Git
git --version
```

### Network Requirements

**Required Ports**:

| Service | Port Range | Protocol | Purpose |
|---------|-----------|----------|---------|
| Lock Manager | 8080-8082 | TCP | REST API |
| Queue System | 9000-9002 | TCP | REST API |
| Cache System | 7000-7002 | TCP | REST API |
| Redis | 6379 | TCP | Shared state (optional) |
| Internal RPC | Dynamic | TCP | Node communication |

**Firewall Rules**:
```bash
# Allow incoming connections on service ports
sudo ufw allow 8080:8082/tcp  # Lock Manager
sudo ufw allow 9000:9002/tcp  # Queue
sudo ufw allow 7000:7002/tcp  # Cache
sudo ufw allow 6379/tcp       # Redis (if external)
```

---

## 📦 Installation

### Method 1: Docker Compose (Recommended)

**Step 1: Clone Repository**

```bash
git clone https://github.com/Wiraproject/distributed-sync-system.git
cd distributed-sync-system
```

**Step 2: Build Images**

```bash
# Build all services
docker-compose build

# Or build specific service
docker-compose build node_0
```

**Step 3: Start Services**

```bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f node_0
```

**Expected Output**:
```
Creating network "distributed_net" with driver "bridge"
Creating redis     ... done
Creating node_0    ... done
Creating node_1    ... done
Creating node_2    ... done
Creating cache_0   ... done
Creating queue_0   ... done
...
```

**Step 4: Verify Deployment**

```bash
# Check health of all nodes
curl http://localhost:8080/health  # Lock Manager Node 0
curl http://localhost:8081/health  # Lock Manager Node 1
curl http://localhost:7000/health  # Cache Node 0
curl http://localhost:9000/health  # Queue Node 0

# Check Raft status
curl http://localhost:8080/status
```

**Expected Response**:
```json
{
  "status": "healthy",
  "node_id": "node_0",
  "is_running": true,
  "type": "lock_manager"
}
```

---

### Method 2: Manual Installation (Development)

**Step 1: Setup Python Environment**

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

**Step 2: Start Redis (Optional)**

```bash
# Using Docker
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Or install locally
sudo apt-get install redis-server
sudo systemctl start redis
```

**Step 3: Configure Environment**

```bash
# Copy example environment file
cp .env.example .env

# Edit configuration
nano .env
```

**Sample .env**:
```bash
# Node Configuration
NODE_ID=node_0
NODE_HOST=localhost
NODE_PORT=8080
API_PORT=8080

# Node Type
NODE_TYPE=lock_manager

# Peer Nodes (format: id:host:port)
PEER_NODES=node_1:localhost:8081,node_2:localhost:8082

# Redis Configuration (optional)
REDIS_HOST=localhost
REDIS_PORT=6379

# Logging
LOG_LEVEL=INFO

# Performance
NUM_NODES=3
CACHE_CAPACITY=100
```

**Step 4: Start Nodes Manually**

**Terminal 1 - Lock Manager Node 0**:
```bash
export NODE_ID=node_0
export NODE_PORT=8080
export API_PORT=8080
export PEER_NODES=node_1:localhost:8081,node_2:localhost:8082

python -m uvicorn src.api.lock_manager_server:app --host 0.0.0.0 --port 8080
```

**Terminal 2 - Lock Manager Node 1**:
```bash
export NODE_ID=node_1
export NODE_PORT=8081
export API_PORT=8081
export PEER_NODES=node_0:localhost:8080,node_2:localhost:8082

python -m uvicorn src.api.lock_manager_server:app --host 0.0.0.0 --port 8081
```

**Terminal 3 - Lock Manager Node 2**:
```bash
export NODE_ID=node_2
export NODE_PORT=8082
export API_PORT=8082
export PEER_NODES=node_0:localhost:8080,node_1:localhost:8081

python -m uvicorn src.api.lock_manager_server:app --host 0.0.0.0 --port 8082
```

**Similar for Cache and Queue nodes** (use respective servers and port ranges).

---

## ⚙️ Configuration

### Environment Variables

**Required Variables**:

| Variable | Description | Example |
|----------|-------------|---------|
| `NODE_ID` | Unique node identifier | `node_0` |
| `NODE_HOST` | Node hostname/IP | `localhost` or `192.168.1.10` |
| `NODE_PORT` | Internal communication port | `8080` |
| `API_PORT` | REST API port | `8080` |
| `NODE_TYPE` | Service type | `lock_manager`, `queue`, `cache` |
| `PEER_NODES` | Comma-separated peer list | `node_1:host:port,node_2:host:port` |

**Optional Variables**:

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_LEVEL` | Logging verbosity | `INFO` |
| `CACHE_CAPACITY` | Max cache entries | `100` |
| `NUM_NODES` | Total cluster nodes | `3` |
| `REDIS_HOST` | Redis hostname | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |

### Logging Configuration

**Location**: `src/utils/logging_config.py`

```python
# Customize log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,     # Detailed debugging
    "INFO": logging.INFO,       # General info
    "WARNING": logging.WARNING, # Warnings
    "ERROR": logging.ERROR,     # Errors only
}

# Log file rotation
ROTATION = {
    "maxBytes": 10 * 1024 * 1024,  # 10 MB
    "backupCount": 5                # Keep 5 old logs
}
```

**Log Files**:
```
logs/
├── node_0.log          # Lock Manager Node 0
├── node_1.log          # Lock Manager Node 1
├── cache_0.log         # Cache Node 0
├── queue_0.log         # Queue Node 0
└── node_0_queue.log    # Queue persistence log
```

---

## 🚀 Deployment Methods

### Production Deployment (Kubernetes)

**Step 1: Create Namespace**

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: distributed-sync
```

```bash
kubectl apply -f namespace.yaml
```

**Step 2: Deploy Redis**

```yaml
# redis-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: distributed-sync
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        ports:
        - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: distributed-sync
spec:
  selector:
    app: redis
  ports:
  - port: 6379
    targetPort: 6379
```

```bash
kubectl apply -f redis-deployment.yaml
```

**Step 3: Deploy Lock Manager Nodes**

```yaml
# lock-manager-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: lock-manager
  namespace: distributed-sync
spec:
  serviceName: lock-manager
  replicas: 3
  selector:
    matchLabels:
      app: lock-manager
  template:
    metadata:
      labels:
        app: lock-manager
    spec:
      containers:
      - name: lock-manager
        image: distributed-sync:latest
        command: 
          - python
          - -m
          - uvicorn
          - src.api.lock_manager_server:app
          - --host
          - "0.0.0.0"
          - --port
          - "8080"
        ports:
        - containerPort: 8080
          name: api
        env:
        - name: NODE_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: NODE_HOST
          valueFrom:
            fieldRef:
              fieldPath: status.podIP
        - name: NODE_PORT
          value: "8080"
        - name: API_PORT
          value: "8080"
        - name: PEER_NODES
          value: "lock-manager-0:lock-manager-0.lock-manager:8080,lock-manager-1:lock-manager-1.lock-manager:8080,lock-manager-2:lock-manager-2.lock-manager:8080"
        - name: REDIS_HOST
          value: "redis"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
        volumeMounts:
        - name: logs
          mountPath: /app/logs
  volumeClaimTemplates:
  - metadata:
      name: logs
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 10Gi
---
apiVersion: v1
kind: Service
metadata:
  name: lock-manager
  namespace: distributed-sync
spec:
  clusterIP: None
  selector:
    app: lock-manager
  ports:
  - port: 8080
    name: api
---
apiVersion: v1
kind: Service
metadata:
  name: lock-manager-lb
  namespace: distributed-sync
spec:
  type: LoadBalancer
  selector:
    app: lock-manager
  ports:
  - port: 8080
    targetPort: 8080
```

```bash
kubectl apply -f lock-manager-statefulset.yaml
```

**Step 4: Deploy Cache and Queue** (similar pattern)

**Step 5: Verify Deployment**

```bash
# Check pods
kubectl get pods -n distributed-sync

# Check services
kubectl get svc -n distributed-sync

# View logs
kubectl logs -n distributed-sync lock-manager-0 -f

# Execute command in pod
kubectl exec -it -n distributed-sync lock-manager-0 -- /bin/bash
```

---

### Cloud Deployment (AWS)

**Architecture**:

```
┌─────────────────────────────────────────────────────┐
│                    AWS VPC                          │
│                                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │         Application Load Balancer            │ │
│  │  (ALB for distributing client requests)      │ │
│  └────────────┬─────────────────────────────────┘ │
│               │                                    │
│  ┌────────────┴─────────────────────────────────┐ │
│  │            Target Group                      │ │
│  │  (Lock Manager / Cache / Queue Nodes)        │ │
│  └────┬──────────────┬──────────────┬──────────┘ │
│       │              │              │             │
│  ┌────▼────┐   ┌────▼────┐   ┌────▼────┐        │
│  │ EC2 / ECS │ │ EC2 / ECS │ │ EC2 / ECS │      │
│  │  Node 0   │ │  Node 1   │ │  Node 2   │      │
│  └───────────┘ └───────────┘ └───────────┘        │
│                                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │         ElastiCache (Redis)                  │ │
│  │  (Optional shared state storage)             │ │
│  └──────────────────────────────────────────────┘ │
│                                                     │
│  ┌──────────────────────────────────────────────┐ │
│  │         EBS Volumes                          │ │
│  │  (Persistent logs and data)                  │ │
│  └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

**Terraform Example**:

```hcl
# main.tf
provider "aws" {
  region = "us-east-1"
}

# ECS Cluster
resource "aws_ecs_cluster" "distributed_sync" {
  name = "distributed-sync-cluster"
}

# Task Definition
resource "aws_ecs_task_definition" "lock_manager" {
  family                   = "lock-manager"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"

  container_definitions = jsonencode([{
    name  = "lock-manager"
    image = "your-ecr-repo/distributed-sync:latest"
    portMappings = [{
      containerPort = 8080
      protocol      = "tcp"
    }]
    environment = [
      { name = "NODE_TYPE", value = "lock_manager" },
      { name = "LOG_LEVEL", value = "INFO" }
    ]
  }])
}

# ECS Service
resource "aws_ecs_service" "lock_manager" {
  name            = "lock-manager-service"
  cluster         = aws_ecs_cluster.distributed_sync.id
  task_definition = aws_ecs_task_definition.lock_manager.arn
  desired_count   = 3
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = aws_subnet.private[*].id
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.lock_manager.arn
    container_name   = "lock-manager"
    container_port   = 8080
  }
}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "distributed-sync-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

# Target Group
resource "aws_lb_target_group" "lock_manager" {
  name        = "lock-manager-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "distributed-sync-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
}
```

```bash
# Deploy infrastructure
terraform init
terraform plan
terraform apply
```

---

## 📊 Monitoring & Maintenance

### Monitoring Stack

**Prometheus + Grafana Setup**:

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'lock-manager'
    static_configs:
      - targets:
        - 'localhost:8080'
        - 'localhost:8081'
        - 'localhost:8082'
    metrics_path: '/metrics'

  - job_name: 'cache'
    static_configs:
      - targets:
        - 'localhost:7000'
        - 'localhost:7001'
        - 'localhost:7002'

  - job_name: 'queue'
    static_configs:
      - targets:
        - 'localhost:9000'
        - 'localhost:9001'
        - 'localhost:9002'
```

**Start Monitoring**:

```bash
# Docker Compose for monitoring stack
docker-compose -f docker-compose.monitoring.yml up -d
```

**Grafana Dashboards**:
- Import pre-built dashboards from `docs/grafana/`
- Access: http://localhost:3000 (default: admin/admin)

### Health Checks

**Automated Health Check Script**:

```bash
#!/bin/bash
# health_check.sh

NODES=(
    "http://localhost:8080"
    "http://localhost:8081"
    "http://localhost:8082"
    "http://localhost:7000"
    "http://localhost:9000"
)

for node in "${NODES[@]}"; do
    response=$(curl -s -o /dev/null -w "%{http_code}" "$node/health")
    if [ "$response" == "200" ]; then
        echo "✓ $node is healthy"
    else
        echo "✗ $node is unhealthy (HTTP $response)"
        # Send alert
        # curl -X POST https://hooks.slack.com/... \
        #      -d "{'text':'Node $node is down'}"
    fi
done
```

**Cron Job**:
```bash
# Run health check every 5 minutes
*/5 * * * * /path/to/health_check.sh
```

### Backup & Recovery

**Backup Lock Manager State**:

```bash
#!/bin/bash
# backup_locks.sh

BACKUP_DIR="/backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup lock state from leader
LEADER=$(curl -s http://localhost:8080/status | jq -r '.node_id')
curl -s http://localhost:8080/locks > $BACKUP_DIR/locks.json

# Backup logs
cp -r logs/ $BACKUP_DIR/logs/

# Compress
tar -czf $BACKUP_DIR.tar.gz $BACKUP_DIR/
rm -rf $BACKUP_DIR

# Upload to S3 (optional)
# aws s3 cp $BACKUP_DIR.tar.gz s3://my-bucket/backups/
```

**Recovery Procedure**:

```bash
# 1. Stop all nodes
docker-compose down

# 2. Restore logs
tar -xzf /backups/20250128.tar.gz -C /tmp
cp -r /tmp/20250128/logs/ ./logs/

# 3. Restart cluster
docker-compose up -d

# 4. Verify recovery
curl http://localhost:8080/status
curl http://localhost:8080/locks
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. **Leader Election Fails**

**Symptoms**:
- No leader elected after 5 seconds
- All nodes stuck in `candidate` state
- Log shows: `Election timeout, becoming candidate`

**Diagnosis**:
```bash
# Check node status
curl http://localhost:8080/status
curl http://localhost:8081/status
curl http://localhost:8082/status

# Check network connectivity
docker exec node_0 ping node_1
docker exec node_0 ping node_2
```

**Solution**:

```bash
# 1. Check peer configuration
docker exec node_0 env | grep PEER_NODES

# 2. Verify all nodes can communicate
docker network inspect distributed_net

# 3. Restart nodes in sequence
docker-compose restart node_0
sleep 5
docker-compose restart node_1
sleep 5
docker-compose restart node_2

# 4. Force election timeout increase
# Edit src/consensus/raft.py:
# self.election_timeout = random.uniform(300, 600) / 1000  # Increase from 150-300

# Rebuild and restart
docker-compose build
docker-compose up -d
```

---

#### 2. **Cache Inconsistency**

**Symptoms**:
- Different nodes return different values for same key
- MESI state incorrect (e.g., multiple Modified copies)

**Diagnosis**:
```bash
# Check cache state on all nodes
curl http://localhost:7000/cache/status/test_key
curl http://localhost:7001/cache/status/test_key
curl http://localhost:7002/cache/status/test_key

# Check MESI states
curl http://localhost:7000/cache/all | jq '.keys'
```

**Solution**:

```bash
# 1. Clear all caches
for port in 7000 7001 7002; do
    curl -X DELETE http://localhost:$port/cache/test_key
done

# 2. Verify peer connectivity
docker exec cache_0 env | grep PEER_NODES

# 3. Check logs for invalidation messages
docker logs cache_0 | grep "invalidate"
docker logs cache_1 | grep "invalidate"

# 4. Restart cache cluster
docker-compose restart cache_0 cache_1 cache_2
```

---

#### 3. **Queue Messages Lost**

**Symptoms**:
- Messages enqueued but never dequeued
- WAL shows entries but queue is empty
- Recovery doesn't restore messages

**Diagnosis**:
```bash
# Check queue status
curl http://localhost:9000/queue/status/my_queue

# Check WAL file
docker exec queue_0 cat /app/logs/queue_0_queue.log | tail -n 20

# Check in-flight messages
curl http://localhost:9000/queue/all
```

**Solution**:

```bash
# 1. Verify consistent hash ring
docker logs queue_0 | grep "Consistent hash ring initialized"

# 2. Manual recovery
docker exec queue_0 python -c "
from src.nodes.queue_node import DistributedQueue
queue = DistributedQueue('queue_0', 'localhost', 9000)
queue.initialize_consistent_hash()
import asyncio
asyncio.run(queue.recover_from_log())
print(f'Recovered {sum(len(q) for q in queue.queues.values())} messages')
"

# 3. Acknowledge stuck messages
# Get message IDs from in-flight
curl http://localhost:9000/queue/all | jq '.in_flight'

# ACK each message
curl -X POST http://localhost:9000/queue/ack \
     -H "Content-Type: application/json" \
     -d '{"message_id":"queue_0-123"}'
```

---

#### 4. **Deadlock Not Resolving**

**Symptoms**:
- Multiple clients stuck waiting for locks
- Deadlock detected but not resolved
- Lock acquisition timeouts

**Diagnosis**:
```bash
# Check for deadlocks
curl http://localhost:8080/locks | jq '.locks'

# Check wait queue
docker logs node_0 | grep "deadlock"

# Check lock graph
docker exec node_0 python -c "
from src.nodes.lock_manager import DistributedLockManager
# Print lock graph state
"
```

**Solution**:

```bash
# 1. Manual deadlock detection
curl -X POST http://localhost:8080/detect-deadlock

# 2. Force release stuck locks (use carefully!)
curl -X POST http://localhost:8080/locks/release \
     -H "Content-Type: application/json" \
     -d '{"resource":"stuck_resource","client_id":"client_1"}'

# 3. Restart lock manager (last resort)
docker-compose restart node_0 node_1 node_2

# Wait for leader election
sleep 10

# Verify recovery
curl http://localhost:8080/status
```

---

#### 5. **High Latency**

**Symptoms**:
- p99 latency > 500ms
- Slow lock acquisitions
- Cache misses take too long

**Diagnosis**:
```bash
# Check metrics
curl http://localhost:8080/metrics

# Run benchmark
python benchmarks/run_benchmarks.py

# Check network latency
docker exec node_0 ping -c 10 node_1

# Check system resources
docker stats
```

**Solution**:

```bash
# 1. Optimize Raft timeouts
# Edit src/consensus/raft.py:
# self.election_timeout = 0.15  # Reduce timeout
# self.heartbeat_interval = 0.05

# 2. Increase cache capacity
# Edit docker-compose.yml:
# CACHE_CAPACITY=500

# 3. Enable connection pooling
# Edit src/nodes/base_node.py:
# Use persistent httpx.AsyncClient

# 4. Scale horizontally
docker-compose scale node=5 cache=5 queue=5

# 5. Enable compression (for large payloads)
# Add middleware in FastAPI servers
```

---

### Log Analysis

**Common Error Patterns**:

```bash
# Find errors in logs
docker logs node_0 2>&1 | grep ERROR

# Search for specific patterns
docker logs node_0 | grep -i "connection refused"
docker logs node_0 | grep -i "timeout"
docker logs node_0 | grep -i "election"

# Export logs for analysis
docker logs node_0 > /tmp/node_0.log
docker logs node_1 > /tmp/node_1.log

# Analyze with tools
cat /tmp/node_0.log | grep "ERROR" | sort | uniq -c | sort -rn
```

**Log Levels**:

```bash
# Increase verbosity for debugging
docker-compose down
# Edit docker-compose.yml: LOG_LEVEL=DEBUG
docker-compose up -d

# Tail logs in real-time
docker-compose logs -f --tail=100
```

---

## ⚡ Performance Tuning

### Raft Tuning

```python
# src/consensus/raft.py

# Reduce election timeout for faster failover
self.election_timeout = random.uniform(100, 200) / 1000  # 100-200ms

# Reduce heartbeat interval
self.heartbeat_interval = 30 / 1000  # 30ms

# Batch AppendEntries
MAX_BATCH_SIZE = 50  # Send up to 50 entries per RPC
```

### Cache Tuning

```python
# src/nodes/cache_node.py

# Increase capacity for hot data
DEFAULT_CAPACITY = 1000  # Increase from 100

# Optimize eviction
# Use SEGMENTED_LRU instead of simple LRU
# Separate hot and cold data

# Async invalidations
# Don't wait for all peers to acknowledge
# Use fire-and-forget for invalidations
```

### Queue Tuning

```python
# src/nodes/queue_node.py

# Batch operations
ENQUEUE_BATCH_SIZE = 100
DEQUEUE_BATCH_SIZE = 50

# Reduce WAL flushes
BUFFER_SIZE = 1024 * 1024  # 1 MB buffer before flush

# Increase virtual nodes
VIRTUAL_NODES = 200  # Better load distribution
```

---

## 🔒 Security Considerations

### Authentication & Authorization

```python
# Add JWT authentication to FastAPI

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(
            credentials.credentials,
            SECRET_KEY,
            algorithms=["HS256"]
        )
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token"
        )

@app.post("/locks/acquire", dependencies=[Depends(verify_token)])
async def acquire_lock(...):
    ...
```

### Network Security

```bash
# Enable TLS for inter-node communication
# Generate certificates
openssl req -x509 -newkey rsa:4096 \
    -keyout key.pem -out cert.pem \
    -days 365 -nodes

# Configure nodes to use HTTPS
# Edit docker-compose.yml:
# command: uvicorn ... --ssl-keyfile=/certs/key.pem --ssl-certfile=/certs/cert.pem
```

### Rate Limiting

```python
# Add rate limiting middleware

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/locks/acquire")
@limiter.limit("10/minute")  # Max 10 requests per minute
async def acquire_lock(...):
    ...
```

---

## 📚 Additional Resources

### Documentation
- [Architecture Details](./architecture.md)
- [API Specification](./api_spec.yaml)
- [Testing Guide](../tests/README.md)
- [Benchmark Results](../benchmarks/README.md)

### External References
- [Raft Consensus](https://raft.github.io/)
- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Redis Documentation](https://redis.io/documentation)

### Quick Reference Commands

**Docker Compose**:
```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart node_0

# View logs
docker-compose logs -f node_0

# Scale services
docker-compose up -d --scale node=5

# Rebuild after code changes
docker-compose build && docker-compose up -d

# Remove all containers and volumes
docker-compose down -v
```

**Health Checks**:
```bash
# Check all lock manager nodes
for port in 8080 8081 8082; do
    curl -s http://localhost:$port/health | jq '.'
done

# Check all cache nodes
for port in 7000 7001 7002; do
    curl -s http://localhost:$port/health | jq '.'
done

# Check all queue nodes
for port in 9000 9001 9002; do
    curl -s http://localhost:$port/health | jq '.'
done
```

**Testing**:
```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run performance tests
pytest tests/performance/ -v

# Run all tests with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/unit/test_lock_manager.py::test_acquire_exclusive_lock -v
```

**Benchmarks**:
```bash
# Run integrated benchmarks
python benchmarks/run_benchmarks.py

# Run specific component benchmark
python benchmarks/lock_benchmark.py
python benchmarks/cache_benchmark.py
python benchmarks/queue_benchmark.py

# Generate performance reports
python benchmarks/generate_reports.py

# Run load tests with Locust
locust -f benchmarks/load_test_scenarios.py \
       --host=http://localhost:8080 \
       --users=100 \
       --spawn-rate=10 \
       --run-time=5m
```

---

## 🐛 Debugging Tips

### Enable Debug Mode

```bash
# Set debug logging
export LOG_LEVEL=DEBUG

# Or in docker-compose.yml
environment:
  - LOG_LEVEL=DEBUG

# Restart services
docker-compose restart
```

### Interactive Debugging

```python
# Add breakpoints in code
import pdb; pdb.set_trace()

# Or use ipdb for better experience
import ipdb; ipdb.set_trace()

# Run without Docker for debugging
python -m src.api.lock_manager_server
```

### Network Debugging

```bash
# Check container network
docker network inspect distributed_net

# Test connectivity between containers
docker exec node_0 ping node_1
docker exec node_0 nc -zv node_1 8081

# Monitor network traffic
docker exec node_0 tcpdump -i eth0 -n

# Check DNS resolution
docker exec node_0 nslookup node_1
```

### Database/State Inspection

```bash
# Connect to Redis
docker exec -it redis redis-cli

# List all keys
127.0.0.1:6379> KEYS *

# Get specific key
127.0.0.1:6379> GET some_key

# Monitor commands
127.0.0.1:6379> MONITOR

# Check memory usage
127.0.0.1:6379> INFO memory
```

### Performance Profiling

```python
# Add profiling to endpoints
import cProfile
import pstats
from io import StringIO

@app.get("/profile")
async def profile_endpoint():
    pr = cProfile.Profile()
    pr.enable()
    
    # Your code here
    result = await some_operation()
    
    pr.disable()
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats()
    
    return {"profile": s.getvalue()}
```

```bash
# Use py-spy for live profiling
pip install py-spy

# Profile running process
sudo py-spy record -o profile.svg --pid <PID>

# Top-like view
sudo py-spy top --pid <PID>
```

---

## 📋 Pre-Production Checklist

### Infrastructure

- [ ] All nodes can communicate with each other
- [ ] Firewall rules configured correctly
- [ ] DNS resolution works
- [ ] Load balancer configured and tested
- [ ] Persistent volumes attached
- [ ] Backup strategy implemented
- [ ] Monitoring stack deployed
- [ ] Alerting rules configured

### Configuration

- [ ] Environment variables reviewed
- [ ] Peer node lists correct
- [ ] Timeouts tuned for network latency
- [ ] Log levels appropriate (INFO for prod)
- [ ] Resource limits set (CPU, memory)
- [ ] TLS certificates valid
- [ ] Secrets managed securely

### Testing

- [ ] All unit tests pass
- [ ] Integration tests pass
- [ ] Load tests completed successfully
- [ ] Failover scenarios tested
- [ ] Data recovery tested
- [ ] Performance benchmarks meet SLA
- [ ] Security scan completed

### Documentation

- [ ] Architecture documented
- [ ] API documentation updated
- [ ] Runbooks created
- [ ] Disaster recovery plan documented
- [ ] Team trained on operations

### Monitoring

- [ ] Health check endpoints working
- [ ] Metrics exported to Prometheus
- [ ] Grafana dashboards configured
- [ ] Alerts configured for critical metrics
- [ ] Log aggregation setup
- [ ] Tracing enabled (optional)

---

## 🚨 Emergency Procedures

### Total Cluster Failure

**Scenario**: All nodes are down

```bash
# 1. Check infrastructure
# - Network connectivity
# - VM/container status
# - Resource availability

# 2. Start Redis first
docker-compose up -d redis
sleep 5

# 3. Start nodes sequentially
docker-compose up -d node_0
sleep 10  # Wait for node_0 to initialize

docker-compose up -d node_1
sleep 5

docker-compose up -d node_2
sleep 5

# 4. Verify leader election
curl http://localhost:8080/status | jq '.state'

# 5. Start remaining services
docker-compose up -d cache_0 cache_1 cache_2
docker-compose up -d queue_0 queue_1 queue_2

# 6. Verify all services
./scripts/health_check.sh

# 7. Check logs for errors
docker-compose logs --tail=100 | grep ERROR
```

### Data Corruption

**Scenario**: Detected inconsistent state

```bash
# 1. Stop all writes immediately
# - Update load balancer to return 503
# - Or stop accepting requests

# 2. Snapshot current state
docker-compose exec node_0 sh -c 'cp -r logs /backup/emergency-$(date +%s)'

# 3. Identify corruption source
docker logs node_0 | grep -i "error\|corrupt\|inconsist"

# 4. Restore from last good backup
tar -xzf /backups/last-good-backup.tar.gz
docker-compose down
cp -r last-good-backup/logs ./logs/
docker-compose up -d

# 5. Verify data integrity
curl http://localhost:8080/locks | jq '.'

# 6. Resume normal operations
# - Update load balancer
# - Monitor closely
```

### Security Breach

**Scenario**: Unauthorized access detected

```bash
# 1. Isolate affected nodes immediately
docker-compose stop node_0  # If node_0 is compromised

# 2. Change all credentials
# - Generate new JWT secrets
# - Rotate TLS certificates
# - Update Redis passwords

# 3. Audit logs for suspicious activity
docker logs node_0 --since 24h | grep -E "401|403|suspicious_pattern"

# 4. Rebuild affected nodes from clean image
docker-compose down node_0
docker-compose build --no-cache node_0
docker-compose up -d node_0

# 5. Enable additional security measures
# - Enable authentication if not already
# - Add rate limiting
# - Restrict network access

# 6. Notify security team and users
```

---

## 🎓 Training Resources

### For Operators

**Day 1: Basics**
- Understanding the architecture
- Deploying the system
- Basic health checks
- Reading logs

**Day 2: Operations**
- Monitoring and alerting
- Scaling up/down
- Backup and recovery
- Performance tuning

**Day 3: Troubleshooting**
- Common issues and solutions
- Debugging techniques
- Emergency procedures
- Postmortem analysis

### For Developers

**Module 1: Raft Consensus**
- Understanding Raft algorithm
- Leader election process
- Log replication
- Safety guarantees

**Module 2: Cache Coherence**
- MESI protocol states
- State transitions
- Invalidation protocol
- Performance implications

**Module 3: Distributed Systems**
- Consistent hashing
- Deadlock detection
- Fault tolerance
- CAP theorem

---

## 📞 Support

### Getting Help

**Community**:
- GitHub Issues: https://github.com/yourusername/distributed-sync-system/issues
- Slack Channel: #distributed-sync
- Stack Overflow: Tag `distributed-sync`

**Commercial Support**:
- Email: support@distributed-sync.io
- SLA-based support available
- Custom development

### Reporting Bugs

```markdown
**Bug Report Template**

**Environment**:
- Version: v1.0.0
- Deployment: Docker Compose / Kubernetes / Cloud
- OS: Ubuntu 22.04
- Node count: 3

**Description**:
Clear description of the issue

**Steps to Reproduce**:
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior**:
What should happen

**Actual Behavior**:
What actually happened

**Logs**:
```
Relevant log excerpts
```

**Additional Context**:
Any other relevant information
```

---

## 📅 Maintenance Schedule

### Daily Tasks
- [ ] Check health of all nodes
- [ ] Review error logs
- [ ] Monitor key metrics (latency, throughput)
- [ ] Verify backups completed

### Weekly Tasks
- [ ] Analyze performance trends
- [ ] Review capacity planning
- [ ] Update documentation
- [ ] Team sync on issues

### Monthly Tasks
- [ ] Security updates
- [ ] Dependency updates
- [ ] Performance testing
- [ ] Disaster recovery drill
- [ ] Log rotation and cleanup

### Quarterly Tasks
- [ ] Architecture review
- [ ] Capacity planning review
- [ ] Security audit
- [ ] Team training refresher

---

## 🔄 Upgrade Procedures

### Zero-Downtime Upgrade

```bash
# 1. Upgrade followers first
docker-compose stop node_1
docker-compose pull  # Get new image
docker-compose up -d node_1
sleep 30  # Wait for node to catch up

docker-compose stop node_2
docker-compose pull
docker-compose up -d node_2
sleep 30

# 2. Force leader election on node_0
# Current leader will step down
curl -X POST http://localhost:8080/admin/stepdown

# Wait for new leader election
sleep 10

# 3. Upgrade former leader
docker-compose stop node_0
docker-compose pull
docker-compose up -d node_0
sleep 30

# 4. Verify cluster health
curl http://localhost:8080/status
curl http://localhost:8081/status
curl http://localhost:8082/status

# 5. Run smoke tests
pytest tests/integration/ --smoke
```

### Rollback Procedure

```bash
# If upgrade fails, rollback immediately

# 1. Note current image tag
docker images | grep distributed-sync

# 2. Stop all nodes
docker-compose down

# 3. Restore previous version
# Edit docker-compose.yml:
# image: distributed-sync:v1.0.0  # Previous stable version

# 4. Start cluster
docker-compose up -d

# 5. Verify rollback successful
./scripts/health_check.sh
pytest tests/integration/ --smoke

# 6. Investigate upgrade failure
docker logs node_0 > upgrade-failure.log
```

---

## 📖 Glossary

**Term** | **Definition**
---------|---------------
**Raft** | Consensus algorithm for managing replicated log
**MESI** | Cache coherence protocol (Modified, Exclusive, Shared, Invalid)
**Consistent Hashing** | Technique for distributing data across nodes
**WAL** | Write-Ahead Log for durability
**Quorum** | Majority of nodes (N/2 + 1)
**Leader Election** | Process of selecting leader node in Raft
**Heartbeat** | Periodic message from leader to maintain authority
**Lock Acquisition** | Process of obtaining exclusive or shared lock
**Cache Coherence** | Maintaining consistency across distributed caches
**Deadlock** | Circular wait condition among transactions
**Failover** | Automatic switch to standby system
**RPC** | Remote Procedure Call for inter-node communication

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-01-28  
**Maintained By**: Distributed Systems Team

---

## Appendix A: Configuration Examples

### Example 1: 3-Node Lock Manager Cluster

```yaml
# docker-compose.3node.yml
version: '3.8'

services:
  node_0:
    image: distributed-sync:latest
    environment:
      - NODE_ID=node_0
      - NODE_HOST=node_0
      - NODE_PORT=8080
      - API_PORT=8080
      - PEER_NODES=node_1:node_1:8081,node_2:node_2:8082
    ports:
      - "8080:8080"
    networks:
      - sync_net

  node_1:
    image: distributed-sync:latest
    environment:
      - NODE_ID=node_1
      - NODE_HOST=node_1
      - NODE_PORT=8081
      - API_PORT=8081
      - PEER_NODES=node_0:node_0:8080,node_2:node_2:8082
    ports:
      - "8081:8081"
    networks:
      - sync_net

  node_2:
    image: distributed-sync:latest
    environment:
      - NODE_ID=node_2
      - NODE_HOST=node_2
      - NODE_PORT=8082
      - API_PORT=8082
      - PEER_NODES=node_0:node_0:8080,node_1:node_1:8081
    ports:
      - "8082:8082"
    networks:
      - sync_net

networks:
  sync_net:
    driver: bridge
```

### Example 2: Production Environment Variables

```bash
# .env.production
# Node Configuration
NODE_ID=prod-lock-0
NODE_HOST=10.0.1.10
NODE_PORT=8080
API_PORT=8080

# Cluster
PEER_NODES=prod-lock-1:10.0.1.11:8080,prod-lock-2:10.0.1.12:8080
NUM_NODES=3

# Performance
ELECTION_TIMEOUT_MS=200
HEARTBEAT_INTERVAL_MS=50
CACHE_CAPACITY=1000

# Logging
LOG_LEVEL=INFO
LOG_FILE=/var/log/distributed-sync/node.log

# Security
ENABLE_AUTH=true
JWT_SECRET=<your-secret-here>
ENABLE_TLS=true
TLS_CERT=/etc/certs/server.crt
TLS_KEY=/etc/certs/server.key

# Monitoring
ENABLE_METRICS=true
METRICS_PORT=9090
```

---

## Appendix B: Performance Tuning Parameters

### Raft Tuning

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `election_timeout` | 150-300ms | 100-500ms | Timeout before starting election |
| `heartbeat_interval` | 50ms | 30-100ms | Leader heartbeat frequency |
| `max_batch_size` | 50 | 10-200 | Max entries per AppendEntries |
| `snapshot_threshold` | 1000 | 100-10000 | Entries before snapshot |

### Cache Tuning

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `capacity` | 100 | 50-10000 | Max cache entries |
| `eviction_policy` | LRU | LRU/LFU/FIFO | Eviction strategy |
| `writeback_delay` | 10ms | 5-100ms | Delay before writeback |
| `invalidation_timeout` | 1000ms | 100-5000ms | Timeout for invalidations |

### Queue Tuning

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `virtual_nodes` | 150 | 50-500 | Virtual nodes per physical node |
| `buffer_size` | 1MB | 512KB-10MB | WAL buffer size |
| `batch_size` | 50 | 10-500 | Batch operations |
| `visibility_timeout` | 30s | 10s-300s | In-flight message timeout |

---

## Appendix C: API Examples

### cURL Examples

```bash
# Acquire lock
curl -X POST http://localhost:8080/locks/acquire \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "database:users",
    "client_id": "service_a",
    "lock_type": "exclusive",
    "timeout_seconds": 60
  }'

# Release lock
curl -X POST http://localhost:8080/locks/release \
  -H "Content-Type: application/json" \
  -d '{
    "resource": "database:users",
    "client_id": "service_a"
  }'

# Enqueue message
curl -X POST http://localhost:9000/queue/enqueue \
  -H "Content-Type: application/json" \
  -d '{
    "queue_name": "orders",
    "message": {"order_id": 123, "customer": "John"}
  }'

# Cache write
curl -X POST http://localhost:7000/cache \
  -H "Content-Type: application/json" \
  -d '{
    "key": "user:123",
    "value": {"name": "John", "age": 30}
  }'

# Cache read
curl http://localhost:7000/cache/user:123
```

### Python Client Examples

```python
import httpx
import asyncio

async def lock_example():
    async with httpx.AsyncClient() as client:
        # Acquire lock
        response = await client.post(
            "http://localhost:8080/locks/acquire",
            json={
                "resource": "database:users",
                "client_id": "my_service",
                "lock_type": "exclusive"
            }
        )
        result = response.json()
        
        if result["success"]:
            try:
                # Do work while holding lock
                await do_critical_work()
            finally:
                # Always release lock
                await client.post(
                    "http://localhost:8080/locks/release",
                    json={
                        "resource": "database:users",
                        "client_id": "my_service"
                    }
                )

asyncio.run(lock_example())
```

---

**End of Deployment Guide**
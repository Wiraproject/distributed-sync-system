# Deployment Guide

Panduan deployment Distributed Sync System ke production.

## Prerequisites

- Docker & Docker Compose
- Kubernetes (optional)
- Redis cluster
- Load balancer
- Monitoring stack (Prometheus, Grafana)

## Docker Deployment

### 1. Build Images

```bash
# Build node image
docker build -f docker/Dockerfile -t distributed-sync-node:1.0.0 .

# Tag for registry
docker tag distributed-sync-node:1.0.0 registry.example.com/distributed-sync-node:1.0.0

# Push to registry
docker push registry.example.com/distributed-sync-node:1.0.0
```

### 2. Deploy with Docker Compose

```bash
# Production deployment
docker-compose -f docker/docker-compose.prod.yml up -d

# Scale nodes
docker-compose -f docker/docker-compose.prod.yml up -d --scale node=5

# View logs
docker-compose -f docker/docker-compose.prod.yml logs -f
```

### 3. Configuration

**docker-compose.prod.yml**:
```yaml

services:
  node:
    image: registry.example.com/distributed-sync-node:1.0.0
    environment:
      - LOG_LEVEL=INFO
      - CACHE_SIZE=1000
      - REDIS_HOST=redis-cluster
    deploy:
      replicas: 5
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
```

## Kubernetes Deployment

### 1. Create Namespace

```bash
kubectl create namespace distributed-sync
```

### 2. Deploy Redis

```bash
# Using Helm
helm install redis bitnami/redis-cluster \
  --namespace distributed-sync \
  --set cluster.nodes=6 \
  --set cluster.replicas=1
```

### 3. Deploy Application

**deployment.yaml**:
```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: distributed-sync-node
  namespace: distributed-sync
spec:
  serviceName: distributed-sync
  replicas: 5
  selector:
    matchLabels:
      app: distributed-sync-node
  template:
    metadata:
      labels:
        app: distributed-sync-node
    spec:
      containers:
      - name: node
        image: registry.example.com/distributed-sync-node:1.0.0
        ports:
        - containerPort: 8000
          name: lock
        - containerPort: 8100
          name: queue
        - containerPort: 8200
          name: cache
        env:
        - name: NODE_ID
          valueFrom:
            fieldRef:
              fieldPath: metadata.name
        - name: REDIS_HOST
          value: "redis-cluster"
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "1Gi"
            cpu: "1"
          limits:
            memory: "2Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
```

```bash
kubectl apply -f deployment.yaml
```

### 4. Create Service

**service.yaml**:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: distributed-sync
  namespace: distributed-sync
spec:
  type: LoadBalancer
  ports:
  - port: 8000
    targetPort: 8000
    name: lock
  - port: 8100
    targetPort: 8100
    name: queue
  - port: 8200
    targetPort: 8200
    name: cache
  selector:
    app: distributed-sync-node
```

```bash
kubectl apply -f service.yaml
```

## Monitoring

### Prometheus Metrics

Add to node implementation:
```python
from prometheus_client import Counter, Histogram, Gauge

lock_requests = Counter('lock_requests_total', 'Total lock requests')
lock_latency = Histogram('lock_latency_seconds', 'Lock acquisition latency')
active_locks = Gauge('active_locks', 'Number of active locks')
```

### Grafana Dashboard

Import dashboard with metrics:
- Lock throughput
- Cache hit rate
- Queue depth
- Node health
- Network latency

## Backup & Recovery

### Redis Backup

```bash
# Manual backup
redis-cli --rmi 0 SAVE

# Automated backup (cron)
0 */6 * * * redis-cli BGSAVE
```

### Queue Persistence

Persistent logs automatically saved to:
```
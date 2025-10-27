# System Architecture Documentation

## Table of Contents
1. [Overview](#overview)
2. [Component Architecture](#component-architecture)
3. [Communication Protocols](#communication-protocols)
4. [Data Flow](#data-flow)
5. [Failure Handling](#failure-handling)
6. [Deployment Architecture](#deployment-architecture)

## Overview

The Distributed Synchronization System is designed with three core components:

```
  ┌───────────────────────────────────────────────────┐
  │                  Application Layer                │
  │  ┌─────────────┐  ┌────────────┐  ┌────────────┐  │
  │  │   Clients   │  │  Services  │  │    APIs    │  │
  │  └─────────────┘  └────────────┘  └────────────┘  │
  └────────────────────────┬──────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│              Distributed Sync System Layer             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ Lock Manager │  │    Queue     │  │    Cache     │  │
│  │   (Raft)     │  │  (Cons Hash) │  │    (MESI)    │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│                  Infrastructure Layer                  │
│    ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│    │   Network   │  │   Storage   │  │  Monitoring │   │
│    └─────────────┘  └─────────────┘  └─────────────┘   │
└────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Distributed Lock Manager

**Purpose:** Provide distributed mutual exclusion using Raft consensus

**Key Components:**
- Raft State Machine
- Log Replication
- Leader Election
- Deadlock Detector

**Architecture Diagram:**
```
┌───────────────────────────────────────┐
│      Distributed Lock Manager         │
├───────────────────────────────────────┤
│  ┌─────────────────────────────────┐  │
│  │      Raft Consensus Layer       │  │
│  │   ┌──────┐ ┌──────┐ ┌──────┐    │  │
│  │   │Leader│ │Follow│ │Follow│    │  │
│  │   └──────┘ └──────┘ └──────┘    │  │
│  └─────────────────────────────────┘  │
│  ┌─────────────────────────────────┐  │
│  │       Lock Management           │  │
│  │  • Shared Locks                 │  │
│  │  • Exclusive Locks              │  │
│  │  • Wait Queue (FIFO)            │  │
│  └─────────────────────────────────┘  │
│  ┌─────────────────────────────────┐  │
│  │    Deadlock Detection           │  │
│  │  • Wait-for Graph               │  │
│  │  • Cycle Detection              │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

### 2. Distributed Queue

**Purpose:** Scalable message queue with consistent hashing

**Key Components:**
- Consistent Hash Ring
- Message Router
- Persistence Layer
- Recovery Manager

**Architecture Diagram:**
```
┌───────────────────────────────────────┐
│       Distributed Queue System        │
├───────────────────────────────────────┤
│  ┌─────────────────────────────────┐  │
│  │   Consistent Hash Ring (150vn)  │  │
│  │    ┌──────────────────────┐     │  │
│  │    │  Hash(key) → Node    │     │  │
│  │    └──────────────────────┘     │  │
│  └─────────────────────────────────┘  │
│  ┌─────────────────────────────────┐  │
│  │      Queue Management           │  │
│  │   ┌─────┐  ┌─────┐  ┌─────┐     │  │
│  │   │ Q1  │  │ Q2  │  │ Q3  │     │  │
│  │   │Node0│  │Node1│  │Node2│     │  │
│  │   └─────┘  └─────┘  └─────┘     │  │
│  └─────────────────────────────────┘  │
│  ┌─────────────────────────────────┐  │
│  │    Persistence (WAL)            │  │
│  │  • Write-Ahead Log              │  │
│  │  • Periodic Snapshots           │  │
│  │  • Auto Recovery                │  │
│  └─────────────────────────────────┘  │
└───────────────────────────────────────┘
```

### 3. Distributed Cache

**Purpose:** High-performance cache with MESI coherence

**Key Components:**
- Cache Lines with States
- Coherence Protocol
- LRU Eviction
- Metrics Collector

**State Machine:**
```
           ┌─────────┐
     ┌────►│Invalid│◄────┐
     │     └────┬────┘   │
     │          │Read    │Invalidate
     │          │        │
     │     ┌────▼────┐   │
Invalidate │ Shared  │───┘
     │     └────┬────┘
     │          │Write
     │     ┌────▼────┐
     └─────│Modified │
           └─────────┘
```

## Communication Protocols

### Message Format

```json
{
  "msg_id": "node_0-12345",
  "msg_type": "lock_acquire",
  "sender_id": "node_0",
  "receiver_id": "node_1",
  "payload": {
    "resource": "db_table",
    "lock_type": "EXCLUSIVE",
    "client_id": "client_abc"
  },
  "timestamp": "2025-10-25T10:30:00Z"
}
```

### Protocol Specifications

**1. Raft Messages:**
- `request_vote`: Election request
- `vote_response`: Vote reply
- `append_entries`: Log replication/heartbeat
- `append_response`: Replication ACK

**2. Lock Messages:**
- `lock_acquire`: Request lock
- `lock_release`: Release lock
- `lock_status`: Query lock state

**3. Queue Messages:**
- `enqueue`: Add message
- `dequeue`: Remove message
- `redistribute`: Rebalance on node change

**4. Cache Messages:**
- `cache_read`: Read notification
- `cache_write`: Write notification
- `cache_invalidate`: Invalidate command

## Data Flow

### Lock Acquisition Flow

```sequence
Client          Leader          Follower1       Follower2
  │                │                │               │
  ├─Lock Request──►│                │               │
  │                ├─Append Entry──►│               │
  │                ├─Append Entry──────────────────►│
  │                │◄───────ACK─────┤               │
  │                │◄───────ACK─────────────────────┤
  │                ├─Commit─────────►│              │
  │                ├─Commit────────────────────────►│
  │◄──Lock Grant───┤                │               │
```

### Queue Message Flow

```sequence
Producer        Node0          Node1(target)    Consumer
  │               │                │               │
  ├─Enqueue──────►│                │               │
  │               ├─Hash(queue)───►│               │
  │               │                ├─Persist──────►│
  │               │◄─────ACK───────┤               │
  │◄────ACK───────┤                │               │
  │               │                │◄──Dequeue─────┤
  │               │                ├─Return Msg───►│
```
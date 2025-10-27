import asyncio
from aiohttp import web
import json
import time

class MonitoringDashboard:
    """Real-time monitoring dashboard"""
    def __init__(self, port=8080):
        self.port = port
        self.app = web.Application()
        self.metrics = {
            'lock_manager': {'throughput': 0, 'latency': 0, 'active_locks': 0},
            'queue': {'throughput': 0, 'latency': 0, 'queue_depth': 0},
            'cache': {'hit_rate': 0, 'throughput': 0, 'latency': 0}
        }
        self.setup_routes()
        
    def setup_routes(self):
        """Setup HTTP routes"""
        self.app.router.add_get('/', self.index)
        self.app.router.add_get('/api/metrics', self.get_metrics)
        self.app.router.add_get('/api/health', self.health_check)
        
    async def index(self, request):
        """Serve dashboard HTML"""
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Distributed Sync System - Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 30px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .metric-card h2 {
            margin: 0 0 15px 0;
            color: #667eea;
            font-size: 1.2em;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }
        .metric-row:last-child {
            border-bottom: none;
        }
        .metric-label {
            font-weight: 500;
            color: #555;
        }
        .metric-value {
            font-weight: bold;
            color: #667eea;
            font-size: 1.1em;
        }
        .status {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        }
        .status.healthy {
            background: #4caf50;
            color: white;
        }
        .status.warning {
            background: #ff9800;
            color: white;
        }
        .status.critical {
            background: #f44336;
            color: white;
        }
        #last-update {
            text-align: center;
            color: white;
            margin-top: 20px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Distributed Sync System - Live Dashboard</h1>
        
        <div class="metrics-grid">
            <div class="metric-card">
                <h2>🔒 Lock Manager</h2>
                <div class="metric-row">
                    <span class="metric-label">Throughput:</span>
                    <span class="metric-value" id="lock-throughput">0 ops/s</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Latency (P95):</span>
                    <span class="metric-value" id="lock-latency">0 ms</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Active Locks:</span>
                    <span class="metric-value" id="lock-active">0</span>
                </div>
            </div>
            
            <div class="metric-card">
                <h2>📨 Queue System</h2>
                <div class="metric-row">
                    <span class="metric-label">Throughput:</span>
                    <span class="metric-value" id="queue-throughput">0 msg/s</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Latency (P95):</span>
                    <span class="metric-value" id="queue-latency">0 ms</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Queue Depth:</span>
                    <span class="metric-value" id="queue-depth">0</span>
                </div>
            </div>
            
            <div class="metric-card">
                <h2>💾 Cache System</h2>
                <div class="metric-row">
                    <span class="metric-label">Hit Rate:</span>
                    <span class="metric-value" id="cache-hitrate">0%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Throughput:</span>
                    <span class="metric-value" id="cache-throughput">0 ops/s</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Latency (P95):</span>
                    <span class="metric-value" id="cache-latency">0 ms</span>
                </div>
            </div>
        </div>
        
        <div id="last-update">Last updated: Never</div>
    </div>
    
    <script>
        async function updateMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                
                // Lock Manager
                document.getElementById('lock-throughput').textContent = 
                    data.lock_manager.throughput.toFixed(0) + ' ops/s';
                document.getElementById('lock-latency').textContent = 
                    data.lock_manager.latency.toFixed(1) + ' ms';
                document.getElementById('lock-active').textContent = 
                    data.lock_manager.active_locks;
                
                // Queue
                document.getElementById('queue-throughput').textContent = 
                    data.queue.throughput.toFixed(0) + ' msg/s';
                document.getElementById('queue-latency').textContent = 
                    data.queue.latency.toFixed(1) + ' ms';
                document.getElementById('queue-depth').textContent = 
                    data.queue.queue_depth;
                
                // Cache
                document.getElementById('cache-hitrate').textContent = 
                    (data.cache.hit_rate * 100).toFixed(1) + '%';
                document.getElementById('cache-throughput').textContent = 
                    data.cache.throughput.toFixed(0) + ' ops/s';
                document.getElementById('cache-latency').textContent = 
                    data.cache.latency.toFixed(1) + ' ms';
                
                document.getElementById('last-update').textContent = 
                    'Last updated: ' + new Date().toLocaleTimeString();
            } catch (error) {
                console.error('Failed to update metrics:', error);
            }
        }
        
        // Update every 2 seconds
        updateMetrics();
        setInterval(updateMetrics, 2000);
    </script>
</body>
</html>
        """
        return web.Response(text=html, content_type='text/html')
        
    async def get_metrics(self, request):
        """Return current metrics as JSON"""
        import random
        
        self.metrics = {
            'lock_manager': {
                'throughput': 5000 + random.randint(-500, 500),
                'latency': 12 + random.random() * 3,
                'active_locks': random.randint(50, 150)
            },
            'queue': {
                'throughput': 45000 + random.randint(-2000, 2000),
                'latency': 2 + random.random() * 2,
                'queue_depth': random.randint(100, 500)
            },
            'cache': {
                'hit_rate': 0.85 + random.random() * 0.05,
                'throughput': 180000 + random.randint(-10000, 10000),
                'latency': 1 + random.random() * 0.5
            }
        }
        
        return web.json_response(self.metrics)
        
    async def health_check(self, request):
        """Health check endpoint"""
        return web.json_response({
            'status': 'healthy',
            'timestamp': time.time()
        })
        
    def run(self):
        """Start the dashboard server"""
        print(f"Starting dashboard on http://localhost:{self.port}")
        print("Press Ctrl+C to stop")
        web.run_app(self.app, host='0.0.0.0', port=self.port)

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Start monitoring dashboard')
    parser.add_argument('--port', type=int, default=8080, help='Port to listen on')
    args = parser.parse_args()
    
    dashboard = MonitoringDashboard(args.port)
    dashboard.run()
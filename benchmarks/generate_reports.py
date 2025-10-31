import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import numpy as np
import json
import os
from datetime import datetime

def load_benchmark_results(filename="benchmarks/results/benchmark_results.json"):
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️  {filename} not found. Using sample data.")
        return None

class ReportGenerator:
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
    def generate_latency_distribution(self, data, title, filename):
        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Extract available percentiles from data
        percentiles = []
        values = []
        
        if 'min' in data:
            percentiles.append('Min')
            values.append(data['min'])
        if 'median' in data:
            percentiles.append('P50')
            values.append(data['median'])
        if 'p95' in data:
            percentiles.append('P95')
            values.append(data['p95'])
        if 'p99' in data:
            percentiles.append('P99')
            values.append(data['p99'])
        if 'max' in data:
            percentiles.append('Max')
            values.append(data['max'])
        
        bars = ax.barh(range(len(percentiles)), values, color='steelblue')
        ax.set_yticks(range(len(percentiles)))
        ax.set_yticklabels(percentiles)
        ax.set_xlabel('Latency (ms)')
        ax.set_title(title)
        ax.grid(axis='x', alpha=0.3)
        
        for i, (bar, val) in enumerate(zip(bars, values)):
            ax.text(val, i, f' {val:.2f}ms', va='center')
        
        # Add mean line if available
        if 'mean' in data:
            ax.axvline(x=data['mean'], color='red', linestyle='--', 
                      alpha=0.7, label=f"Mean: {data['mean']:.2f}ms")
            ax.legend()
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, filename))
        plt.close()
        print(f"  ✓ Generated {filename}")
        
    def generate_throughput_comparison(self, data, filename):
        fig, ax = plt.subplots(figsize=(10, 6))
        
        components = list(data.keys())
        throughputs = list(data.values())
        
        bars = ax.bar(components, throughputs, color=['steelblue', 'coral', 'lightgreen'])
        ax.set_ylabel('Throughput (ops/sec)')
        ax.set_title('Component Throughput Comparison')
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels on bars
        for bar, val in zip(bars, throughputs):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{val:.2f}',
                   ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, filename))
        plt.close()
        print(f"  ✓ Generated {filename}")
        
    def generate_scaling_efficiency(self, data, filename):
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        nodes = [d['nodes'] for d in data]
        throughput = [d['throughput'] for d in data]
        efficiency = [d['efficiency'] for d in data]
        
        # Throughput chart
        ax1.plot(nodes, throughput, 'o-', linewidth=2, markersize=8, 
                color='steelblue', label='Actual Throughput')
        
        # Calculate ideal linear scaling
        if throughput:
            ideal = [throughput[0] * n for n in nodes]
            ax1.plot(nodes, ideal, '--', linewidth=2, 
                    color='orange', label='Ideal Linear Scaling')
        
        ax1.set_xlabel('Number of Nodes')
        ax1.set_ylabel('Throughput (ops/sec)')
        ax1.set_title('Throughput vs Number of Nodes')
        ax1.legend()
        ax1.grid(alpha=0.3)
        
        # Add value labels
        for n, t in zip(nodes, throughput):
            ax1.annotate(f'{t:.1f}', 
                        xy=(n, t), 
                        xytext=(0, 10),
                        textcoords='offset points',
                        ha='center')
        
        # Efficiency chart
        ax2.plot(nodes, efficiency, 'o-', linewidth=2, markersize=8, 
                color='green')
        ax2.set_xlabel('Number of Nodes')
        ax2.set_ylabel('Efficiency (ops/sec per node)')
        ax2.set_title('Scaling Efficiency')
        ax2.grid(alpha=0.3)
        
        # Add value labels
        for n, e in zip(nodes, efficiency):
            ax2.annotate(f'{e:.1f}', 
                        xy=(n, e), 
                        xytext=(0, 10),
                        textcoords='offset points',
                        ha='center')
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, filename))
        plt.close()
        print(f"  ✓ Generated {filename}")
        
    def generate_queue_performance(self, data, filename):
        fig, ax = plt.subplots(figsize=(10, 6))
        
        metrics = ['Enqueued', 'Dequeued', 'Throughput\n(ops/sec)']
        values = [
            data['enqueued'],
            data['dequeued'],
            data['ops_per_sec']
        ]
        
        colors = ['steelblue', 'coral', 'lightgreen']
        bars = ax.bar(metrics, values, color=colors)
        
        ax.set_ylabel('Count / Rate')
        ax.set_title(f'Queue Performance (Duration: {data["elapsed"]:.1f}s)')
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for bar, val in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{val:.1f}',
                   ha='center', va='bottom')
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, filename))
        plt.close()
        print(f"  ✓ Generated {filename}")
        
    def generate_operations_summary(self, data, filename):
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(14, 10))
        
        # Lock Manager
        lock_data = data['lock_manager']
        ax1.bar(['Operations', 'Errors'], 
               [lock_data['throughput']['operations'], 
                lock_data['throughput']['errors']],
               color=['steelblue', 'red'])
        ax1.set_title('Lock Manager - Operations')
        ax1.set_ylabel('Count')
        ax1.grid(axis='y', alpha=0.3)
        for i, v in enumerate([lock_data['throughput']['operations'], 
                               lock_data['throughput']['errors']]):
            ax1.text(i, v, str(v), ha='center', va='bottom')
        
        # Lock Manager Throughput
        ax2.text(0.5, 0.5, 
                f"{lock_data['throughput']['ops_per_sec']:.2f}\nops/sec",
                ha='center', va='center', fontsize=24, 
                transform=ax2.transAxes)
        ax2.set_title('Lock Manager - Throughput')
        ax2.axis('off')
        
        # Queue Performance
        queue_data = data['queue']['throughput']
        ax3.bar(['Enqueued', 'Dequeued'], 
               [queue_data['enqueued'], queue_data['dequeued']],
               color=['coral', 'lightgreen'])
        ax3.set_title('Queue - Operations')
        ax3.set_ylabel('Count')
        ax3.grid(axis='y', alpha=0.3)
        for i, v in enumerate([queue_data['enqueued'], queue_data['dequeued']]):
            ax3.text(i, v, str(v), ha='center', va='bottom')
        
        # Queue Throughput
        ax4.text(0.5, 0.5, 
                f"{queue_data['ops_per_sec']:.2f}\nops/sec",
                ha='center', va='center', fontsize=24, 
                transform=ax4.transAxes)
        ax4.set_title('Queue - Throughput')
        ax4.axis('off')
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, filename))
        plt.close()
        print(f"  ✓ Generated {filename}")
        
    def generate_all_reports(self):
        print("Generating performance reports...")
        
        # Load real benchmark data
        data = load_benchmark_results()
        
        if not data:
            print("❌ No benchmark data found. Please run benchmarks first.")
            return
        
        print("✓ Using real benchmark data")
        print(f"  Timestamp: {data['timestamp']}")
        
        # 1. Lock Manager Latency Distribution
        if "lock_manager" in data and "latency" in data["lock_manager"]:
            self.generate_latency_distribution(
                data["lock_manager"]["latency"],
                "Lock Manager Latency Distribution",
                "lock_latency.png"
            )
        
        # 2. Throughput Comparison
        throughput_comparison = {}
        if "lock_manager" in data:
            throughput_comparison['Lock Manager'] = data['lock_manager']['throughput']['ops_per_sec']
        if "queue" in data:
            throughput_comparison['Queue'] = data['queue']['throughput']['ops_per_sec']
        if "cache" in data:
            throughput_comparison['Cache'] = data['cache']['performance']['ops_per_sec']
        
        if throughput_comparison:
            self.generate_throughput_comparison(
                throughput_comparison, 
                "throughput_comparison.png"
            )
        
        # 3. Scaling Efficiency
        if "scalability" in data and data["scalability"]:
            self.generate_scaling_efficiency(
                data["scalability"],
                "scaling_efficiency.png"
            )
        
        # 4. Queue Performance
        if "queue" in data and "throughput" in data["queue"]:
            self.generate_queue_performance(
                data["queue"]["throughput"],
                "queue_performance.png"
            )
        
        # 5. Operations Summary
        self.generate_operations_summary(
            data,
            "operations_summary.png"
        )
        
        print(f"\n✅ All reports generated successfully in '{self.output_dir}/' directory")
        print(f"   Generated {len([f for f in os.listdir(self.output_dir) if f.endswith('.png')])} PNG files")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate performance reports')
    parser.add_argument('--output', default='reports', help='Output directory')
    args = parser.parse_args()
    
    generator = ReportGenerator(args.output)
    generator.generate_all_reports()
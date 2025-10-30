from flask import Flask, request, jsonify, render_template_string
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
from collections import deque
import threading

app = Flask(__name__)

# Store metrics in memory (last 100 entries per client)
metrics_store = {}
max_entries = 100
lock = threading.Lock()

# HTML template with embedded table and charts
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>System Metrics Dashboard</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .api-info {
            background-color: #f0f9ff;
            border: 2px solid #0ea5e9;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 30px;
        }
        .api-info h2 {
            margin-top: 0;
            color: #0369a1;
        }
        .api-info code {
            background-color: #e0f2fe;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
        }
        .api-info pre {
            background-color: #1e293b;
            color: #e2e8f0;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-card h3 {
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }
        .stat-card .value {
            font-size: 32px;
            font-weight: bold;
            margin: 0;
        }
        .client-section {
            margin-top: 30px;
            padding: 20px;
            background-color: #fafafa;
            border-radius: 8px;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th {
            background-color: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }
        td {
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }
        tr:hover {
            background-color: #f5f5f5;
        }
        .status-connected {
            color: #22c55e;
            font-weight: bold;
        }
        .status-disconnected {
            color: #ef4444;
            font-weight: bold;
        }
        .charts {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .chart-container {
            text-align: center;
        }
        .chart-container img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .info {
            text-align: center;
            color: #666;
            margin-top: 20px;
            font-size: 14px;
        }
        .no-data {
            text-align: center;
            padding: 60px 20px;
            color: #666;
        }
        .no-data h2 {
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🖥️ System Metrics Dashboard</h1>
        
        <div class="api-info">
            <h2>📡 How to Send Metrics</h2>
            <p>Send metrics to this dashboard via POST request:</p>
            <p><strong>Endpoint:</strong> <code>POST {{ base_url }}/api/metrics</code></p>
            <p><strong>Example Python Code:</strong></p>
            <pre>import requests
import psutil
from datetime import datetime

def send_metrics():
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'cpu_percent': psutil.cpu_percent(interval=1),
        'ram': {
            'used_gb': psutil.virtual_memory().used / (1024**3),
            'total_gb': psutil.virtual_memory().total / (1024**3),
            'percent': psutil.virtual_memory().percent
        },
        'client_name': 'My Computer'  # Optional identifier
    }
    
    response = requests.post(
        '{{ base_url }}/api/metrics',
        json=metrics
    )
    print(response.json())

# Run every 5 seconds
import time
while True:
    send_metrics()
    time.sleep(5)</pre>
        </div>

        {% if metrics %}
        {% if latest_metrics %}
        <div class="stats">
            <div class="stat-card">
                <h3>Active Clients</h3>
                <p class="value">{{ total_clients }}</p>
            </div>
            <div class="stat-card">
                <h3>Total Metrics</h3>
                <p class="value">{{ total_metrics }}</p>
            </div>
            <div class="stat-card">
                <h3>Latest CPU</h3>
                <p class="value">{{ "%.1f"|format(latest_metrics.cpu_percent) if latest_metrics.cpu_percent else "N/A" }}%</p>
            </div>
            <div class="stat-card">
                <h3>Latest RAM</h3>
                <p class="value">{{ "%.1f"|format(latest_metrics.ram.percent) if latest_metrics.ram else "N/A" }}%</p>
            </div>
        </div>
        {% endif %}

        <h2>Recent Metrics from All Clients</h2>
        <table>
            <thead>
                <tr>
                    <th>Client</th>
                    <th>Timestamp</th>
                    <th>CPU %</th>
                    <th>GPU %</th>
                    <th>RAM Used (GB)</th>
                    <th>RAM %</th>
                    <th>Ping (ms)</th>
                    <th>Internet</th>
                </tr>
            </thead>
            <tbody>
                {% for metric in metrics %}
                <tr>
                    <td><strong>{{ metric.client_name or metric.client_id }}</strong></td>
                    <td>{{ metric.timestamp }}</td>
                    <td>{{ "%.1f"|format(metric.cpu_percent) if metric.cpu_percent else "N/A" }}%</td>
                    <td>{{ "%.1f"|format(metric.gpu_percent) if metric.gpu_percent else "N/A" }}</td>
                    <td>
                        {% if metric.ram %}
                        {{ "%.2f"|format(metric.ram.used_gb) }} / {{ "%.2f"|format(metric.ram.total_gb) }}
                        {% else %}
                        N/A
                        {% endif %}
                    </td>
                    <td>{{ "%.1f"|format(metric.ram.percent) if metric.ram else "N/A" }}%</td>
                    <td>{{ "%.1f"|format(metric.ping_ms) if metric.ping_ms else "N/A" }}</td>
                    <td class="{% if metric.internet_connected %}status-connected{% else %}status-disconnected{% endif %}">
                        {% if metric.internet_connected is not none %}
                            {{ "Connected" if metric.internet_connected else "Disconnected" }}
                        {% else %}
                            N/A
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        {% if charts %}
        <h2>Performance Charts</h2>
        <div class="charts">
            {% for chart_name, chart_data in charts.items() %}
            <div class="chart-container">
                <h3>{{ chart_name }}</h3>
                <img src="data:image/png;base64,{{ chart_data }}" alt="{{ chart_name }}">
            </div>
            {% endfor %}
        </div>
        {% endif %}

        <div class="info">
            <p>Dashboard auto-refreshes every 5 seconds | Total clients: {{ total_clients }}</p>
        </div>

        {% else %}
        <div class="no-data">
            <h2>📊 No Metrics Yet</h2>
            <p>Waiting for clients to send data...</p>
            <p>Use the API endpoint above to start sending metrics.</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

# ==================== HELPER FUNCTIONS ====================

def generate_charts(metrics_list):
    """Generate matplotlib charts from metrics data."""
    if not metrics_list or len(metrics_list) < 2:
        return {}
    
    charts = {}
    
    # Extract data (handle missing values)
    timestamps = [m.get('timestamp', '')[-8:] for m in metrics_list]
    cpu_data = [m.get('cpu_percent', 0) for m in metrics_list if m.get('cpu_percent') is not None]
    ram_data = [m.get('ram', {}).get('percent', 0) for m in metrics_list if m.get('ram', {}).get('percent') is not None]
    
    # CPU Chart
    if cpu_data and len(cpu_data) > 1:
        cpu_timestamps = [m.get('timestamp', '')[-8:] for m in metrics_list if m.get('cpu_percent') is not None]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(cpu_timestamps, cpu_data, marker='o', linewidth=2, markersize=4, color='#667eea')
        ax.set_xlabel('Time')
        ax.set_ylabel('CPU Usage (%)')
        ax.set_title('CPU Usage Over Time')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        charts['CPU Usage'] = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
    
    # RAM Chart
    if ram_data and len(ram_data) > 1:
        ram_timestamps = [m.get('timestamp', '')[-8:] for m in metrics_list if m.get('ram', {}).get('percent') is not None]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(ram_timestamps, ram_data, marker='o', linewidth=2, markersize=4, color='#764ba2')
        ax.set_xlabel('Time')
        ax.set_ylabel('RAM Usage (%)')
        ax.set_title('RAM Usage Over Time')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        charts['RAM Usage'] = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
    
    # GPU Chart (if available)
    gpu_data = [m.get('gpu_percent') for m in metrics_list if m.get('gpu_percent') is not None]
    if gpu_data and len(gpu_data) > 1:
        gpu_timestamps = [m.get('timestamp', '')[-8:] for m in metrics_list if m.get('gpu_percent') is not None]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(gpu_timestamps, gpu_data, marker='o', linewidth=2, markersize=4, color='#22c55e')
        ax.set_xlabel('Time')
        ax.set_ylabel('GPU Usage (%)')
        ax.set_title('GPU Usage Over Time')
        ax.grid(True, alpha=0.3)
        ax.set_ylim(0, 100)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        charts['GPU Usage'] = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
    
    # Ping Chart (if available)
    ping_data = [m.get('ping_ms') for m in metrics_list if m.get('ping_ms') is not None]
    if ping_data and len(ping_data) > 1:
        ping_timestamps = [m.get('timestamp', '')[-8:] for m in metrics_list if m.get('ping_ms') is not None]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot(ping_timestamps, ping_data, marker='o', linewidth=2, markersize=4, color='#f59e0b')
        ax.set_xlabel('Time')
        ax.set_ylabel('Ping (ms)')
        ax.set_title('Network Latency Over Time')
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)
        charts['Network Latency'] = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()
    
    return charts

# ==================== FLASK ROUTES ====================

@app.route('/')
def dashboard():
    """Display the metrics dashboard."""
    with lock:
        # Get all metrics from all clients
        all_metrics = []
        for client_id, client_metrics in metrics_store.items():
            for metric in client_metrics:
                metric_copy = metric.copy()
                if 'client_id' not in metric_copy:
                    metric_copy['client_id'] = client_id
                all_metrics.append(metric_copy)
        
        # Sort by timestamp (most recent first)
        all_metrics.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Get latest metrics for stat cards
        latest = all_metrics[0] if all_metrics else None
        
        # Generate charts from recent metrics (last 20)
        recent_metrics = list(reversed(all_metrics[:20]))
        charts = generate_charts(recent_metrics)
        
        # Get base URL for API instructions
        base_url = request.url_root.rstrip('/')
        
        return render_template_string(
            HTML_TEMPLATE,
            metrics=all_metrics[:50],
            latest_metrics=latest,
            charts=charts,
            total_clients=len(metrics_store),
            total_metrics=len(all_metrics),
            base_url=base_url
        )

@app.route('/api/metrics', methods=['POST'])
def receive_metrics():
    """API endpoint to receive metrics from external monitoring clients."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Add server-side timestamp
        data['received_at'] = datetime.now().isoformat()
        
        # Get client identifier (IP or custom name)
        client_id = data.get('client_name') or data.get('client_id') or request.remote_addr
        
        with lock:
            if client_id not in metrics_store:
                metrics_store[client_id] = deque(maxlen=max_entries)
            metrics_store[client_id].append(data)
        
        return jsonify({
            'status': 'success',
            'message': 'Metrics received',
            'client_id': client_id,
            'stored_count': len(metrics_store[client_id])
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """API endpoint to retrieve stored metrics."""
    with lock:
        all_metrics = []
        for client_id, client_metrics in metrics_store.items():
            for metric in client_metrics:
                metric_copy = metric.copy()
                if 'client_id' not in metric_copy:
                    metric_copy['client_id'] = client_id
                all_metrics.append(metric_copy)
        
        return jsonify({
            'total_entries': len(all_metrics),
            'total_clients': len(metrics_store),
            'metrics': all_metrics
        }), 200

@app.route('/api/clients', methods=['GET'])
def get_clients():
    """API endpoint to get list of connected clients."""
    with lock:
        clients = []
        for client_id, client_metrics in metrics_store.items():
            if client_metrics:
                latest = list(client_metrics)[-1]
                clients.append({
                    'client_id': client_id,
                    'client_name': latest.get('client_name', client_id),
                    'last_seen': latest.get('timestamp'),
                    'metric_count': len(client_metrics)
                })
        
        return jsonify({
            'total_clients': len(clients),
            'clients': clients
        }), 200

@app.route('/health')
def health():
    """Health check endpoint for Azure."""
    return jsonify({
        'status': 'healthy',
        'clients': len(metrics_store),
        'timestamp': datetime.now().isoformat()
    }), 200

# ==================== MAIN ====================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 Metrics Dashboard Server Starting...")
    print("="*60)
    print("📊 Dashboard: http://localhost:8000")
    print("📡 API Endpoint: http://localhost:8000/api/metrics")
    print("💚 Health Check: http://localhost:8000/health")
    print("="*60 + "\n")
    
    # For local development
    app.run(host='0.0.0.0', port=8000, debug=False)
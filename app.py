from flask import Flask, request, jsonify, render_template_string
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import io
import base64
from datetime import datetime
import sqlite3
import threading
import json

app = Flask(__name__)

# Database configuration
DATABASE = 'metrics.db'
max_entries = 100
db_lock = threading.Lock()

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
        <h1>System Metrics Dashboard</h1>
        
        <div class="api-info">
            <h2>How to Send Metrics</h2>
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
            <h2>No Metrics Yet</h2>
            <p>Waiting for clients to send data...</p>
            <p>Use the API endpoint above to start sending metrics.</p>
        </div>
        {% endif %}
    </div>
</body>
</html>
'''

# ==================== DATABASE FUNCTIONS ====================

def init_db():
    """Initialize the SQLite database."""
    with db_lock:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        
        # Create metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id TEXT NOT NULL,
                client_name TEXT,
                timestamp TEXT NOT NULL,
                received_at TEXT NOT NULL,
                cpu_percent REAL,
                gpu_percent REAL,
                ram_json TEXT,
                ping_ms REAL,
                internet_connected INTEGER,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_client_id ON metrics(client_id)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON metrics(timestamp DESC)
        ''')
        
        conn.commit()
        conn.close()

def get_db_connection():
    """Get a database connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def cleanup_old_metrics(client_id):
    """Keep only the latest max_entries for each client."""
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Count entries for this client
        cursor.execute('SELECT COUNT(*) as count FROM metrics WHERE client_id = ?', (client_id,))
        count = cursor.fetchone()['count']
        
        if count > max_entries:
            # Delete oldest entries
            cursor.execute('''
                DELETE FROM metrics 
                WHERE client_id = ? 
                AND id NOT IN (
                    SELECT id FROM metrics 
                    WHERE client_id = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                )
            ''', (client_id, client_id, max_entries))
            conn.commit()
        
        conn.close()

def insert_metric(client_id, data):
    """Insert a metric into the database."""
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Extract fields
        client_name = data.get('client_name')
        timestamp = data.get('timestamp')
        received_at = data.get('received_at')
        cpu_percent = data.get('cpu_percent')
        gpu_percent = data.get('gpu_percent')
        ram = data.get('ram')
        ping_ms = data.get('ping_ms')
        internet_connected = data.get('internet_connected')
        
        # Convert RAM to JSON string
        ram_json = json.dumps(ram) if ram else None
        
        # Store complete raw data as JSON
        raw_data = json.dumps(data)
        
        cursor.execute('''
            INSERT INTO metrics 
            (client_id, client_name, timestamp, received_at, cpu_percent, gpu_percent, 
             ram_json, ping_ms, internet_connected, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, client_name, timestamp, received_at, cpu_percent, gpu_percent,
              ram_json, ping_ms, internet_connected, raw_data))
        
        conn.commit()
        
        # Get count for this client
        cursor.execute('SELECT COUNT(*) as count FROM metrics WHERE client_id = ?', (client_id,))
        count = cursor.fetchone()['count']
        
        conn.close()
        
        # Cleanup old entries
        cleanup_old_metrics(client_id)
        
        return count

def get_all_metrics(limit=50):
    """Get all metrics from database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM metrics 
        ORDER BY timestamp DESC 
        LIMIT ?
    ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Convert to list of dicts
    metrics = []
    for row in rows:
        metric = json.loads(row['raw_data'])
        metric['client_id'] = row['client_id']
        metrics.append(metric)
    
    return metrics

def get_client_metrics(client_id=None, limit=20):
    """Get metrics for a specific client or all clients."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if client_id:
        cursor.execute('''
            SELECT * FROM metrics 
            WHERE client_id = ?
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (client_id, limit))
    else:
        cursor.execute('''
            SELECT * FROM metrics 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    
    # Convert to list of dicts
    metrics = []
    for row in rows:
        metric = json.loads(row['raw_data'])
        metric['client_id'] = row['client_id']
        metrics.append(metric)
    
    return metrics

def get_total_clients():
    """Get count of unique clients."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(DISTINCT client_id) as count FROM metrics')
    count = cursor.fetchone()['count']
    
    conn.close()
    return count

def get_total_metrics():
    """Get total count of metrics."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) as count FROM metrics')
    count = cursor.fetchone()['count']
    
    conn.close()
    return count

def get_client_list():
    """Get list of all clients with their info."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            client_id,
            client_name,
            MAX(timestamp) as last_seen,
            COUNT(*) as metric_count
        FROM metrics
        GROUP BY client_id
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    clients = []
    for row in rows:
        clients.append({
            'client_id': row['client_id'],
            'client_name': row['client_name'] or row['client_id'],
            'last_seen': row['last_seen'],
            'metric_count': row['metric_count']
        })
    
    return clients

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
    # Get all metrics
    all_metrics = get_all_metrics(limit=50)
    
    # Get latest metrics for stat cards
    latest = all_metrics[0] if all_metrics else None
    
    # Generate charts from recent metrics (last 20)
    recent_metrics = list(reversed(get_client_metrics(limit=20)))
    charts = generate_charts(recent_metrics)
    
    # Get statistics
    total_clients = get_total_clients()
    total_metrics = get_total_metrics()
    
    # Get base URL for API instructions
    base_url = request.url_root.rstrip('/')
    
    return render_template_string(
        HTML_TEMPLATE,
        metrics=all_metrics,
        latest_metrics=latest,
        charts=charts,
        total_clients=total_clients,
        total_metrics=total_metrics,
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
        
        # Insert into database
        count = insert_metric(client_id, data)
        
        return jsonify({
            'status': 'success',
            'message': 'Metrics received',
            'client_id': client_id,
            'stored_count': count
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    """API endpoint to retrieve stored metrics."""
    all_metrics = get_all_metrics(limit=1000)
    total_clients = get_total_clients()
    
    return jsonify({
        'total_entries': len(all_metrics),
        'total_clients': total_clients,
        'metrics': all_metrics
    }), 200

@app.route('/api/clients', methods=['GET'])
def get_clients():
    """API endpoint to get list of connected clients."""
    clients = get_client_list()
    
    return jsonify({
        'total_clients': len(clients),
        'clients': clients
    }), 200

@app.route('/health')
def health():
    """Health check endpoint for Azure."""
    total_clients = get_total_clients()
    
    return jsonify({
        'status': 'healthy',
        'clients': total_clients,
        'timestamp': datetime.now().isoformat()
    }), 200

# ==================== MAIN ====================

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    # For local development
    app.run(host='0.0.0.0', port=8000, debug=False)
import os
import sqlite3
import json
import random
import time
import threading
from datetime import datetime
from flask import Flask, render_template, jsonify, request, g

app = Flask(__name__)
app.config['DATABASE'] = 'crane_monitor.db'

# --- Database Setup ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(app.config['DATABASE'])
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with app.open_resource('schema.sql', mode='r') as f:
            db.cursor().executescript(f.read())
        db.commit()

# --- Mock Sensor Data Generator ---
class SensorSimulator:
    def __init__(self):
        self.running = False
        self.telemetry = {
            "vibration_mm_s": 0.0,
            "temperature_c": 0.0,
            "load_cycles": 10000,
            "motor_current_a": 0.0,
            "brake_health_pct": 98.5,
            "motor_hours": 1240.5,
            "oil_pressure_bar": 5.0,
            "gearbox_oil_temp_c": 45.0,
            "hydraulic_pressure_bar": 120.0,
            "voltage_imbalance_pct": 0.5
        }
        # Detailed Component Wear (Invisible to simple telemetry, used for deep diagnostics)
        self.component_wear = {
            "main_bearing": 0.05, # 0.0 to 1.0 (1.0 = failure)
            "hoist_motor": 0.12,
            "cable_tension": 0.02
        }
        self.history = [] # Store last 50 points

    def generate_data(self):
        while self.running:
            # Simulate slight fluctuations
            self.telemetry["vibration_mm_s"] = round(random.uniform(0.5, 5.0), 2)
            self.telemetry["temperature_c"] = round(random.uniform(20.0, 95.0), 1)
            self.telemetry["motor_current_a"] = round(random.uniform(10.0, 60.0), 1)
            self.telemetry["load_cycles"] += int(random.random() > 0.8) # Increment occasionally
            
            # Slow degradation for demos
            self.telemetry["brake_health_pct"] = round(max(0, self.telemetry["brake_health_pct"] - (random.random() * 0.01)), 2)
            self.telemetry["motor_hours"] = round(self.telemetry["motor_hours"] + 0.01, 2)
            self.telemetry["oil_pressure_bar"] = round(random.uniform(4.8, 5.2), 2)
            
            # Additional sensors
            self.telemetry["gearbox_oil_temp_c"] = round(random.uniform(40.0, 60.0), 1)
            self.telemetry["hydraulic_pressure_bar"] = round(random.uniform(115.0, 125.0), 1)
            self.telemetry["voltage_imbalance_pct"] = round(random.uniform(0.0, 1.5), 2)

            # Update specialized component wear
            self.component_wear["main_bearing"] = min(1.0, self.component_wear["main_bearing"] + (0.0001 * random.random()))
            self.component_wear["hoist_motor"] = min(1.0, self.component_wear["hoist_motor"] + (0.00005 * random.random()))

            # Update timestamp for history
            snapshot = self.telemetry.copy()
            snapshot.update(self.component_wear) # Include deep data in snapshot for API usage if needed
            snapshot["timestamp"] = datetime.now().isoformat()
            
            self.history.append(snapshot)
            if len(self.history) > 50:
                self.history.pop(0)
            
            time.sleep(2) # Update every 2 seconds

    def start(self):
        if not self.running:
            self.running = True
            thread = threading.Thread(target=self.generate_data)
            thread.daemon = True
            thread.start()

# --- Inventory Management ---
class InventoryManager:
    def __init__(self):
        self.stock = {
            "Main Bearing (B-54)": 1,
            "Hoist Motor": 2,
            "Hydraulic Filter": 12
        }

    def get_stock(self):
        return self.stock

    def update_stock(self, part_name, change):
        if part_name in self.stock:
            self.stock[part_name] += change
            return True
        return False

inventory_mgr = InventoryManager()

sensor_sim = SensorSimulator()

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/owner')
def owner_view():
    return render_template('owner.html')

@app.route('/maintenance')
def maintenance_view():
    return render_template('maintenance.html')

@app.route('/technician')
def technician_view():
    return render_template('technician.html')

@app.route('/api/telemetry')
def get_telemetry():
    # Merge basic telemetry with deep component data for broader API access
    data = sensor_sim.telemetry.copy()
    data.update(sensor_sim.component_wear)
    return jsonify(data)

from gemini_integration import engine
import uuid

# ... (imports remain the same)

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """
    Triggers an analysis based on current or provided telemetry.
    """
    data = request.json
    if not data:
        # If no data provided, use current simulated data
        data = sensor_sim.telemetry
        # Add a timestamp if missing
        data['timestamp'] = datetime.now().isoformat()
    
    # 1. Get Analysis from Gemini
    analysis = engine.analyze_telemetry(data)
    
    # 2. Construct Event Object
    event_id = str(uuid.uuid4())
    event = {
        "id": event_id,
        "timestamp": datetime.now().isoformat(),
        "component_id": "CRANE-01", # Mock ID
        "type": analysis.get("type", "Info"),
        "severity": analysis.get("urgency_score", 1) / 10.0,
        "urgency_score": analysis.get("urgency_score", 1),
        "raw_telemetry": json.dumps(data),
        "prescription": json.dumps(analysis.get("prescription", {})),
        "status": "active",
        "resolution_notes": ""
    }

    # 3. Save to DB
    db = get_db()
    db.execute(
        'INSERT INTO events (id, timestamp, component_id, type, severity, urgency_score, raw_telemetry, prescription, status, resolution_notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (event['id'], event['timestamp'], event['component_id'], event['type'], event['severity'], event['urgency_score'], event['raw_telemetry'], event['prescription'], event['status'], event['resolution_notes'])
    )
    
    # 4. Auto-log Diagnostic Scan
    db.execute(
        'INSERT INTO audit_log (timestamp, role, action, event_id, details) VALUES (?, ?, ?, ?, ?)',
        (datetime.now().isoformat(), 'Technician', 'Ran Diagnostic Scan', event['id'], f"Detected: {event['type']}")
    )
    db.commit()

    return jsonify(event), 201

@app.route('/api/events', methods=['GET'])
def events():
    status_filter = request.args.get('status')
    db = get_db()
    
    query = 'SELECT * FROM events'
    args = []
    
    if status_filter:
        query += ' WHERE status = ?'
        args.append(status_filter)
        
    query += ' ORDER BY timestamp DESC LIMIT 20'
    
    cur = db.execute(query, args)
    events = []
    for row in cur.fetchall():
        item = dict(row)
        # Parse JSON strings back to objects for the API response
        try:
            item['raw_telemetry'] = json.loads(item['raw_telemetry'])
            item['prescription'] = json.loads(item['prescription'])
        except:
            pass
        events.append(item)
    return jsonify(events)

@app.route('/api/events/<event_id>/resolve', methods=['POST'])
def resolve_event(event_id):
    data = request.json
    notes = data.get('notes', 'Resolved via Dashboard')
    
    db = get_db()
    
    # 1. Update Event
    db.execute(
        'UPDATE events SET status = ?, resolution_notes = ? WHERE id = ?',
        ('resolved', notes, event_id)
    )
    
    # 2. Add to Audit Log
    db.execute(
        'INSERT INTO audit_log (timestamp, role, action, event_id, details) VALUES (?, ?, ?, ?, ?)',
        (datetime.now().isoformat(), 'Technician', 'Resolved Issue', event_id, notes)
    )

    db.commit()
    return jsonify({"status": "success", "message": "Event resolved"}), 200

@app.route('/api/verify_fix', methods=['POST'])
def verify_fix():
    data = request.json
    event_id = data.get('event_id')
    checks = data.get('checks', [])

    db = get_db()
    # Log specific verification steps
    details = f"Verified: {', '.join(checks)}"
    db.execute(
        'INSERT INTO audit_log (timestamp, role, action, event_id, details) VALUES (?, ?, ?, ?, ?)',
        (datetime.now().isoformat(), 'Technician', 'Protocol Verification', event_id, details)
    )
    db.commit()
    return jsonify({"status": "success"}), 200

@app.route('/api/decisions', methods=['POST'])
def log_decision():
    data = request.json
    role = data.get('role', 'Owner')
    decision = data.get('decision', 'Unknown Decision')
    event_id = data.get('event_id')

    # 1. Log to Audit
    db = get_db()
    db.execute(
        'INSERT INTO audit_log (timestamp, role, action, event_id, details) VALUES (?, ?, ?, ?, ?)',
        (datetime.now().isoformat(), role, 'Executive Decision', event_id, decision)
    )
    
    # 2. Update Event with Decision
    db.execute(
        'UPDATE events SET owner_decision = ? WHERE id = ?',
        (decision, event_id)
    )
    db.commit()
    return jsonify({"status": "success"}), 200

@app.route('/api/log_action', methods=['POST'])
def log_action():
    data = request.json
    role = data.get('role', 'System')
    action = data.get('action', 'Activity')
    details = data.get('details', '')
    event_id = data.get('event_id')

    db = get_db()
    db.execute(
        'INSERT INTO audit_log (timestamp, role, action, event_id, details) VALUES (?, ?, ?, ?, ?)',
        (datetime.now().isoformat(), role, action, event_id, details)
    )
    db.commit()
    return jsonify({"status": "success"}), 200

@app.route('/api/audit_log', methods=['GET'])
def get_audit_log():
    role_filter = request.args.get('role')
    db = get_db()
    
    query = 'SELECT * FROM audit_log'
    args = []
    
    if role_filter:
        query += ' WHERE role = ?'
        args.append(role_filter)
        
    query += ' ORDER BY timestamp DESC LIMIT 50'
    
    cur = db.execute(query, args)
    logs = [dict(row) for row in cur.fetchall()]
    return jsonify(logs)

@app.route('/api/history', methods=['GET'])
def get_history():
    return jsonify(sensor_sim.history)

# --- Parts & Inventory APIs ---

@app.route('/api/inventory', methods=['GET'])
def get_inventory():
    return jsonify(inventory_mgr.get_stock())

@app.route('/api/parts/request', methods=['POST'])
def request_part():
    data = request.json
    part = data.get('part')
    role = data.get('role', 'Maintenance Lead')
    
    db = get_db()
    req_id = str(uuid.uuid4())
    db.execute(
        'INSERT INTO part_requests (id, part_name, requester_role, status, timestamp) VALUES (?, ?, ?, ?, ?)',
        (req_id, part, role, 'pending', datetime.now().isoformat())
    )
    
    # Log action
    db.execute(
        'INSERT INTO audit_log (timestamp, role, action, event_id, details) VALUES (?, ?, ?, ?, ?)',
        (datetime.now().isoformat(), role, 'Requested Part', req_id, f"Requested restock: {part}")
    )
    db.commit()
    
    return jsonify({"status": "success", "id": req_id}), 201

@app.route('/api/parts/requests', methods=['GET'])
def get_part_requests():
    status = request.args.get('status')
    db = get_db()
    query = 'SELECT * FROM part_requests'
    args = []
    if status:
        query += ' WHERE status = ?'
        args.append(status)
    query += ' ORDER BY timestamp DESC'
    
    cur = db.execute(query, args)
    return jsonify([dict(row) for row in cur.fetchall()])

# --- Business Metrics ---
class BusinessMetrics:
    def __init__(self):
        self.metrics = {
            "uptime_pct": 98.5,
            "maintenance_spend": 12450,
            "maintenance_budget": 15000,
            "avoided_downtime_savings": 45000,
            "active_assets": 1,
            "total_assets": 1
        }
    
    def get_metrics(self):
        # Simulate slight fluctuations
        self.metrics["uptime_pct"] = round(98.0 + (random.random() * 1.5), 2)
        return self.metrics

business_metrics = BusinessMetrics()

# --- Routes ---

# ... (Routes remain until new API)

@app.route('/api/parts/approve/<req_id>', methods=['POST'])
def approve_part(req_id):
    db = get_db()
    
    # Get request details
    cur = db.execute('SELECT * FROM part_requests WHERE id = ?', (req_id,))
    req = cur.fetchone()
    if not req:
        return jsonify({"error": "Request not found"}), 404
    
    part_name = req['part_name']
    
    # Update Request Status
    db.execute('UPDATE part_requests SET status = ? WHERE id = ?', ('approved', req_id))
    
    # Update Inventory (Simulated instant arrival)
    inventory_mgr.update_stock(part_name, 5) # Add 5 units on approval
    
    # Log Action
    db.execute(
        'INSERT INTO audit_log (timestamp, role, action, event_id, details) VALUES (?, ?, ?, ?, ?)',
        (datetime.now().isoformat(), 'Owner', 'Approved Purchase', req_id, f"Approved order for {part_name}. Stock updated.")
    )
    db.commit()
    
    return jsonify({"status": "success", "new_stock": inventory_mgr.stock.get(part_name)}), 200

@app.route('/api/business/metrics', methods=['GET'])
def get_business_metrics():
    return jsonify(business_metrics.get_metrics())

if __name__ == '__main__':
# ... (Startup logic remains)
    # Ensure tables exist (Simple migration)
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                component_id TEXT NOT NULL,
                type TEXT NOT NULL,
                severity REAL,
                urgency_score INTEGER,
                raw_telemetry TEXT,
                prescription TEXT,
                status TEXT DEFAULT 'active',
                resolution_notes TEXT
            );
            
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                action TEXT NOT NULL,
                event_id TEXT,
                details TEXT
            );

            CREATE TABLE IF NOT EXISTS part_requests (
                id TEXT PRIMARY KEY,
                part_name TEXT NOT NULL,
                requester_role TEXT,
                status TEXT DEFAULT 'pending',
                timestamp TEXT
            );
        ''')
        db.commit()

    if not os.path.exists(app.config['DATABASE']):
        # Create schema.sql if it doesn't exist for first run (redundant but kept for consistency)
        with open('schema.sql', 'w') as f:
            f.write('''
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    component_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    severity REAL,
                    urgency_score INTEGER,
                    raw_telemetry TEXT,
                    prescription TEXT,
                    status TEXT DEFAULT 'active',
                    resolution_notes TEXT
                );
                
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    event_id TEXT,
                    details TEXT
                );

                CREATE TABLE IF NOT EXISTS part_requests (
                    id TEXT PRIMARY KEY,
                    part_name TEXT NOT NULL,
                    requester_role TEXT,
                    status TEXT DEFAULT 'pending',
                    timestamp TEXT
                );
            ''')
        init_db()
    
    # Decide if migration is needed for owner_decision
    with app.app_context():
        db = get_db()
        try:
            db.execute('SELECT owner_decision FROM events LIMIT 1')
        except sqlite3.OperationalError:
            print("Migrating: Adding owner_decision column to events table.")
            db.execute('ALTER TABLE events ADD COLUMN owner_decision TEXT')
            db.commit()

    sensor_sim.start()
    app.run()

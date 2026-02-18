
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

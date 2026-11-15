"""
Akash Setu - Database & Persistence Layer
Module: core/db.py

Manages SQLite storage for:
- Raw emergency messages (original content strictly preserved)
- Consolidated incidents
- Rescue teams & fleet roster
- Incident operational audit trails
- Low-bandwidth satellite communication logs
- Mathematical risk assessment breakdown
"""

import sqlite3
import json
import os
import datetime
from typing import Dict, Any, List, Optional, Tuple

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "akash_setu.db")


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    target_path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(target_path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[str] = None):
    """Creates all required tables and indexes if they do not exist."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.executescript("""
    -- 1. Raw messages table: original incoming transmissions are ALWAYS preserved verbatim.
    CREATE TABLE IF NOT EXISTS raw_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raw_text TEXT NOT NULL,
        channel TEXT NOT NULL, -- WEB, SATELLITE_BURST, SMS, HF_RADIO, FIELD_RELAY
        sender_contact TEXT,
        received_at TEXT NOT NULL,
        signal_metrics TEXT, -- JSON containing SNR, constellation, packet stats
        processed_flag INTEGER DEFAULT 0,
        incident_id INTEGER,
        FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE SET NULL
    );

    -- 2. Consolidated incidents table
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_code TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        disaster_type TEXT NOT NULL, -- FLOOD, LANDSLIDE, EARTHQUAKE, BUILDING_COLLAPSE, FIRE, MEDICAL, CYCLONE
        severity_level TEXT NOT NULL, -- CRITICAL, HIGH, MEDIUM, LOW
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        location_name TEXT NOT NULL,
        district TEXT NOT NULL,
        trapped_count INTEGER, -- NULLABLE: explicitly preserves unknown states! Never silently 0.
        injured_count INTEGER, -- NULLABLE
        casualties_count INTEGER, -- NULLABLE
        vulnerable_groups TEXT, -- JSON list: ["INFANTS", "ELDERLY", "PREGNANT", "DIALYSIS"]
        infrastructure_damaged TEXT, -- JSON list or descriptive text
        water_level_meters REAL, -- NULLABLE float for flood depth
        risk_score REAL NOT NULL DEFAULT 0.0, -- 0.0 to 100.0 from mathematical risk algorithm
        priority_level TEXT NOT NULL, -- P1, P2, P3, P4
        status TEXT NOT NULL DEFAULT 'PENDING_TRIAGE', -- PENDING_TRIAGE, TRIAGED, DISPATCHED, IN_PROGRESS, RESOLVED, CLOSED
        assigned_team_id INTEGER,
        deduplication_cluster_id TEXT,
        duplicate_count INTEGER DEFAULT 0,
        is_consolidated INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        ai_classification_meta TEXT, -- JSON storing classifier engine, confidence, entity tags
        risk_breakdown TEXT, -- JSON storing exact math components
        FOREIGN KEY (assigned_team_id) REFERENCES rescue_teams (id) ON DELETE SET NULL
    );

    -- 3. Incident updates / audit log
    CREATE TABLE IF NOT EXISTS incident_updates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        incident_id INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        author TEXT NOT NULL,
        update_type TEXT NOT NULL, -- CREATED, STATUS_CHANGE, TEAM_DISPATCHED, VICTIM_UPDATE, MERGED, SITREP
        message TEXT NOT NULL,
        previous_status TEXT,
        new_status TEXT,
        FOREIGN KEY (incident_id) REFERENCES incidents (id) ON DELETE CASCADE
    );

    -- 4. Rescue teams roster
    CREATE TABLE IF NOT EXISTS rescue_teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        agency TEXT NOT NULL, -- NDRF, SDRF, ARMY_AVIATION, ITBP, RED_CROSS, CIVIL_DEFENCE
        specialization TEXT NOT NULL, -- FLOOD_WATER_RESCUE, HIGH_ALTITUDE, COLLAPSE_SEARCH, HELI_EVAC, MEDICAL_TRIAGE
        leader_name TEXT NOT NULL,
        contact TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'AVAILABLE', -- AVAILABLE, DISPATCHED, ON_SITE, STANDBY, REST
        current_lat REAL NOT NULL,
        current_lon REAL NOT NULL,
        base_location TEXT NOT NULL,
        capacity_persons INTEGER NOT NULL DEFAULT 10,
        equipment TEXT, -- JSON list of equipment: ["INFLATABLE_BOATS", "DRONES", "HELI_WINCH", etc.]
        assigned_incident_id INTEGER,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (assigned_incident_id) REFERENCES incidents (id) ON DELETE SET NULL
    );

    -- 5. Low-bandwidth satellite transmission logs
    CREATE TABLE IF NOT EXISTS satellite_transmissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        packet_id TEXT UNIQUE NOT NULL,
        constellation TEXT NOT NULL, -- NAVIC_DISASTER_BURST, GSAT_7A, IRIDIUM_SBD, INMARSAT_C
        raw_bytes_count INTEGER NOT NULL,
        compressed_bytes_count INTEGER NOT NULL,
        compression_ratio REAL NOT NULL,
        snr_db REAL NOT NULL,
        elevation_deg REAL NOT NULL,
        link_margin_db REAL NOT NULL,
        packet_loss_simulated INTEGER DEFAULT 0,
        retransmissions INTEGER DEFAULT 0,
        transmission_time_ms REAL NOT NULL,
        status TEXT NOT NULL, -- DELIVERED, RETRANSMITTED, FAILED
        hex_payload TEXT NOT NULL,
        decoded_payload TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );

    -- Indexes for high-speed triage & search
    CREATE INDEX IF NOT EXISTS idx_incidents_priority ON incidents (priority_level, status);
    CREATE INDEX IF NOT EXISTS idx_incidents_geo ON incidents (latitude, longitude);
    CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents (status);
    CREATE INDEX IF NOT EXISTS idx_raw_messages_incident ON raw_messages (incident_id);
    CREATE INDEX IF NOT EXISTS idx_teams_status ON rescue_teams (status);
    """)

    conn.commit()
    conn.close()


def save_raw_message(raw_text: str, channel: str, sender_contact: Optional[str] = None,
                     signal_metrics: Optional[Dict[str, Any]] = None,
                     db_path: Optional[str] = None) -> int:
    """Saves raw message strictly unaltered."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    metrics_json = json.dumps(signal_metrics or {})

    cursor.execute("""
        INSERT INTO raw_messages (raw_text, channel, sender_contact, received_at, signal_metrics)
        VALUES (?, ?, ?, ?, ?)
    """, (raw_text, channel, sender_contact, now, metrics_json))

    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id


def link_message_to_incident(msg_id: int, incident_id: int, db_path: Optional[str] = None):
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE raw_messages SET incident_id = ?, processed_flag = 1 WHERE id = ?", (incident_id, msg_id))
    conn.commit()
    conn.close()


def insert_incident(incident: Dict[str, Any], raw_msg_id: Optional[int] = None,
                    db_path: Optional[str] = None) -> int:
    """Inserts an incident and optionally links its source raw message."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Generate incident code if not provided
    if not incident.get("incident_code"):
        cursor.execute("SELECT COUNT(*) FROM incidents")
        count = cursor.fetchone()[0] + 1
        incident["incident_code"] = f"AS-INC-{count:04d}"

    vulnerable_groups_json = json.dumps(incident.get("vulnerable_groups") or [])
    infra_json = json.dumps(incident.get("infrastructure_damaged") or [])
    ai_meta_json = json.dumps(incident.get("ai_classification_meta") or {})
    risk_breakdown_json = json.dumps(incident.get("risk_breakdown") or {})

    cursor.execute("""
        INSERT INTO incidents (
            incident_code, title, disaster_type, severity_level,
            latitude, longitude, location_name, district,
            trapped_count, injured_count, casualties_count,
            vulnerable_groups, infrastructure_damaged, water_level_meters,
            risk_score, priority_level, status, assigned_team_id,
            deduplication_cluster_id, duplicate_count, is_consolidated,
            created_at, updated_at, ai_classification_meta, risk_breakdown
        ) VALUES (
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?
        )
    """, (
        incident["incident_code"],
        incident.get("title", "Emergency Incident"),
        incident.get("disaster_type", "GENERAL_DISASTER"),
        incident.get("severity_level", "HIGH"),
        float(incident["latitude"]),
        float(incident["longitude"]),
        incident.get("location_name", "Disaster Sector"),
        incident.get("district", "Uttarakhand"),
        incident.get("trapped_count"), # Notice: preserves None/null!
        incident.get("injured_count"), # Notice: preserves None/null!
        incident.get("casualties_count"), # Notice: preserves None/null!
        vulnerable_groups_json,
        infra_json,
        incident.get("water_level_meters"),
        float(incident.get("risk_score", 0.0)),
        incident.get("priority_level", "P2"),
        incident.get("status", "PENDING_TRIAGE"),
        incident.get("assigned_team_id"),
        incident.get("deduplication_cluster_id"),
        int(incident.get("duplicate_count", 0)),
        int(incident.get("is_consolidated", 0)),
        incident.get("created_at", now),
        now,
        ai_meta_json,
        risk_breakdown_json
    ))

    inc_id = cursor.lastrowid

    # Record creation update log
    cursor.execute("""
        INSERT INTO incident_updates (incident_id, timestamp, author, update_type, message, new_status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (inc_id, now, "System/Triage Intake", "CREATED", "Incident logged into Akash Setu triage queue", incident.get("status", "PENDING_TRIAGE")))

    if raw_msg_id:
        cursor.execute("UPDATE raw_messages SET incident_id = ?, processed_flag = 1 WHERE id = ?", (inc_id, raw_msg_id))

    conn.commit()
    conn.close()
    return inc_id


def get_incidents(status: Optional[str] = None, priority: Optional[str] = None,
                  disaster_type: Optional[str] = None, search: Optional[str] = None,
                  db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Fetches list of incidents with filtering and priority order."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    query = """
        SELECT i.*, t.name as assigned_team_name, t.agency as assigned_team_agency,
               t.contact as assigned_team_contact
        FROM incidents i
        LEFT JOIN rescue_teams t ON i.assigned_team_id = t.id
        WHERE 1=1
    """
    params: List[Any] = []

    if status and status != "ALL":
        query += " AND i.status = ?"
        params.append(status)

    if priority and priority != "ALL":
        query += " AND i.priority_level = ?"
        params.append(priority)

    if disaster_type and disaster_type != "ALL":
        query += " AND i.disaster_type = ?"
        params.append(disaster_type)

    if search:
        search_like = f"%{search.strip()}%"
        query += " AND (i.title LIKE ? OR i.location_name LIKE ? OR i.district LIKE ? OR i.incident_code LIKE ?)"
        params.extend([search_like, search_like, search_like, search_like])

    # Sort primarily by risk_score DESC (so critical P1 comes first) then created_at DESC
    query += " ORDER BY i.risk_score DESC, i.created_at DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    results = []
    for r in rows:
        item = dict(r)
        # Parse JSON fields
        item["vulnerable_groups"] = json.loads(item["vulnerable_groups"] or "[]")
        item["infrastructure_damaged"] = json.loads(item["infrastructure_damaged"] or "[]")
        item["ai_classification_meta"] = json.loads(item["ai_classification_meta"] or "{}")
        item["risk_breakdown"] = json.loads(item["risk_breakdown"] or "{}")
        results.append(item)

    conn.close()
    return results


def get_incident_by_id(incident_id: int, db_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves full incident details including raw message records and update timeline."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT i.*, t.name as assigned_team_name, t.agency as assigned_team_agency,
               t.contact as assigned_team_contact, t.status as assigned_team_status
        FROM incidents i
        LEFT JOIN rescue_teams t ON i.assigned_team_id = t.id
        WHERE i.id = ?
    """, (incident_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return None

    incident = dict(row)
    incident["vulnerable_groups"] = json.loads(incident["vulnerable_groups"] or "[]")
    incident["infrastructure_damaged"] = json.loads(incident["infrastructure_damaged"] or "[]")
    incident["ai_classification_meta"] = json.loads(incident["ai_classification_meta"] or "{}")
    incident["risk_breakdown"] = json.loads(incident["risk_breakdown"] or "{}")

    # Fetch associated raw messages (original source text strictly preserved)
    cursor.execute("""
        SELECT id, raw_text, channel, sender_contact, received_at, signal_metrics
        FROM raw_messages
        WHERE incident_id = ?
        ORDER BY received_at ASC
    """, (incident_id,))
    msg_rows = cursor.fetchall()
    incident["raw_messages"] = []
    for m in msg_rows:
        m_dict = dict(m)
        m_dict["signal_metrics"] = json.loads(m_dict["signal_metrics"] or "{}")
        incident["raw_messages"].append(m_dict)

    # Fetch timeline updates
    cursor.execute("""
        SELECT id, timestamp, author, update_type, message, previous_status, new_status
        FROM incident_updates
        WHERE incident_id = ?
        ORDER BY timestamp ASC
    """, (incident_id,))
    update_rows = cursor.fetchall()
    incident["updates"] = [dict(u) for u in update_rows]

    conn.close()
    return incident


def update_incident_status(incident_id: int, new_status: str, author: str,
                           note: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    cursor.execute("SELECT status FROM incidents WHERE id = ?", (incident_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    old_status = row["status"]
    cursor.execute("""
        UPDATE incidents
        SET status = ?, updated_at = ?
        WHERE id = ?
    """, (new_status, now, incident_id))

    cursor.execute("""
        INSERT INTO incident_updates (incident_id, timestamp, author, update_type, message, previous_status, new_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (incident_id, now, author, "STATUS_CHANGE", note or f"Status changed from {old_status} to {new_status}", old_status, new_status))

    # If resolved or closed, free up assigned rescue team
    if new_status in ("RESOLVED", "CLOSED"):
        cursor.execute("SELECT assigned_team_id FROM incidents WHERE id = ?", (incident_id,))
        inc_team = cursor.fetchone()
        if inc_team and inc_team["assigned_team_id"]:
            cursor.execute("""
                UPDATE rescue_teams
                SET status = 'AVAILABLE', assigned_incident_id = NULL, updated_at = ?
                WHERE id = ?
            """, (now, inc_team["assigned_team_id"]))

    conn.commit()
    conn.close()
    return True


def assign_team_to_incident(incident_id: int, team_id: int, author: str,
                            notes: Optional[str] = None, db_path: Optional[str] = None) -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    cursor.execute("SELECT id, name, status FROM rescue_teams WHERE id = ?", (team_id,))
    team = cursor.fetchone()
    if not team:
        conn.close()
        return False

    cursor.execute("SELECT id, status, incident_code FROM incidents WHERE id = ?", (incident_id,))
    inc = cursor.fetchone()
    if not inc:
        conn.close()
        return False

    # Update incident
    cursor.execute("""
        UPDATE incidents
        SET assigned_team_id = ?, status = 'DISPATCHED', updated_at = ?
        WHERE id = ?
    """, (team_id, now, incident_id))

    # Update team status
    cursor.execute("""
        UPDATE rescue_teams
        SET status = 'DISPATCHED', assigned_incident_id = ?, updated_at = ?
        WHERE id = ?
    """, (incident_id, now, team_id))

    # Update log
    cursor.execute("""
        INSERT INTO incident_updates (incident_id, timestamp, author, update_type, message, previous_status, new_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        incident_id, now, author, "TEAM_DISPATCHED",
        f"Rescue Team '{team['name']}' dispatched to incident {inc['incident_code']}. {notes or ''}",
        inc["status"], "DISPATCHED"
    ))

    conn.commit()
    conn.close()
    return True


def merge_incidents(primary_id: int, duplicate_id: int, author: str,
                    reason: str = "Duplicate report consolidated",
                    db_path: Optional[str] = None) -> bool:
    """Consolidates duplicate_id into primary_id, repointing raw messages and aggregating counts."""
    if primary_id == duplicate_id:
        return False

    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    cursor.execute("SELECT * FROM incidents WHERE id = ?", (primary_id,))
    p_row = cursor.fetchone()
    cursor.execute("SELECT * FROM incidents WHERE id = ?", (duplicate_id,))
    d_row = cursor.fetchone()

    if not p_row or not d_row:
        conn.close()
        return False

    # Repoint raw messages from duplicate to primary
    cursor.execute("UPDATE raw_messages SET incident_id = ? WHERE incident_id = ?", (primary_id, duplicate_id))

    # Aggregate counts carefully: preserve NULL if both were unknown, otherwise max known values to prevent double counting
    p_trapped = p_row["trapped_count"]
    d_trapped = d_row["trapped_count"]
    new_trapped = None
    if p_trapped is not None or d_trapped is not None:
        new_trapped = max(p_trapped or 0, d_trapped or 0)

    p_injured = p_row["injured_count"]
    d_injured = d_row["injured_count"]
    new_injured = None
    if p_injured is not None or d_injured is not None:
        new_injured = max(p_injured or 0, d_injured or 0)

    p_casualties = p_row["casualties_count"]
    d_casualties = d_row["casualties_count"]
    new_casualties = None
    if p_casualties is not None or d_casualties is not None:
        new_casualties = max(p_casualties or 0, d_casualties or 0)

    # Merge vulnerable groups list
    p_vuln = json.loads(p_row["vulnerable_groups"] or "[]")
    d_vuln = json.loads(d_row["vulnerable_groups"] or "[]")
    merged_vuln = list(set(p_vuln + d_vuln))

    new_dup_count = (p_row["duplicate_count"] or 0) + (d_row["duplicate_count"] or 0) + 1

    cursor.execute("""
        UPDATE incidents
        SET duplicate_count = ?, is_consolidated = 1,
            trapped_count = ?, injured_count = ?, casualties_count = ?,
            vulnerable_groups = ?, updated_at = ?
        WHERE id = ?
    """, (new_dup_count, new_trapped, new_injured, new_casualties, json.dumps(merged_vuln), now, primary_id))

    # Mark duplicate incident as CLOSED (CONSOLIDATED)
    cursor.execute("""
        UPDATE incidents
        SET status = 'CLOSED', updated_at = ?
        WHERE id = ?
    """, (now, duplicate_id))

    cursor.execute("""
        INSERT INTO incident_updates (incident_id, timestamp, author, update_type, message, previous_status, new_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        primary_id, now, author, "MERGED",
        f"Consolidated duplicate incident {d_row['incident_code']} into this incident. Reason: {reason}",
        p_row["status"], p_row["status"]
    ))

    cursor.execute("""
        INSERT INTO incident_updates (incident_id, timestamp, author, update_type, message, previous_status, new_status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        duplicate_id, now, author, "MERGED",
        f"Consolidated into primary incident {p_row['incident_code']}. Closed duplicate entry.",
        d_row["status"], "CLOSED"
    ))

    conn.commit()
    conn.close()
    return True


def get_rescue_teams(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT t.*, i.incident_code as assigned_incident_code, i.title as assigned_incident_title
        FROM rescue_teams t
        LEFT JOIN incidents i ON t.assigned_incident_id = i.id
        ORDER BY t.agency ASC, t.name ASC
    """)
    rows = cursor.fetchall()
    results = []
    for r in rows:
        item = dict(r)
        item["equipment"] = json.loads(item["equipment"] or "[]")
        results.append(item)
    conn.close()
    return results


def update_team_status(team_id: int, new_status: str, current_lat: Optional[float] = None,
                       current_lon: Optional[float] = None, db_path: Optional[str] = None) -> bool:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if current_lat is not None and current_lon is not None:
        cursor.execute("""
            UPDATE rescue_teams
            SET status = ?, current_lat = ?, current_lon = ?, updated_at = ?
            WHERE id = ?
        """, (new_status, current_lat, current_lon, now, team_id))
    else:
        cursor.execute("""
            UPDATE rescue_teams
            SET status = ?, updated_at = ?
            WHERE id = ?
        """, (new_status, now, team_id))

    conn.commit()
    conn.close()
    return True


def log_satellite_transmission(record: Dict[str, Any], db_path: Optional[str] = None) -> int:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    decoded_val = record.get("decoded_payload", "")
    if isinstance(decoded_val, (dict, list)):
        decoded_str = json.dumps(decoded_val)
    else:
        decoded_str = str(decoded_val)

    cursor.execute("""
        INSERT INTO satellite_transmissions (
            packet_id, constellation, raw_bytes_count, compressed_bytes_count,
            compression_ratio, snr_db, elevation_deg, link_margin_db,
            packet_loss_simulated, retransmissions, transmission_time_ms,
            status, hex_payload, decoded_payload, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record["packet_id"],
        record.get("constellation", "NAVIC_DISASTER_BURST"),
        int(record["raw_bytes_count"]),
        int(record["compressed_bytes_count"]),
        float(record["compression_ratio"]),
        float(record.get("snr_db", 14.5)),
        float(record.get("elevation_deg", 52.0)),
        float(record.get("link_margin_db", 6.8)),
        int(record.get("packet_loss_simulated", 0)),
        int(record.get("retransmissions", 0)),
        float(record.get("transmission_time_ms", 320.0)),
        record.get("status", "DELIVERED"),
        record.get("hex_payload", ""),
        decoded_str,
        record.get("timestamp", now)
    ))

    t_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return t_id


def get_satellite_logs(limit: int = 30, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM satellite_transmissions
        ORDER BY timestamp DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def get_analytics_summary(db_path: Optional[str] = None) -> Dict[str, Any]:
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Priority counts
    cursor.execute("SELECT priority_level, COUNT(*) as c FROM incidents GROUP BY priority_level")
    priority_counts = {r["priority_level"]: r["c"] for r in cursor.fetchall()}

    # Status counts
    cursor.execute("SELECT status, COUNT(*) as c FROM incidents GROUP BY status")
    status_counts = {r["status"]: r["c"] for r in cursor.fetchall()}

    # Disaster type counts
    cursor.execute("SELECT disaster_type, COUNT(*) as c FROM incidents GROUP BY disaster_type")
    type_counts = {r["disaster_type"]: r["c"] for r in cursor.fetchall()}

    # Total counts
    cursor.execute("SELECT COUNT(*) FROM incidents")
    total_incidents = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM raw_messages")
    total_messages = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM raw_messages WHERE channel = 'SATELLITE_BURST'")
    sat_messages = cursor.fetchone()[0]

    # Casualties summary
    cursor.execute("""
        SELECT
            SUM(CASE WHEN trapped_count IS NOT NULL THEN trapped_count ELSE 0 END) as total_trapped,
            SUM(CASE WHEN injured_count IS NOT NULL THEN injured_count ELSE 0 END) as total_injured,
            SUM(CASE WHEN casualties_count IS NOT NULL THEN casualties_count ELSE 0 END) as total_casualties,
            SUM(CASE WHEN trapped_count IS NULL THEN 1 ELSE 0 END) as unknown_trapped_incidents
        FROM incidents
    """)
    cas_row = cursor.fetchone()

    # Team availability
    cursor.execute("SELECT status, COUNT(*) as c FROM rescue_teams GROUP BY status")
    team_status = {r["status"]: r["c"] for r in cursor.fetchall()}

    # Satellite stats
    cursor.execute("""
        SELECT
            COUNT(*) as total_transmissions,
            AVG(compression_ratio) as avg_compression,
            AVG(transmission_time_ms) as avg_latency_ms,
            SUM(packet_loss_simulated) as simulated_loss_events
        FROM satellite_transmissions
    """)
    sat_row = cursor.fetchone()

    conn.close()

    critical_count = priority_counts.get("P1", 0)
    high_priority_count = priority_counts.get("P2", 0) + priority_counts.get("P3", 0)
    pending_count = (
        status_counts.get("PENDING_TRIAGE", 0) +
        status_counts.get("TRIAGED", 0) +
        status_counts.get("DISPATCHED", 0) +
        status_counts.get("IN_PROGRESS", 0)
    )
    resolved_count = status_counts.get("RESOLVED", 0) + status_counts.get("CLOSED", 0)

    return {
        "total_sos_reports": total_messages,
        "total_incidents": total_incidents,
        "critical_incidents": critical_count,
        "high_priority_incidents": high_priority_count,
        "pending_incidents": pending_count,
        "resolved_incidents": resolved_count,
        "total_messages": total_messages,
        "satellite_messages_count": sat_messages,
        "priority_distribution": {
            "P1": priority_counts.get("P1", 0),
            "P2": priority_counts.get("P2", 0),
            "P3": priority_counts.get("P3", 0),
            "P4": priority_counts.get("P4", 0)
        },
        "status_distribution": status_counts,
        "disaster_type_distribution": type_counts,
        "humanitarian_impact": {
            "total_trapped": cas_row["total_trapped"] if cas_row else 0,
            "total_injured": cas_row["total_injured"] if cas_row else 0,
            "total_fatalities": cas_row["total_casualties"] if cas_row else 0,
            "incidents_with_unknown_trapped_count": cas_row["unknown_trapped_incidents"] if cas_row else 0
        },
        "team_readiness": team_status,
        "satellite_network": {
            "total_packets": sat_row["total_transmissions"] if sat_row else 0,
            "avg_compression_pct": round((sat_row["avg_compression"] or 0) * 100, 1) if sat_row else 0,
            "avg_latency_ms": round(sat_row["avg_latency_ms"] or 0, 1) if sat_row else 0,
            "loss_events_recovered": sat_row["simulated_loss_events"] if sat_row else 0
        }
    }

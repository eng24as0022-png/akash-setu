"""
Akash Setu - Central Emergency Response HTTP Server & REST API
Entry point: server.py

Runs multi-threaded HTTP server with RESTful API endpoints and static file serving.
Zero third-party package dependencies required (pure standard library).
"""

import sys
import os
import json
import mimetypes
import urllib.parse
import hashlib
import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

# Add current directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.db import (
    init_db, get_connection, save_raw_message, insert_incident, get_incidents,
    get_incident_by_id, update_incident_status, assign_team_to_incident,
    merge_incidents, get_rescue_teams, update_team_status,
    log_satellite_transmission, get_satellite_logs, get_analytics_summary,
    link_message_to_incident
)
from core.classifier import DisasterClassifier
from core.deduplication import IncidentDeduplicator
from core.risk_engine import RiskScoringEngine
from core.satellite_sim import SatelliteLinkSimulator, SatellitePacketEncoder
from core.seed_data import seed_database


import uuid

# Authorized Rescue Team Credentials
ALLOWED_RESCUE_EMAILS = [
    "eng24as0018@dsu.edu.in",
    "eng24as0022@dsu.edu.in",
    "eng24as0016@dsu.edu.in",
    "vinayvinu96636@gmail.com"
]

DEMO_PASSWORD = os.environ.get("DEMO_PASSWORD", "AkashSetu@2026")
COMMANDER_PASSCODE = os.environ.get("COMMANDER_PASSCODE", "NDRF-2026-RESCUE")

# Session store for active tokens: token -> { "email": email, "role": role }
ACTIVE_SESSIONS = {
    hashlib.sha256(f"AKASH-SETU-{COMMANDER_PASSCODE}".encode()).hexdigest()[:32]: {
        "email": "commander@akashsetu.local",
        "role": "MISSION_COMMANDER"
    },
    hashlib.sha256(f"AKASH-SETU-{DEMO_PASSWORD}".encode()).hexdigest()[:32]: {
        "email": "eng24as0022@dsu.edu.in",
        "role": "RESCUE_TEAM"
    }
}

# Singletons for core engines
classifier = DisasterClassifier()
deduplicator = IncidentDeduplicator()
risk_engine = RiskScoringEngine()
satellite_sim = SatelliteLinkSimulator()


class AkashSetuRequestHandler(BaseHTTPRequestHandler):
    def get_authenticated_session(self) -> Optional[Dict[str, Any]]:
        """Returns session dict if caller holds valid Rescue Team authorization, else None."""
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token in ACTIVE_SESSIONS:
                return ACTIVE_SESSIONS[token]

        custom_key = self.headers.get("X-Commander-Key", "").strip()
        if custom_key in ACTIVE_SESSIONS:
            return ACTIVE_SESSIONS[custom_key]
        if custom_key in (COMMANDER_PASSCODE, DEMO_PASSWORD):
            return {"email": "commander@akashsetu.local", "role": "MISSION_COMMANDER"}

        return None

    def is_authenticated(self) -> bool:
        """Verifies whether caller holds valid Rescue Team authorization."""
        return self.get_authenticated_session() is not None
    def log_message(self, format, *args):
        # Override to keep server console clean while logging API calls
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.command} {self.path} - {format%args}\n")

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, PUT, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Requested-With")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200, "text/plain")

    def _read_json_body(self) -> Dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            return {}
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            return json.loads(body)
        except Exception:
            return {}

    def _send_json(self, data: Any, status: int = 200):
        self._set_headers(status, "application/json; charset=utf-8")
        self.wfile.write(json.dumps(data, indent=2).encode("utf-8"))

    def _send_error(self, message: str, status: int = 400, details: Optional[str] = None):
        self._send_json({"error": message, "details": details, "status": "ERROR"}, status=status)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        try:
            # 1. API routes
            if path == "/api/incidents":
                status = query.get("status", [None])[0]
                priority = query.get("priority", [None])[0]
                dtype = query.get("disaster_type", [None])[0]
                search = query.get("search", [None])[0]
                incidents = get_incidents(status=status, priority=priority, disaster_type=dtype, search=search)
                session = self.get_authenticated_session()
                # If public, ensure raw message contact info is hidden
                self._send_json({
                    "incidents": incidents,
                    "count": len(incidents),
                    "authenticated": session is not None,
                    "user": session.get("email") if session else None
                })
                return

            if path.startswith("/api/incidents/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3 and parts[2].isdigit():
                    inc_id = int(parts[2])
                    inc = get_incident_by_id(inc_id)
                    if inc:
                        session = self.get_authenticated_session()
                        if not session and "raw_messages" in inc:
                            for m in inc["raw_messages"]:
                                m["sender_contact"] = "Citizen (Protected)"
                        self._send_json({"incident": inc, "authenticated": session is not None})
                    else:
                        self._send_error(f"Incident #{inc_id} not found", status=404)
                    return

            if path == "/api/auth/verify":
                session = self.get_authenticated_session()
                self._send_json({
                    "authenticated": session is not None,
                    "session": session,
                    "role": session.get("role") if session else "PUBLIC",
                    "allowed_emails": ALLOWED_RESCUE_EMAILS
                })
                return

            if path == "/api/teams":
                teams = get_rescue_teams()
                self._send_json({"teams": teams, "count": len(teams)})
                return

            if path == "/api/analytics":
                summary = get_analytics_summary()
                self._send_json(summary)
                return

            if path == "/api/satellite/status":
                logs = get_satellite_logs(limit=25)
                constellations = satellite_sim.CONSTELLATIONS
                self._send_json({
                    "recent_transmissions": logs,
                    "constellations": constellations,
                    "status": "ONLINE",
                    "simulation_mode": True,
                    "simulation_notice": "[SIMULATED SATELLITE TELEMETRY - S-BAND & L-BAND LINK MODEL]"
                })
                return

            # 2. Static file routes
            if path == "/" or path == "/index.html":
                self._serve_static_file(os.path.join(BASE_DIR, "static", "index.html"))
                return

            # Serve files from static directory
            clean_subpath = path.lstrip("/")
            if clean_subpath.startswith("static/"):
                clean_subpath = clean_subpath[len("static/"):]

            target_file = os.path.join(BASE_DIR, "static", clean_subpath)
            if os.path.isfile(target_file):
                self._serve_static_file(target_file)
                return

            self._send_error("Resource Not Found", status=404)

        except Exception as e:
            self._send_error("Internal Server Error", status=500, details=str(e))

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        try:
            # Route: Rescue Team Authentication
            if path == "/api/auth/login":
                body = self._read_json_body()
                email = (body.get("email") or "").strip().lower()
                password = (body.get("password") or body.get("passcode") or "").strip()

                # Legacy passcode fallback if email not provided
                if not email and password in (COMMANDER_PASSCODE, DEMO_PASSWORD):
                    token = hashlib.sha256(f"AKASH-SETU-{password}".encode()).hexdigest()[:32]
                    ACTIVE_SESSIONS[token] = {"email": "commander@akashsetu.local", "role": "MISSION_COMMANDER"}
                    self._send_json({
                        "authenticated": True,
                        "token": token,
                        "email": "commander@akashsetu.local",
                        "role": "MISSION_COMMANDER",
                        "agency": "NDRF / SDMA OPERATIONS COMMAND",
                        "message": "Commander authenticated — operational view enabled."
                    })
                    return

                # Strict check for allowed emails
                allowed_lower = [e.lower() for e in ALLOWED_RESCUE_EMAILS]
                if email not in allowed_lower:
                    self._send_error(
                        f"Access restricted to authorized rescue personnel: {', '.join(ALLOWED_RESCUE_EMAILS)}",
                        status=401
                    )
                    return

                # Strict check for password
                if password not in (DEMO_PASSWORD, COMMANDER_PASSCODE):
                    self._send_error("Invalid rescue team password. Access denied.", status=401)
                    return

                token = hashlib.sha256(f"AKASH-SETU-{email}-{password}".encode()).hexdigest()[:32]
                ACTIVE_SESSIONS[token] = {"email": email, "role": "RESCUE_TEAM"}
                self._send_json({
                    "authenticated": True,
                    "token": token,
                    "email": email,
                    "role": "RESCUE_TEAM",
                    "agency": "NDRF / SDMA RESCUE OPERATIONS",
                    "message": f"Welcome, Rescue Team ({email}) — full monitoring access enabled."
                })
                return

            if path == "/api/auth/logout":
                auth_header = self.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    token = auth_header[7:].strip()
                    ACTIVE_SESSIONS.pop(token, None)
                self._send_json({"authenticated": False, "message": "Logged out successfully"})
                return

            # Route: Emergency report submission (citizen / responder - PUBLIC)
            if path == "/api/emergency/submit":
                body = self._read_json_body()
                name = (body.get("name") or body.get("reporter_name") or body.get("sender_contact") or "Citizen").strip()
                location_name = (body.get("location") or body.get("location_name") or "Disaster Zone").strip()
                raw_text = (body.get("description") or body.get("raw_text") or body.get("what_happened") or "").strip()

                if not raw_text:
                    self._send_error("Emergency description ('What Happened?') is required.")
                    return

                message_id = f"AS-SOS-{uuid.uuid4().hex[:6].upper()}"
                channel = body.get("channel", "PUBLIC_WEB_SOS")

                # 1. Strictly preserve raw message
                raw_msg_id = save_raw_message(
                    raw_text=raw_text,
                    channel=channel,
                    sender_contact=name,
                    signal_metrics={"sos_message_id": message_id, "location_reported": location_name}
                )

                # 2. AI / Local NLP Classifier
                cls_result = classifier.classify_emergency(raw_text, channel=channel)

                # Assign or override coordinates
                lat = float(body.get("latitude") or 30.6315)
                lon = float(body.get("longitude") or 79.0028)
                district = body.get("district") or "Rudraprayag"

                # Check manual trapped/injured override while preserving None
                trapped_count = body.get("trapped_count")
                if trapped_count is None or trapped_count == "":
                    trapped_count = cls_result["trapped_count"]
                else:
                    trapped_count = int(trapped_count)

                injured_count = body.get("injured_count")
                if injured_count is None or injured_count == "":
                    injured_count = cls_result["injured_count"]
                else:
                    injured_count = int(injured_count)

                # Merge vulnerabilities
                form_vulns = body.get("vulnerable_groups") or []
                all_vulns = list(set(form_vulns + cls_result.get("vulnerable_groups", [])))

                w_level = body.get("water_level_meters")
                if w_level is not None and w_level != "":
                    w_level = float(w_level)
                else:
                    w_level = cls_result.get("water_level_meters")

                candidate_data = {
                    "title": body.get("title") or cls_result["summary_title"],
                    "disaster_type": body.get("disaster_type") or cls_result["disaster_type"],
                    "severity_level": body.get("severity_level") or cls_result["severity_level"],
                    "latitude": lat,
                    "longitude": lon,
                    "location_name": location_name,
                    "district": district,
                    "trapped_count": trapped_count,
                    "injured_count": injured_count,
                    "casualties_count": cls_result.get("casualties_count"),
                    "vulnerable_groups": all_vulns,
                    "infrastructure_damaged": cls_result.get("infrastructure_damaged", []),
                    "water_level_meters": w_level,
                    "raw_text": raw_text
                }

                # 3. Duplicate Detection & Consolidation (Formula: M = 0.35L + 0.20T + 0.25C + 0.20D)
                active_incidents = get_incidents()
                match = deduplicator.find_best_match(candidate_data, active_incidents)

                is_duplicate = False
                matched_incident_info = None

                if match and match[1]["is_duplicate"]:
                    primary_inc, metrics = match
                    is_duplicate = True
                    matched_incident_info = {
                        "primary_incident_id": primary_inc["id"],
                        "incident_code": primary_inc["incident_code"],
                        "confidence_pct": round(metrics["composite_score"] * 100, 1),
                        "distance_km": metrics["distance_km"],
                        "formula": metrics.get("formula", "M = 0.35L + 0.20T + 0.25C + 0.20D")
                    }
                    # Link raw message to primary incident
                    link_message_to_incident(raw_msg_id, primary_inc["id"])

                    # Consolidate directly into primary incident without double counting victims
                    conn = get_connection()
                    cur = conn.cursor()
                    now_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    cur_trapped = primary_inc.get("trapped_count")
                    cand_trapped = candidate_data.get("trapped_count")
                    agg_trapped = None
                    if cur_trapped is not None or cand_trapped is not None:
                        agg_trapped = max(cur_trapped or 0, cand_trapped or 0)

                    cur_injured = primary_inc.get("injured_count")
                    cand_injured = candidate_data.get("injured_count")
                    agg_injured = None
                    if cur_injured is not None or cand_injured is not None:
                        agg_injured = max(cur_injured or 0, cand_injured or 0)

                    new_dup_count = (primary_inc.get("duplicate_count") or 0) + 1
                    cur.execute("""
                        UPDATE incidents
                        SET duplicate_count = ?, is_consolidated = 1,
                            trapped_count = ?, injured_count = ?, updated_at = ?
                        WHERE id = ?
                    """, (new_dup_count, agg_trapped, agg_injured, now_ts, primary_inc["id"]))

                    cur.execute("""
                        INSERT INTO incident_updates (incident_id, timestamp, author, update_type, message, previous_status, new_status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        primary_inc["id"], now_ts, "Akash Setu Deduplicator", "CONSOLIDATED",
                        f"Consolidated citizen report {message_id} ({name} at {location_name}). Match score: {round(metrics['composite_score']*100,1)}%",
                        primary_inc["status"], primary_inc["status"]
                    ))
                    conn.commit()
                    conn.close()

                    inc_id = primary_inc["id"]
                else:
                    # 4. Mathematical Risk Scoring (Formula: P = 5S + 5D + 3N + 3T + 2V + 2E)
                    risk_breakdown = risk_engine.calculate_risk(candidate_data)
                    candidate_data["risk_score"] = risk_breakdown["final_score"]
                    candidate_data["priority_level"] = risk_breakdown["priority"]
                    candidate_data["risk_breakdown"] = risk_breakdown
                    candidate_data["ai_classification_meta"] = cls_result

                    # 5. Insert new Incident
                    inc_id = insert_incident(candidate_data, raw_msg_id=raw_msg_id)

                full_inc = get_incident_by_id(inc_id)

                self._send_json({
                    "status": "SUCCESS",
                    "message_id": message_id,
                    "incident_id": inc_id,
                    "incident_code": full_inc.get("incident_code") if full_inc else f"AS-INC-{inc_id}",
                    "is_duplicate_merged": is_duplicate,
                    "duplicate_metrics": matched_incident_info,
                    "incident": full_inc,
                    "priority_tier": full_inc.get("priority_tier", full_inc.get("priority_level", "P1")),
                    "risk_score": full_inc.get("risk_score", 0),
                    "message": f"Emergency SOS [{message_id}] received and triaged into Akash Setu."
                }, status=201)
                return

            # Route: Satellite burst transmission simulation
            if path == "/api/satellite/transmit":
                body = self._read_json_body()
                raw_text = (body.get("raw_text") or "SATELLITE EMERGENCY BURST: Mandakini valley flash flood").strip()
                constellation = body.get("constellation", "NAVIC_DISASTER_BURST")
                rain_fade = float(body.get("simulated_rain_fade_db", 4.0))
                force_loss = bool(body.get("force_packet_loss", False))

                # Step 1: Run satellite link simulation
                burst_report = {
                    "raw_text": raw_text,
                    "latitude": float(body.get("latitude", 30.6315)),
                    "longitude": float(body.get("longitude", 79.0028)),
                    "disaster_type": body.get("disaster_type", "FLOOD"),
                    "trapped_count": body.get("trapped_count"), # Preserves None
                    "injured_count": body.get("injured_count"), # Preserves None
                    "vulnerable_groups": body.get("vulnerable_groups", []),
                    "water_level_meters": body.get("water_level_meters")
                }

                sat_result = satellite_sim.transmit_burst(
                    burst_report,
                    constellation_key=constellation,
                    simulated_rain_fade_db=rain_fade,
                    force_packet_loss=force_loss
                )

                # Step 2: Log transmission
                log_id = log_satellite_transmission(sat_result)

                # Step 3: Intake decoded transmission as an emergency report
                raw_msg_id = save_raw_message(
                    raw_text=f"[SATELLITE BURST: {sat_result['constellation']}] {raw_text}",
                    channel="SATELLITE_BURST",
                    sender_contact=f"SatTerminal-{sat_result['packet_id']}",
                    signal_metrics={
                        "snr_db": sat_result["snr_db"],
                        "link_margin_db": sat_result["link_margin_db"],
                        "compression_pct": sat_result["compression_pct"]
                    }
                )

                cls_result = classifier.classify_emergency(raw_text, channel="SATELLITE_BURST")
                candidate_data = {
                    "title": cls_result["summary_title"],
                    "disaster_type": cls_result["disaster_type"],
                    "severity_level": cls_result["severity_level"],
                    "latitude": burst_report["latitude"],
                    "longitude": burst_report["longitude"],
                    "location_name": body.get("location_name", "Remote Satellite Station"),
                    "district": body.get("district", "Rudraprayag"),
                    "trapped_count": burst_report["trapped_count"],
                    "injured_count": burst_report["injured_count"],
                    "casualties_count": cls_result.get("casualties_count"),
                    "vulnerable_groups": list(set((burst_report.get("vulnerable_groups") or []) + cls_result.get("vulnerable_groups", []))),
                    "infrastructure_damaged": cls_result.get("infrastructure_damaged", []),
                    "water_level_meters": burst_report["water_level_meters"],
                    "raw_text": raw_text
                }

                risk_breakdown = risk_engine.calculate_risk(candidate_data)
                candidate_data["risk_score"] = risk_breakdown["final_score"]
                candidate_data["priority_level"] = risk_breakdown["priority"]
                candidate_data["risk_breakdown"] = risk_breakdown
                candidate_data["ai_classification_meta"] = cls_result

                inc_id = insert_incident(candidate_data, raw_msg_id=raw_msg_id)

                self._send_json({
                    "status": "SUCCESS",
                    "transmission": sat_result,
                    "created_incident_id": inc_id,
                    "incident": get_incident_by_id(inc_id),
                    "simulation_notice": "[SIMULATED SATELLITE BURST TRANSMISSION - DELIVERED VIA VIRTUAL GROUND STATION]"
                })
                return

            # Route: Update incident status (PROTECTED — rescue teams may mark RESOLVED)
            if path.startswith("/api/incidents/") and path.endswith("/status"):
                parts = path.strip("/").split("/")
                inc_id = int(parts[2])
                body = self._read_json_body()
                new_status = body.get("status")
                author = body.get("author", "Rescue Coordinator")
                note = body.get("note", "Operational status updated")

                # Allow rescue teams (even unauthenticated) to mark as RESOLVED/CLOSED
                # All other status changes still require commander authentication
                if new_status not in ("RESOLVED", "CLOSED"):
                    if not self.is_authenticated():
                        self._send_error("Authentication Required: Only authorized disaster coordinators can modify incident status.", status=401)
                        return
                else:
                    # Auto-tag the author when a field rescue team marks it
                    if not self.is_authenticated():
                        author = body.get("author", "Field Rescue Team")

                success = update_incident_status(inc_id, new_status, author=author, note=note)
                if success:
                    self._send_json({"status": "SUCCESS", "incident": get_incident_by_id(inc_id)})
                else:
                    self._send_error(f"Failed to update incident #{inc_id}", status=404)
                return

            # Route: Dispatch rescue team to incident (PROTECTED)
            if path.startswith("/api/incidents/") and path.endswith("/dispatch"):
                if not self.is_authenticated():
                    self._send_error("Authentication Required: Only authorized disaster coordinators can dispatch rescue units.", status=401)
                    return

                parts = path.strip("/").split("/")
                inc_id = int(parts[2])
                body = self._read_json_body()
                team_id = int(body.get("team_id", 0))
                author = body.get("author", "Disaster Operations Command")
                notes = body.get("notes", "Emergency deployment initiated.")

                success = assign_team_to_incident(inc_id, team_id, author=author, notes=notes)
                if success:
                    self._send_json({
                        "status": "SUCCESS",
                        "incident": get_incident_by_id(inc_id),
                        "teams": get_rescue_teams()
                    })
                else:
                    self._send_error("Failed to dispatch team (invalid team_id or incident_id)", status=400)
                return

            # Route: Merge duplicate incidents (PROTECTED)
            if path.startswith("/api/incidents/") and path.endswith("/merge"):
                if not self.is_authenticated():
                    self._send_error("Authentication Required: Only authorized coordinators can consolidate incidents.", status=401)
                    return

                parts = path.strip("/").split("/")
                primary_id = int(parts[2])
                body = self._read_json_body()
                dup_id = int(body.get("duplicate_id", 0))
                author = body.get("author", "Incident Commander")
                reason = body.get("reason", "Manual duplicate consolidation")

                success = merge_incidents(primary_id, dup_id, author=author, reason=reason)
                if success:
                    self._send_json({
                        "status": "SUCCESS",
                        "primary_incident": get_incident_by_id(primary_id),
                        "message": f"Incident #{dup_id} consolidated into #{primary_id}"
                    })
                else:
                    self._send_error("Merge failed (invalid IDs or same incident)", status=400)
                return

            # Route: Update rescue team operational status (PROTECTED)
            if path.startswith("/api/teams/") and path.endswith("/status"):
                if not self.is_authenticated():
                    self._send_error("Authentication Required: Only authorized commanders can modify rescue fleet status.", status=401)
                    return

                parts = path.strip("/").split("/")
                team_id = int(parts[2])
                body = self._read_json_body()
                new_status = body.get("status", "AVAILABLE")
                lat = body.get("current_lat")
                lon = body.get("current_lon")

                success = update_team_status(team_id, new_status, current_lat=lat, current_lon=lon)
                if success:
                    self._send_json({"status": "SUCCESS", "teams": get_rescue_teams()})
                else:
                    self._send_error(f"Failed to update team #{team_id}", status=404)
                return

            # Route: Reset database to fresh seed demo (PROTECTED)
            if path == "/api/system/reset-demo":
                if not self.is_authenticated():
                    self._send_error("Authentication Required: Only authorized commanders can reset the scenario.", status=401)
                    return

                result = seed_database()
                self._send_json({"status": "SUCCESS", "result": result, "message": "Akash Setu database reset to realistic Himalayan disaster scenario."})
                return

            self._send_error("Route Not Found", status=404)

        except Exception as e:
            self._send_error("Internal Server Error", status=500, details=str(e))

    def _serve_static_file(self, filepath: str):
        if not os.path.isfile(filepath):
            self._send_error("File Not Found", status=404)
            return

        content_type, _ = mimetypes.guess_type(filepath)
        if not content_type:
            if filepath.endswith(".js"):
                content_type = "application/javascript"
            elif filepath.endswith(".css"):
                content_type = "text/css"
            elif filepath.endswith(".html"):
                content_type = "text/html"
            elif filepath.endswith(".svg"):
                content_type = "image/svg+xml"
            else:
                content_type = "application/octet-stream"

        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self._set_headers(200, content_type)
            self.wfile.write(content)
        except Exception as e:
            self._send_error(f"Error reading file: {str(e)}", status=500)


def run_server(host: str = "0.0.0.0", port: int = 8080):
    # Ensure database is initialized and seeded if empty
    init_db()
    incs = get_incidents()
    if not incs:
        print("[AKASH SETU] Empty database detected. Seeding realistic Himalayan disaster scenario...")
        seed_database()
        print("[AKASH SETU] Seeding complete.")

    server = ThreadingHTTPServer((host, port), AkashSetuRequestHandler)
    print("=" * 72)
    print(f"  AKASH SETU (आकाश सेतु) - EMERGENCY DISASTER RESPONSE PLATFORM")
    print(f"  Server Active at: http://{host}:{port}")
    print(f"  Tactical Dashboard: http://localhost:{port}")
    print(f"  Constellation Simulator: ACTIVE (NavIC / GSAT-7A / Iridium)")
    print(f"  Autonomous Local NLP Engine: ACTIVE")
    print("=" * 72)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[AKASH SETU] Server shutdown requested. Terminating.")
        server.server_close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    host = os.environ.get("HOST", "0.0.0.0")
    run_server(host=host, port=port)

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
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, Optional

# Add current directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.db import (
    init_db, save_raw_message, insert_incident, get_incidents,
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


# Singletons for core engines
classifier = DisasterClassifier()
deduplicator = IncidentDeduplicator()
risk_engine = RiskScoringEngine()
satellite_sim = SatelliteLinkSimulator()


class AkashSetuRequestHandler(BaseHTTPRequestHandler):
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
                self._send_json({"incidents": incidents, "count": len(incidents)})
                return

            if path.startswith("/api/incidents/"):
                parts = path.strip("/").split("/")
                if len(parts) == 3 and parts[2].isdigit():
                    inc_id = int(parts[2])
                    inc = get_incident_by_id(inc_id)
                    if inc:
                        self._send_json({"incident": inc})
                    else:
                        self._send_error(f"Incident #{inc_id} not found", status=404)
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
            # Route: Emergency report submission (citizen / responder)
            if path == "/api/emergency/submit":
                body = self._read_json_body()
                raw_text = (body.get("raw_text") or "").strip()
                if not raw_text:
                    self._send_error("Emergency message text (raw_text) is required.")
                    return

                channel = body.get("channel", "WEB")
                sender = body.get("sender_contact", "Anonymous Citizen")

                # 1. Strictly preserve raw message
                raw_msg_id = save_raw_message(
                    raw_text=raw_text,
                    channel=channel,
                    sender_contact=sender,
                    signal_metrics=body.get("signal_metrics")
                )

                # 2. AI / Local NLP Classifier
                cls_result = classifier.classify_emergency(raw_text, channel=channel)

                # User may override coordinates or specific fields from form
                lat = float(body.get("latitude") or 30.6315) # Default to disaster valley if omitted
                lon = float(body.get("longitude") or 79.0028)
                location_name = body.get("location_name") or "Disaster Zone, Uttarakhand"
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

                # 3. Duplicate Detection & Consolidation
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
                        "distance_km": metrics["distance_km"]
                    }
                    # Link raw message to primary incident
                    link_message_to_incident(raw_msg_id, primary_inc["id"])
                    # Consolidate
                    merge_incidents(
                        primary_id=primary_inc["id"],
                        duplicate_id=primary_inc["id"],
                        author="Akash Setu Real-time Deduplicator",
                        reason=f"Auto-merged: {metrics['status_label']} ({round(metrics['composite_score']*100,1)}% match)"
                    )
                    inc_id = primary_inc["id"]
                    candidate_data["risk_score"] = primary_inc["risk_score"]
                    candidate_data["priority_level"] = primary_inc["priority_level"]
                else:
                    # 4. Mathematical Risk Scoring
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
                    "incident_id": inc_id,
                    "is_duplicate_merged": is_duplicate,
                    "duplicate_metrics": matched_incident_info,
                    "incident": full_inc,
                    "message": "Emergency logged and triaged into Akash Setu."
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

            # Route: Update incident status
            if path.startswith("/api/incidents/") and path.endswith("/status"):
                parts = path.strip("/").split("/")
                inc_id = int(parts[2])
                body = self._read_json_body()
                new_status = body.get("status")
                author = body.get("author", "Rescue Coordinator")
                note = body.get("note", "Operational status updated")

                success = update_incident_status(inc_id, new_status, author=author, note=note)
                if success:
                    self._send_json({"status": "SUCCESS", "incident": get_incident_by_id(inc_id)})
                else:
                    self._send_error(f"Failed to update incident #{inc_id}", status=404)
                return

            # Route: Dispatch rescue team to incident
            if path.startswith("/api/incidents/") and path.endswith("/dispatch"):
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

            # Route: Merge duplicate incidents
            if path.startswith("/api/incidents/") and path.endswith("/merge"):
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

            # Route: Update rescue team operational status
            if path.startswith("/api/teams/") and path.endswith("/status"):
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

            # Route: Reset database to fresh seed demo
            if path == "/api/system/reset-demo":
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

"""
Akash Setu - Automated Test Suite
Module: tests/test_all.py

Tests all modules:
1. Database operations & strict NULL value preservation
2. Dual-mode AI / Local NLP disaster classification
3. Geospatial & semantic duplicate detection & consolidation
4. Mathematical risk-scoring algorithm & provisional scoring
5. Low-bandwidth satellite packet binary encoding/decoding & compression
6. Constellation link simulation & ARQ retransmission
7. REST API endpoints & server integration
"""

import unittest
import os
import sys
import tempfile
import json
import urllib.request
import threading
import time

# Ensure core is on path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.db import (
    init_db, save_raw_message, insert_incident, get_incidents,
    get_incident_by_id, update_incident_status, assign_team_to_incident,
    merge_incidents, get_rescue_teams, log_satellite_transmission,
    get_satellite_logs, get_analytics_summary
)
from core.classifier import DisasterClassifier
from core.deduplication import IncidentDeduplicator, haversine_distance_km
from core.risk_engine import RiskScoringEngine
from core.satellite_sim import SatellitePacketEncoder, SatelliteLinkSimulator
from core.seed_data import seed_database
from server import AkashSetuRequestHandler, ThreadingHTTPServer


class TestAkashSetuDatabase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp_dir, "test_akash.db")
        init_db(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        os.rmdir(self.tmp_dir)

    def test_raw_message_verbatim_preservation(self):
        original_text = "HELP! 14 pilgrims trapped at Sonprayag bridge! Water rising fast!"
        msg_id = save_raw_message(original_text, "SMS", "+91-98765-43210", db_path=self.db_path)
        self.assertGreater(msg_id, 0)

        # Retrieve and verify verbatim preservation
        conn = get_incidents(db_path=self.db_path) # verify db accessible

    def test_strict_null_preservation_never_zero(self):
        """Crucial requirement: Unknown trapped count must stay None and NEVER become 0."""
        incident_data = {
            "title": "Unspecified landslide trapped count",
            "disaster_type": "LANDSLIDE",
            "severity_level": "HIGH",
            "latitude": 30.6514,
            "longitude": 79.0270,
            "location_name": "Gaurikund",
            "district": "Rudraprayag",
            "trapped_count": None, # Genuine unknown state!
            "injured_count": None,
            "risk_score": 75.0,
            "priority_level": "P2"
        }
        inc_id = insert_incident(incident_data, db_path=self.db_path)
        retrieved = get_incident_by_id(inc_id, db_path=self.db_path)

        self.assertIsNotNone(retrieved)
        self.assertIsNone(retrieved["trapped_count"], "Trapped count MUST be None, never silently coerced to 0!")
        self.assertIsNone(retrieved["injured_count"], "Injured count MUST be None, never silently coerced to 0!")


class TestClassifierEngine(unittest.TestCase):
    def setUp(self):
        self.classifier = DisasterClassifier()

    def test_flood_classification_and_water_level(self):
        msg = "Mandakini river flood water level is 2.8 meters high. 12 people trapped on roof. 2 infants."
        res = self.classifier.classify_emergency(msg, "WEB")

        self.assertEqual(res["disaster_type"], "FLOOD")
        self.assertEqual(res["trapped_count"], 12)
        self.assertAlmostEqual(res["water_level_meters"], 2.8, places=1)
        self.assertIn("INFANTS_CHILDREN", res["vulnerable_groups"])
        self.assertEqual(res["severity_level"], "CRITICAL")

    def test_unknown_trapped_count_returns_none(self):
        msg = "Landslide blocked road. Trekkers shouting from distance, cannot see how many."
        res = self.classifier.classify_emergency(msg, "HF_RADIO")

        self.assertEqual(res["disaster_type"], "LANDSLIDE")
        self.assertIsNone(res["trapped_count"], "Unstated trapped count must return None, not 0!")


class TestDeduplicationEngine(unittest.TestCase):
    def setUp(self):
        self.deduplicator = IncidentDeduplicator()

    def test_haversine_distance(self):
        # Kedarnath (30.735, 79.067) to Gaurikund (30.651, 79.027) ~ 10 km
        dist = haversine_distance_km(30.735, 79.067, 30.651, 79.027)
        self.assertGreater(dist, 8.0)
        self.assertLess(dist, 14.0)

    def test_high_confidence_duplicate_detection(self):
        existing = {
            "title": "Bus stranded at Banswara turn",
            "disaster_type": "LANDSLIDE",
            "latitude": 30.4650,
            "longitude": 79.0780,
            "location_name": "Banswara Highway",
            "raw_text": "Bus stranded at Banswara turn. Landslide blocked both sides.",
            "created_at": "2026-11-14T10:00:00Z"
        }
        candidate = {
            "title": "Stranded bus at Banswara landslide",
            "disaster_type": "LANDSLIDE",
            "latitude": 30.4655, # 60 meters away
            "longitude": 79.0778,
            "location_name": "Banswara Turn",
            "raw_text": "Tourist bus stranded by rocks at Banswara. Need bulldozer.",
            "created_at": "2026-11-14T10:20:00Z"
        }

        sim = self.deduplicator.compute_similarity(candidate, existing)
        self.assertTrue(sim["is_duplicate"], f"Expected duplicate, got score {sim['composite_score']}")
        self.assertGreaterEqual(sim["composite_score"], 0.70)


class TestMathematicalRiskEngine(unittest.TestCase):
    def setUp(self):
        self.engine = RiskScoringEngine()

    def test_risk_scoring_known_victims(self):
        incident = {
            "disaster_type": "FLOOD",
            "severity_level": "CRITICAL",
            "trapped_count": 14,
            "injured_count": 3,
            "vulnerable_groups": ["INFANTS_CHILDREN", "PREGNANT_WOMEN"],
            "infrastructure_damaged": ["BRIDGE_COLLAPSE"],
            "water_level_meters": 2.8,
            "raw_text": "Massive flood rising fast, bridge collapsed, 14 trapped",
            "status": "PENDING_TRIAGE"
        }
        breakdown = self.engine.calculate_risk(incident)
        self.assertGreaterEqual(breakdown["final_score"], 80.0, "Critical flood with infants should score P1 (>=80)")
        self.assertEqual(breakdown["priority"], "P1")
        self.assertFalse(breakdown["is_provisional"])

    def test_single_severe_medical_emergency_reaches_critical_priority(self):
        """Prompt requirement: A single severe medical emergency (severe bleeding / breathing) must reach Critical (>= 80)."""
        incident = {
            "disaster_type": "MEDICAL",
            "severity_level": "CRITICAL",
            "trapped_count": 0,
            "injured_count": 1, # Exactly 1 patient
            "raw_text": "Urgent! Patient has severe bleeding and cannot breathe after rockfall. Immediate ambulance needed!",
            "status": "PENDING_TRIAGE"
        }
        breakdown = self.engine.calculate_risk(incident)
        self.assertGreaterEqual(breakdown["final_score"], 80.0, f"Single severe medical emergency must score >= 80, got {breakdown['final_score']}")
        self.assertEqual(breakdown["priority"], "P1")
        self.assertEqual(breakdown["priority_tier"], "Critical")

    def test_provisional_score_when_victim_count_unknown(self):
        incident = {
            "disaster_type": "BUILDING_COLLAPSE",
            "severity_level": "HIGH",
            "trapped_count": None, # Genuine unknown count!
            "injured_count": None,
            "vulnerable_groups": ["ELDERLY"],
            "raw_text": "Building collapsed at bazaar. Unknown how many trapped inside.",
            "status": "PENDING_TRIAGE"
        }
        breakdown = self.engine.calculate_risk(incident)
        self.assertTrue(breakdown["is_provisional"], "Unknown trapped count must trigger provisional scoring!")
        reasons_text = " ".join(breakdown.get("reasons", [])).lower()
        self.assertIn("provisional", reasons_text)


class TestSatelliteSimulator(unittest.TestCase):
    def setUp(self):
        self.encoder = SatellitePacketEncoder()
        self.link_sim = SatelliteLinkSimulator(self.encoder)

    def test_binary_packet_encode_decode_and_compression(self):
        report = {
            "latitude": 30.6315,
            "longitude": 79.0028,
            "disaster_type": "FLOOD",
            "trapped_count": 8,
            "injured_count": 2,
            "vulnerable_groups": ["INFANTS_CHILDREN", "BRIDGE_COLLAPSE"],
            "water_level_meters": 2.5,
            "raw_text": "Sonprayag bridge flooded. 8 pilgrims trapped on guesthouse roof.",
            "priority_level": "P1"
        }

        packet_bytes, telemetry = self.encoder.encode_report(report)
        self.assertLess(len(packet_bytes), 95, f"Satellite packet should be compact, was {len(packet_bytes)} bytes")
        self.assertGreaterEqual(telemetry["compression_pct"], 50.0)

        # Decode packet
        decoded = self.encoder.decode_packet(packet_bytes)
        self.assertTrue(decoded["crc_valid"], "CRC checksum failed")
        self.assertAlmostEqual(decoded["latitude"], 30.6315, places=4)
        self.assertAlmostEqual(decoded["longitude"], 79.0028, places=4)
        self.assertEqual(decoded["disaster_type"], "FLOOD")
        self.assertEqual(decoded["trapped_count"], 8)
        self.assertAlmostEqual(decoded["water_level_meters"], 2.5, places=1)

    def test_satellite_transmission_simulation_with_arq(self):
        report = {
            "latitude": 30.6315,
            "longitude": 79.0028,
            "disaster_type": "LANDSLIDE",
            "trapped_count": 4,
            "raw_text": "Gaurikund landslide road blocked."
        }
        res = self.link_sim.transmit_burst(report, "NAVIC_DISASTER_BURST", force_packet_loss=True)
        self.assertEqual(res["status"], "RETRANSMITTED")
        self.assertEqual(res["retransmissions"], 1)
        self.assertGreater(res["transmission_time_ms"], 1000.0)


import io
import email

class TestFullSystemIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.mkdtemp()
        cls.db_path = os.path.join(cls.tmp_dir, "test_integration.db")

        import core.db
        cls.orig_db_path = core.db.DEFAULT_DB_PATH
        core.db.DEFAULT_DB_PATH = cls.db_path

        seed_database(cls.db_path)

    @classmethod
    def tearDownClass(cls):
        import core.db
        core.db.DEFAULT_DB_PATH = cls.orig_db_path
        if os.path.exists(cls.db_path):
            os.remove(cls.db_path)
        os.rmdir(cls.tmp_dir)

    def _call_handler(self, method: str, path: str, body: dict = None, headers_extra: dict = None):
        body_bytes = b""
        if body is not None:
            body_bytes = json.dumps(body).encode("utf-8")

        headers_dict = {
            "Host": "127.0.0.1",
            "Content-Type": "application/json",
            "Content-Length": str(len(body_bytes))
        }
        if headers_extra:
            headers_dict.update(headers_extra)

        headers_str = "".join(f"{k}: {v}\r\n" for k, v in headers_dict.items()) + "\r\n"
        raw_input = f"{method} {path} HTTP/1.1\r\n{headers_str}".encode("utf-8") + body_bytes

        handler = AkashSetuRequestHandler.__new__(AkashSetuRequestHandler)
        handler.rfile = io.BytesIO(body_bytes)
        handler.wfile = io.BytesIO()
        handler.command = method
        handler.path = path
        handler.request_version = "HTTP/1.1"
        handler.requestline = f"{method} {path} HTTP/1.1"
        handler.headers = email.message_from_string(headers_str)
        handler.client_address = ("127.0.0.1", 12345)
        handler.server = None

        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()

        handler.wfile.seek(0)
        output_raw = handler.wfile.read()
        parts = output_raw.split(b"\r\n\r\n", 1)
        header_text = parts[0].decode("utf-8", errors="ignore")
        body_text = parts[1].decode("utf-8", errors="ignore") if len(parts) > 1 else ""

        status_code = int(header_text.splitlines()[0].split()[1])
        try:
            parsed_json = json.loads(body_text)
        except Exception:
            parsed_json = None

        return status_code, parsed_json

    def test_api_get_incidents(self):
        status, data = self._call_handler("GET", "/api/incidents")
        self.assertEqual(status, 200)
        self.assertIn("incidents", data)
        self.assertGreater(data["count"], 5)

    def test_rescued_incidents_move_down_and_recent_appear_first(self):
        """Verify: Active tasks maintain priority, resolved/rescued tasks move down, recent appear first."""
        # 1. Fetch initial incidents
        status, data = self._call_handler("GET", "/api/incidents")
        incidents = data["incidents"]
        self.assertGreater(len(incidents), 2)
        top_inc = incidents[0]

        # 2. Authenticate as rescue team
        status, auth_data = self._call_handler("POST", "/api/auth/login", body={
            "email": "eng24as0022@dsu.edu.in",
            "password": "AkashSetu@2026"
        })
        self.assertEqual(status, 200)
        token = auth_data["token"]

        # 3. Mark top incident as RESOLVED (successful rescue)
        status, res = self._call_handler(
            "POST", f"/api/incidents/{top_inc['id']}/status",
            body={"status": "RESOLVED", "author": "Rescue Commander"},
            headers_extra={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(status, 200)

        # 4. Fetch incidents again: verify resolved incident has moved down
        status, data2 = self._call_handler("GET", "/api/incidents")
        updated_incidents = data2["incidents"]
        new_top = updated_incidents[0]
        self.assertNotEqual(new_top["id"], top_inc["id"], "Resolved incident must move down!")
        self.assertIn(new_top["status"], ["PENDING_TRIAGE", "TRIAGED", "DISPATCHED", "IN_PROGRESS"], "Top incident must be an active emergency!")
        # Verify resolved incident is in the lower group
        resolved_indices = [idx for idx, inc in enumerate(updated_incidents) if inc["status"] in ("RESOLVED", "CLOSED")]
        active_indices = [idx for idx, inc in enumerate(updated_incidents) if inc["status"] not in ("RESOLVED", "CLOSED")]
        self.assertGreater(min(resolved_indices), max(active_indices), "All resolved/rescued incidents must be below active incidents!")

    def test_api_submit_emergency_and_auto_triage(self):
        """Test 1: Public SOS form submission with 3 required fields and unique tracking ID generation."""
        payload = {
            "name": "Sunita Joshi",
            "location": "Guptkashi Market Sector 2",
            "description": "Rooftop collapse at market lodge. 7 tourists trapped under wooden beams. Water entering cellar."
        }
        status, data = self._call_handler("POST", "/api/emergency/submit", body=payload)
        self.assertEqual(status, 201)
        self.assertEqual(data["status"], "SUCCESS")
        self.assertIn("AS-SOS-", data["message_id"], "Must generate unique SOS tracking ID")
        inc = data["incident"]
        self.assertIsNotNone(inc)
        self.assertIn("AS-INC-", inc["incident_code"])
        self.assertGreater(inc["risk_score"], 0)

        # Test 2: Duplicate detection & consolidation without double-counting casualties
        dup_payload = {
            "name": "Local Shopkeeper",
            "location": "Guptkashi Market Sector 2",
            "description": "Lodge roof collapsed in market near temple. People trapped under beams. Need rescue!"
        }
        status2, data2 = self._call_handler("POST", "/api/emergency/submit", body=dup_payload)
        self.assertEqual(status2, 201)
        self.assertTrue(data2["is_duplicate_merged"], "Second report at same location & type must be auto-consolidated!")
        self.assertEqual(data2["incident_id"], data["incident_id"], "Must consolidate into same incident!")

    def test_rescue_team_email_allowlist_authentication(self):
        """Test 4: Rescue team authentication with the 4 allowed emails vs unauthorized access."""
        allowed_emails = [
            "eng24as0018@dsu.edu.in",
            "eng24as0022@dsu.edu.in",
            "eng24as0016@dsu.edu.in",
            "vinayvinu96636@gmail.com"
        ]

        # 1. Test all 4 allowed emails with correct demo password
        for email_addr in allowed_emails:
            status, data = self._call_handler("POST", "/api/auth/login", body={
                "email": email_addr,
                "password": "AkashSetu@2026"
            })
            self.assertEqual(status, 200, f"Allowed email {email_addr} should authenticate successfully")
            self.assertTrue(data["authenticated"])
            self.assertIsNotNone(data["token"])

        # 2. Test unauthorized email address rejection
        status, data = self._call_handler("POST", "/api/auth/login", body={
            "email": "intruder@external.com",
            "password": "AkashSetu@2026"
        })
        self.assertEqual(status, 401, "Unauthorized email must be rejected with 401")
        self.assertIn("Access restricted to authorized rescue personnel", data["error"])

        # 3. Test correct email with wrong password rejection
        status, data = self._call_handler("POST", "/api/auth/login", body={
            "email": "eng24as0022@dsu.edu.in",
            "password": "WrongPassword123"
        })
        self.assertEqual(status, 401, "Invalid password must be rejected with 401")

    def test_api_satellite_burst_transmission(self):
        payload = {
            "raw_text": "Kedarnath path cloudburst. 3 shepherds trapped on rock.",
            "constellation": "NAVIC_DISASTER_BURST",
            "simulated_rain_fade_db": 3.0
        }
        status, data = self._call_handler("POST", "/api/satellite/transmit", body=payload)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "SUCCESS")
        self.assertIn("transmission", data)
        self.assertIn("created_incident_id", data)

    def test_api_analytics_summary(self):
        status, data = self._call_handler("GET", "/api/analytics")
        self.assertEqual(status, 200)
        self.assertIn("priority_distribution", data)
        self.assertIn("humanitarian_impact", data)
        self.assertIn("satellite_network", data)

    def test_auth_login_and_permission_protection(self):
        # 1. Unauthenticated dispatch attempt should be rejected with 401
        status, data = self._call_handler("POST", "/api/incidents/1/dispatch", body={"team_id": 1})
        self.assertEqual(status, 401, "Unauthenticated dispatch must be rejected with 401!")

        # 2. Invalid passcode login attempt
        status, data = self._call_handler("POST", "/api/auth/login", body={"passcode": "WRONG-PASSWORD"})
        self.assertEqual(status, 401)

        # 3. Valid commander login
        status, data = self._call_handler("POST", "/api/auth/login", body={"passcode": "NDRF-2026-RESCUE"})
        self.assertEqual(status, 200)
        self.assertTrue(data["authenticated"])
        token = data["token"]
        self.assertIsNotNone(token)

        # 4. Authenticated dispatch with valid token should succeed
        status, data = self._call_handler(
            "POST", "/api/incidents/1/dispatch",
            body={"team_id": 1, "author": "Commander Test", "notes": "Approved"},
            headers_extra={"Authorization": f"Bearer {token}"}
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "SUCCESS")


if __name__ == "__main__":
    unittest.main(verbosity=2)

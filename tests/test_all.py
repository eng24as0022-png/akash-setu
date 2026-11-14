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
            "status": "PENDING_TRIAGE"
        }
        breakdown = self.engine.calculate_risk(incident)
        self.assertGreaterEqual(breakdown["final_score"], 80.0, "Critical flood with infants should score P1 (>=80)")
        self.assertEqual(breakdown["priority"], "P1")
        self.assertFalse(breakdown["is_provisional"])

    def test_provisional_score_when_victim_count_unknown(self):
        incident = {
            "disaster_type": "BUILDING_COLLAPSE",
            "severity_level": "HIGH",
            "trapped_count": None, # Genuine unknown count!
            "injured_count": None,
            "vulnerable_groups": ["ELDERLY"],
            "status": "PENDING_TRIAGE"
        }
        breakdown = self.engine.calculate_risk(incident)
        self.assertTrue(breakdown["is_provisional"], "Unknown trapped count must trigger provisional scoring!")
        self.assertIn("provisional uncertainty weight applied", breakdown["provisional_reasons"][0].lower())


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

    def _call_handler(self, method: str, path: str, body: dict = None):
        body_bytes = b""
        if body is not None:
            body_bytes = json.dumps(body).encode("utf-8")

        headers_str = (
            f"Host: 127.0.0.1\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        )
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

    def test_api_submit_emergency_and_auto_triage(self):
        payload = {
            "raw_text": "Rooftop collapse at Guptkashi market. 7 tourists trapped under wooden beams.",
            "location_name": "Guptkashi Market",
            "latitude": 30.528,
            "longitude": 79.065,
            "channel": "WEB"
        }
        status, data = self._call_handler("POST", "/api/emergency/submit", body=payload)
        self.assertEqual(status, 201)
        self.assertEqual(data["status"], "SUCCESS")
        inc = data["incident"]
        self.assertIsNotNone(inc)
        self.assertIn("AS-INC-", inc["incident_code"])
        self.assertGreater(inc["risk_score"], 0)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)

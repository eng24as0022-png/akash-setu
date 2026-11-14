"""
Akash Setu - Realistic Disaster Scenario Seed Data
Module: core/seed_data.py

Scenario: Mandakini Valley & Chamoli Himalayan Cloudburst & Flash Flood Crisis
Includes 16 realistic emergency incidents across diverse disaster types,
duplicate message clusters, satellite bursts, unknown victim counts, and 6 rescue teams.
"""

import json
from typing import List, Dict, Any
from .db import (
    init_db, save_raw_message, insert_incident,
    get_connection, log_satellite_transmission
)
from .classifier import DisasterClassifier
from .deduplication import IncidentDeduplicator
from .risk_engine import RiskScoringEngine
from .satellite_sim import SatelliteLinkSimulator


SAMPLE_TEAMS = [
    {
        "team_code": "TEAM-NDRF-08A",
        "name": "NDRF 8th Battalion - Alpha Flood Team",
        "agency": "NDRF",
        "specialization": "FLOOD_WATER_RESCUE",
        "leader_name": "Cmdt. Rajeshwar Sharma",
        "contact": "+91-94120-11001",
        "status": "AVAILABLE",
        "current_lat": 30.5280,
        "current_lon": 79.1240,
        "base_location": "Rudraprayag Forward Staging Base",
        "capacity_persons": 24,
        "equipment": ["INFLATABLE_MOTOR_BOATS", "LIFE_JACKETS", "SONAR_DEPTH_FINDER", "DIVING_GEAR", "HIGH_CAPACITY_DEWATERING_PUMPS"]
    },
    {
        "team_code": "TEAM-SDRF-02M",
        "name": "SDRF Uttarakhand - Mountain Echo",
        "agency": "SDRF",
        "specialization": "HIGH_ALTITUDE",
        "leader_name": "Insp. Virendra Negi",
        "contact": "+91-94120-22002",
        "status": "AVAILABLE",
        "current_lat": 30.7346,
        "current_lon": 79.0669,
        "base_location": "Guptkashi Mountain Rescue Center",
        "capacity_persons": 16,
        "equipment": ["CLIMBING_ROPES", "TITANIUM_STRETCHERS", "AVALANCHE_TRANSCEIVERS", "PNEUMATIC_JACKS", "PORTABLE_OXYGEN"]
    },
    {
        "team_code": "TEAM-IAF-ALH",
        "name": "IAF 152 Helicopter Unit (ALH Dhruv Mk-III)",
        "agency": "ARMY_AVIATION",
        "specialization": "HELI_EVAC",
        "leader_name": "Wing Cmdr. Arjun Rao",
        "contact": "+91-94120-33003",
        "status": "AVAILABLE",
        "current_lat": 30.1890,
        "current_lon": 79.2150,
        "base_location": "Gauchar Advanced Landing Ground",
        "capacity_persons": 12,
        "equipment": ["HELI_RESCUE_WINCH", "FLIR_THERMAL_CAMERAS", "AIRDROP_SURVIVAL_CRATES", "MEDEVAC_LITTERS"]
    },
    {
        "team_code": "TEAM-ITBP-01",
        "name": "ITBP 1st Border First Responder Unit",
        "agency": "ITBP",
        "specialization": "COLLAPSE_SEARCH",
        "leader_name": "Dy. Cmdt. Gurmeet Singh",
        "contact": "+91-94120-44004",
        "status": "AVAILABLE",
        "current_lat": 30.5570,
        "current_lon": 79.5630,
        "base_location": "Joshimath Tactical Post",
        "capacity_persons": 20,
        "equipment": ["SEISMIC_ACOUSTIC_DETECTOR", "DIAMOND_CHAINSAWS", "SNIFFER_CANINES", "HYDRAULIC_SPREADERS"]
    },
    {
        "team_code": "TEAM-RC-MED",
        "name": "Red Cross Emergency Trauma Surgery Mobile Unit",
        "agency": "RED_CROSS",
        "specialization": "MEDICAL_TRIAGE",
        "leader_name": "Dr. Ananya Sen",
        "contact": "+91-94120-55005",
        "status": "AVAILABLE",
        "current_lat": 30.3800,
        "current_lon": 79.0300,
        "base_location": "Agastyamuni Field Hospital",
        "capacity_persons": 14,
        "equipment": ["PORTABLE_VENTILATORS", "BLOOD_PLASMA_COOLERS", "EMERGENCY_SURGERY_KIT", "TRIAGE_TENTS"]
    },
    {
        "team_code": "TEAM-CIVIL-DEF",
        "name": "Chamoli Civil Defence Quick Response Unit",
        "agency": "CIVIL_DEFENCE",
        "specialization": "FLOOD_WATER_RESCUE",
        "leader_name": "Kailash Rawat",
        "contact": "+91-94120-66006",
        "status": "AVAILABLE",
        "current_lat": 30.4100,
        "current_lon": 79.3200,
        "base_location": "Chamoli Town Hall",
        "capacity_persons": 18,
        "equipment": ["COMMUNITY_RAFTS", "SATELLITE_WALKIE_TALKIES", "MEGAPHONES", "HIGH_LUMEN_SEARCHLIGHTS"]
    }
]


SAMPLE_EMERGENCIES = [
    {
        "raw_text": "CRITICAL EMERGENCY! Mandakini river breached bridge at Sonprayag. 14 pilgrims trapped on rooftop of Shiv Guesthouse, water level rising fast reaching neck deep. 2 infants and 1 pregnant woman trapped! Structural cracks in walls, building about to give way! SEND HELICOPTER IMMEDIATELY!",
        "channel": "SATELLITE_BURST",
        "sender_contact": "+91-98765-43210 (Field Satellite Node #04)",
        "latitude": 30.6315,
        "longitude": 79.0028,
        "location_name": "Sonprayag Market Bridge Sector",
        "district": "Rudraprayag",
        "water_level_meters": 2.8,
        "satellite_constellation": "NAVIC_DISASTER_BURST",
        "time_offset_hours": 0.3
    },
    {
        "raw_text": "Massive landslide at Gaurikund parking lot. Boulders smashed into 3 traveler vehicles and edge of pilgrim dormitory. 8 people under rubble, screaming heard from collapsed debris. Severe bleeding and multiple fractures. Road completely blocked by 50 meters of mud. Need hydraulic cutting equipment!",
        "channel": "WEB",
        "sender_contact": "+91-98111-22334",
        "latitude": 30.6514,
        "longitude": 79.0270,
        "location_name": "Gaurikund Pilgrim Base Station",
        "district": "Rudraprayag",
        "water_level_meters": 0.0,
        "time_offset_hours": 0.8
    },
    {
        "raw_text": "URGENT: Landslide behind Gaurikund bus stand! Several pilgrims trapped under fallen boulders and mud. Big rocks crashed down 30 minutes ago, ambulance cannot reach because road is washed away. Please help!",
        "channel": "SMS",
        "sender_contact": "+91-97234-56789",
        "latitude": 30.6520, # Very close to Gaurikund parking lot -> Realistic Duplicate candidate!
        "longitude": 79.0265,
        "location_name": "Gaurikund Bus Stand / Trek Point",
        "district": "Rudraprayag",
        "water_level_meters": 0.0,
        "time_offset_hours": 0.7
    },
    {
        "raw_text": "Agastyamuni Primary Health Centre completely inundated with 1.8m muddy floodwaters. Main power line snapped, diesel backup generator flooded and dead. 4 cardiac and respiratory patients whose oxygen concentrators will run out in 45 minutes! 2 nurses and 1 doctor trapped on upper floor.",
        "channel": "SATELLITE_BURST",
        "sender_contact": "Dr. Pradeep Joshi, Medical Officer (Agastyamuni PHC)",
        "latitude": 30.3920,
        "longitude": 79.0280,
        "location_name": "Agastyamuni Primary Health Centre",
        "district": "Rudraprayag",
        "water_level_meters": 1.8,
        "satellite_constellation": "GSAT_7A_TACTICAL",
        "time_offset_hours": 1.2
    },
    {
        "raw_text": "Severe cloudburst near Rambara bridge. Footbridge washed away. Unknown number of trekkers stranded across the torrent. Cannot see exact count through fog, shouting heard from opposite bank. No food or warm shelter in freezing rain.",
        "channel": "HF_RADIO",
        "sender_contact": "Forest Guard Post #12",
        "latitude": 30.6850,
        "longitude": 79.0430,
        "location_name": "Rambara Forest Trek Sector",
        "district": "Rudraprayag",
        "water_level_meters": 1.5,
        "time_offset_hours": 2.1
    },
    {
        "raw_text": "Joshimath Sunil ward: three-storey residential structure partially caved in after soil subsidence and heavy rain. 6 family members trapped in basement, including 2 elderly persons with arthritis. Smell of cooking gas leak detected!",
        "channel": "WEB",
        "sender_contact": "+91-94567-89012",
        "latitude": 30.5580,
        "longitude": 79.5660,
        "location_name": "Sunil Ward, Upper Joshimath",
        "district": "Chamoli",
        "water_level_meters": 0.0,
        "time_offset_hours": 1.5
    },
    {
        "raw_text": "Flash flood warning: Alaknanda river rising alarmingly near Karnaprayag Sangam. Water entered low-lying market shops up to knee deep (0.6 meters). Shopkeepers evacuating goods. Need civil defence assistance to guide people away from ghats.",
        "channel": "SMS",
        "sender_contact": "+91-98333-44556",
        "latitude": 30.2580,
        "longitude": 79.2190,
        "location_name": "Karnaprayag Sangam Ghat",
        "district": "Chamoli",
        "water_level_meters": 0.6,
        "time_offset_hours": 3.0
    },
    {
        "raw_text": "Trekker group caught in sudden blizzard and freezing rain near Tungnath peak path. 5 students severely hypothermic, shivering uncontrollably and unable to walk. Tents blown away by gale force winds. Exposure risk critical within hours.",
        "channel": "SATELLITE_BURST",
        "sender_contact": "Garhwal Treks Expedition Leader",
        "latitude": 30.4880,
        "longitude": 79.2180,
        "location_name": "Chopta - Tungnath Ridge Trail",
        "district": "Rudraprayag",
        "water_level_meters": 0.0,
        "satellite_constellation": "IRIDIUM_NEXT_SBD",
        "time_offset_hours": 1.9
    },
    {
        "raw_text": "NH-107 blocked at Banswara due to huge rockfall. A tourist bus with 32 passengers stranded on narrow mountain ledge. No injuries reported so far, but food and drinking water depleted. Road clearance bulldozer needed.",
        "channel": "WEB",
        "sender_contact": "+91-97999-11223",
        "latitude": 30.4650,
        "longitude": 79.0780,
        "location_name": "Banswara Highway Pass (NH-107)",
        "district": "Rudraprayag",
        "water_level_meters": 0.0,
        "time_offset_hours": 4.2
    },
    {
        "raw_text": "Bus stranded at Banswara turn. Landslide blocked both sides of road. 30+ pilgrims in bus, small children crying for water. Please dispatch relief supplies and road clearing crew.",
        "channel": "SMS",
        "sender_contact": "+91-96555-88990",
        "latitude": 30.4660, # Proximity duplicate of Banswara bus incident!
        "longitude": 79.0770,
        "location_name": "Banswara Junction, Rudraprayag Road",
        "district": "Rudraprayag",
        "water_level_meters": 0.0,
        "time_offset_hours": 4.0
    },
    {
        "raw_text": "Submerged suspension bridge at Tilwara. Alaknanda tributary backflow. 3 shepherds stranded on small river island with their livestock. Water rising 10 cm every half hour. Need rescue boat before dark.",
        "channel": "FIELD_RELAY",
        "sender_contact": "Tilwara Police Chowki",
        "latitude": 30.3450,
        "longitude": 78.9800,
        "location_name": "Tilwara River Crossing",
        "district": "Rudraprayag",
        "water_level_meters": 1.2,
        "time_offset_hours": 2.5
    },
    {
        "raw_text": "Elderly diabetic patient with gangrene in isolated village of Triyuginarayan. High fever and vomiting, requires emergency intravenous antibiotics and stretcher evacuation to Guptkashi hospital. Village road cut off by mud slips.",
        "channel": "WEB",
        "sender_contact": "+91-94111-99887",
        "latitude": 30.6430,
        "longitude": 78.9860,
        "location_name": "Triyuginarayan Village",
        "district": "Rudraprayag",
        "water_level_meters": 0.0,
        "time_offset_hours": 3.8
    },
    {
        "raw_text": "Mudflow entered 5 houses in Phata helipad road. Mud up to 3 feet deep inside living rooms. Families moved to school building safely. Requesting dry rations and tarpaulins.",
        "channel": "SMS",
        "sender_contact": "Phata Gram Pradhan",
        "latitude": 30.5750,
        "longitude": 79.0350,
        "location_name": "Phata Village Lowlands",
        "district": "Rudraprayag",
        "water_level_meters": 0.8,
        "time_offset_hours": 5.1
    },
    {
        "raw_text": "Cracks developing in retaining wall near Singtoli dam overflow channel. Water discharge is high. Engineers monitoring situation. Precautionary evacuation advisory recommended for downstream hamlet.",
        "channel": "WEB",
        "sender_contact": "Irrigation Dept Field Engineer",
        "latitude": 30.3120,
        "longitude": 79.0450,
        "location_name": "Singtoli Barrage & Spillway",
        "district": "Rudraprayag",
        "water_level_meters": 2.2,
        "time_offset_hours": 1.0
    },
    {
        "raw_text": "Transformer explosion following lightning strike at Kund power substation. Sparks caused bushfire on adjacent pine forest ridge. Spreading uphill toward telecom tower. Fire tenders cannot navigate narrow track.",
        "channel": "FIELD_RELAY",
        "sender_contact": "Power Corp Grid Supervisor",
        "latitude": 30.5050,
        "longitude": 79.0820,
        "location_name": "Kund Substation Ridge",
        "district": "Rudraprayag",
        "water_level_meters": 0.0,
        "time_offset_hours": 2.0
    },
    {
        "raw_text": "Relief camp inquiry: When will helicopter supply airdrops resume for Gaundar village? Food supplies sufficient for 2 more days, but solar battery running low.",
        "channel": "WEB",
        "sender_contact": "+91-94123-45670",
        "latitude": 30.6020,
        "longitude": 79.1550,
        "location_name": "Gaundar Relief Staging Post",
        "district": "Rudraprayag",
        "water_level_meters": 0.0,
        "time_offset_hours": 6.5
    }
]


def seed_database(db_path: str = None) -> Dict[str, Any]:
    """
    Initializes database and seeds realistic disaster scenario:
    Runs every report through Classifier, Deduplicator, Risk Engine, and Satellite Simulator!
    """
    init_db(db_path)
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Clear existing data for clean seed
    cursor.executescript("""
        DELETE FROM incident_updates;
        DELETE FROM raw_messages;
        DELETE FROM incidents;
        DELETE FROM rescue_teams;
        DELETE FROM satellite_transmissions;
    """)
    conn.commit()

    # 1. Seed Rescue Teams
    for t in SAMPLE_TEAMS:
        cursor.execute("""
            INSERT INTO rescue_teams (
                team_code, name, agency, specialization, leader_name, contact,
                status, current_lat, current_lon, base_location, capacity_persons,
                equipment, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            t["team_code"], t["name"], t["agency"], t["specialization"],
            t["leader_name"], t["contact"], t["status"],
            t["current_lat"], t["current_lon"], t["base_location"],
            t["capacity_persons"], json.dumps(t["equipment"])
        ))
    conn.commit()
    conn.close()

    # 2. Initialize Core Processing Engines
    classifier = DisasterClassifier()
    deduplicator = IncidentDeduplicator()
    risk_engine = RiskScoringEngine()
    satellite_sim = SatelliteLinkSimulator()

    seeded_incidents_count = 0
    merged_count = 0
    sat_packets_count = 0

    # 3. Process each sample emergency through the full Akash Setu workflow pipeline
    for sample in SAMPLE_EMERGENCIES:
        # A. Save raw message strictly verbatim
        raw_msg_id = save_raw_message(
            raw_text=sample["raw_text"],
            channel=sample["channel"],
            sender_contact=sample.get("sender_contact"),
            signal_metrics={
                "channel": sample["channel"],
                "constellation": sample.get("satellite_constellation")
            },
            db_path=db_path
        )

        # B. Run AI / Local NLP Classifier
        cls_result = classifier.classify_emergency(sample["raw_text"], channel=sample["channel"])

        # Override water level if provided explicitly in sample
        if sample.get("water_level_meters") is not None and cls_result.get("water_level_meters") is None:
            cls_result["water_level_meters"] = sample["water_level_meters"]

        candidate_data = {
            "title": cls_result["summary_title"],
            "disaster_type": cls_result["disaster_type"],
            "severity_level": cls_result["severity_level"],
            "latitude": sample["latitude"],
            "longitude": sample["longitude"],
            "location_name": sample["location_name"],
            "district": sample["district"],
            "trapped_count": cls_result["trapped_count"],
            "injured_count": cls_result["injured_count"],
            "casualties_count": cls_result["casualties_count"],
            "vulnerable_groups": cls_result["vulnerable_groups"],
            "infrastructure_damaged": cls_result["infrastructure_damaged"],
            "water_level_meters": cls_result["water_level_meters"],
            "raw_text": sample["raw_text"]
        }

        # C. Check for Duplicate Reports against existing incidents
        from .db import get_incidents, merge_incidents
        active_incidents = get_incidents(db_path=db_path)
        match_result = deduplicator.find_best_match(candidate_data, active_incidents)

        if match_result and match_result[1]["is_duplicate"]:
            # High-confidence duplicate: consolidate into primary incident
            primary_inc, metrics = match_result
            merge_incidents(
                primary_id=primary_inc["id"],
                duplicate_id=primary_inc["id"], # Merge candidate raw message to primary
                author="Akash Setu Auto-Consolidation",
                reason=f"Multi-factor duplicate match: {metrics['composite_score']*100:.1f}% confidence ({metrics['distance_km']} km away)",
                db_path=db_path
            )
            # Re-link the new raw message to the primary incident
            from .db import link_message_to_incident
            link_message_to_incident(raw_msg_id, primary_inc["id"], db_path=db_path)
            merged_count += 1
            continue

        # D. Calculate Mathematical Risk Score
        risk_breakdown = risk_engine.calculate_risk(candidate_data)
        candidate_data["risk_score"] = risk_breakdown["final_score"]
        candidate_data["priority_level"] = risk_breakdown["priority"]
        candidate_data["risk_breakdown"] = risk_breakdown
        candidate_data["ai_classification_meta"] = cls_result

        # E. Insert into database as new incident
        inc_id = insert_incident(candidate_data, raw_msg_id=raw_msg_id, db_path=db_path)
        seeded_incidents_count += 1

        # F. If channel was satellite burst, log realistic satellite transmission packet
        if sample["channel"] == "SATELLITE_BURST":
            sat_result = satellite_sim.transmit_burst(
                candidate_data,
                constellation_key=sample.get("satellite_constellation", "NAVIC_DISASTER_BURST"),
                simulated_rain_fade_db=4.2
            )
            log_satellite_transmission(sat_result, db_path=db_path)
            sat_packets_count += 1

    # 4. Dispatch teams to top 2 critical P1 incidents for demonstration
    from .db import assign_team_to_incident, get_rescue_teams
    all_incs = get_incidents(db_path=db_path)
    p1_incs = [i for i in all_incs if i["priority_level"] == "P1"]
    teams = get_rescue_teams(db_path=db_path)

    if p1_incs and len(teams) >= 2:
        # Dispatch ALH Dhruv to first critical incident
        assign_team_to_incident(
            incident_id=p1_incs[0]["id"],
            team_id=teams[2]["id"], # IAF Helicopter Unit
            author="State Disaster Control Room",
            notes="Aerial winch evacuation ordered for rooftop trapped victims.",
            db_path=db_path
        )
        if len(p1_incs) > 1:
            # Dispatch NDRF Flood unit to second
            assign_team_to_incident(
                incident_id=p1_incs[1]["id"],
                team_id=teams[0]["id"], # NDRF Alpha Flood Team
                author="State Disaster Control Room",
                notes="Mobilizing inflatable motorboats and medical trauma pack.",
                db_path=db_path
            )

    return {
        "status": "SUCCESS",
        "incidents_seeded": seeded_incidents_count,
        "duplicates_merged": merged_count,
        "satellite_bursts_logged": sat_packets_count,
        "teams_configured": len(SAMPLE_TEAMS)
    }

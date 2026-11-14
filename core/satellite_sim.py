"""
Akash Setu - Low-Bandwidth Satellite Communications Simulator
Module: core/satellite_sim.py

Simulates tactical emergency satellite communications over constrained links:
- Binary bit-packing & compression of emergency reports
- Constellation link budget & orbital telemetry (NavIC, GSAT-7A, Iridium SBD)
- Rain fade attenuation & Signal-to-Noise Ratio (SNR) calculation
- Packet loss & Automatic Repeat reQuest (ARQ) retransmission
- Realistic hex payload formatting & transmission time benchmarking

LABELING NOTICE:
All transmissions produced by this module are SIMULATED SATELLITE TRANSMISSIONS.
"""

import struct
import zlib
import time
import math
import random
import datetime
from typing import Dict, Any, Tuple, Optional, List


class SatellitePacketEncoder:
    """
    Encodes high-level emergency reports into an ultra-compact binary burst packet
    designed for 1200-2400 bps satellite transponders (NavIC / Iridium SBD).
    """

    MAGIC_HEADER = 0x4153 # 'AS' in ASCII
    PROTOCOL_VERSION = 1

    DISASTER_TYPE_MAP = {
        "GENERAL_DISASTER": 0,
        "FLOOD": 1,
        "LANDSLIDE": 2,
        "BUILDING_COLLAPSE": 3,
        "EARTHQUAKE": 4,
        "FIRE": 5,
        "MEDICAL": 6,
        "CYCLONE": 7
    }
    REVERSE_TYPE_MAP = {v: k for k, v in DISASTER_TYPE_MAP.items()}

    VULNERABILITY_BITS = {
        "INFANTS_CHILDREN": 1 << 0,
        "PREGNANT_WOMEN": 1 << 1,
        "ELDERLY": 1 << 2,
        "CRITICAL_MEDICAL": 1 << 3,
        "HYPOTHERMIA_EXPOSURE": 1 << 4,
        "BRIDGE_COLLAPSE": 1 << 5,
        "HOSPITAL_COMPROMISED": 1 << 6,
        "DAM_RISK": 1 << 7
    }

    HEADER_FORMAT = ">HBBiiBBBH"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT) # 17 bytes

    def encode_report(self, report: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
        """
        Compacts report dictionary into binary byte array.
        Returns (packed_bytes, telemetry_stats).
        """
        # 1. Header (2 bytes magic + 1 byte version + 1 byte flags)
        magic = self.MAGIC_HEADER
        version = self.PROTOCOL_VERSION

        # Priority flag (2 bits) + channel (2 bits)
        priority_code = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}.get(report.get("priority_level", "P2"), 2)
        flags = (priority_code & 0x03)

        # 2. Coordinates: 32-bit signed fixed point (microdegrees: lat * 1e6)
        lat = float(report.get("latitude", 0.0))
        lon = float(report.get("longitude", 0.0))
        lat_fixed = int(round(lat * 1e6))
        lon_fixed = int(round(lon * 1e6))

        # 3. Disaster Type (1 byte)
        dtype = report.get("disaster_type", "GENERAL_DISASTER").upper()
        dtype_code = self.DISASTER_TYPE_MAP.get(dtype, 0)

        # 4. Packed Casualties (1 byte: high nibble trapped, low nibble injured)
        # Value 15 indicates unknown/unspecified or >14
        trapped = report.get("trapped_count")
        injured = report.get("injured_count")

        trapped_nibble = 15 if trapped is None else min(14, max(0, trapped))
        injured_nibble = 15 if injured is None else min(14, max(0, injured))
        casualties_byte = (trapped_nibble << 4) | (injured_nibble & 0x0F)

        # 5. Vulnerability & Infrastructure Bitmask (1 byte)
        vmask = 0
        all_flags = (report.get("vulnerable_groups") or []) + (report.get("infrastructure_damaged") or [])
        for f in all_flags:
            if f in self.VULNERABILITY_BITS:
                vmask |= self.VULNERABILITY_BITS[f]

        # 6. Water Level in decimeters (2 bytes unsigned short: 0 to 6553.5 meters)
        w_level = report.get("water_level_meters")
        w_decimeters = int(round(w_level * 10)) if w_level is not None else 0xFFFF

        # Pack fixed header struct (17 bytes total)
        fixed_header = struct.pack(self.HEADER_FORMAT,
            magic, version, flags,
            lat_fixed, lon_fixed,
            dtype_code, casualties_byte, vmask, w_decimeters
        )

        # 7. Variable Text Payload: compressed with DEFLATE / zlib
        raw_text = (report.get("raw_text") or report.get("title") or "").strip()
        compressed_text = b""
        if raw_text:
            # Level 9 compression
            compressed_text = zlib.compress(raw_text.encode("utf-8"), level=9)

        # Cap text payload to fit satellite burst limit (max 64 bytes for text)
        if len(compressed_text) > 64:
            compressed_text = compressed_text[:64]

        payload = fixed_header + struct.pack(">B", len(compressed_text)) + compressed_text

        # 8. CRC-16 Checksum (2 bytes)
        crc = zlib.crc32(payload) & 0xFFFF
        full_packet = payload + struct.pack(">H", crc)

        raw_size = len(raw_text.encode("utf-8")) + 120 # Estimate typical JSON size
        compressed_size = len(full_packet)
        comp_ratio = max(0.0, 1.0 - (compressed_size / float(raw_size)))

        telemetry = {
            "raw_size_bytes": raw_size,
            "compressed_size_bytes": compressed_size,
            "compression_ratio": round(comp_ratio, 3),
            "compression_pct": round(comp_ratio * 100, 1),
            "crc16": f"0x{crc:04X}",
            "hex_dump": " ".join(f"{b:02X}" for b in full_packet)
        }

        return full_packet, telemetry

    def decode_packet(self, packet: bytes) -> Dict[str, Any]:
        """Unpacks binary satellite burst packet back into report fields."""
        min_len = self.HEADER_SIZE + 1 + 2
        if len(packet) < min_len:
            raise ValueError(f"Packet too short ({len(packet)} bytes, minimum {min_len})")

        # Verify CRC
        payload_data = packet[:-2]
        received_crc = struct.unpack(">H", packet[-2:])[0]
        calculated_crc = zlib.crc32(payload_data) & 0xFFFF
        crc_valid = (received_crc == calculated_crc)

        (magic, version, flags,
         lat_fixed, lon_fixed,
         dtype_code, casualties_byte, vmask, w_decimeters) = struct.unpack(self.HEADER_FORMAT, payload_data[:self.HEADER_SIZE])

        if magic != self.MAGIC_HEADER:
            raise ValueError("Invalid Akash Setu Satellite packet header")

        lat = lat_fixed / 1e6
        lon = lon_fixed / 1e6
        dtype = self.REVERSE_TYPE_MAP.get(dtype_code, "GENERAL_DISASTER")

        trapped_nibble = (casualties_byte >> 4) & 0x0F
        injured_nibble = casualties_byte & 0x0F

        # Strict missing-value preservation: 15 represents None/unknown
        trapped_count = None if trapped_nibble == 15 else trapped_nibble
        injured_count = None if injured_nibble == 15 else injured_nibble

        vulnerable_groups = []
        for name, bit in self.VULNERABILITY_BITS.items():
            if vmask & bit:
                vulnerable_groups.append(name)

        water_level = None if w_decimeters == 0xFFFF else (w_decimeters / 10.0)

        # Decompress text
        text_len = struct.unpack(">B", payload_data[self.HEADER_SIZE:self.HEADER_SIZE + 1])[0]
        text_bytes = payload_data[self.HEADER_SIZE + 1:self.HEADER_SIZE + 1 + text_len]
        decoded_text = ""
        if text_bytes:
            try:
                decoded_text = zlib.decompress(text_bytes).decode("utf-8")
            except Exception:
                decoded_text = f"[Compressed burst text fragment: {len(text_bytes)} bytes]"

        return {
            "latitude": lat,
            "longitude": lon,
            "disaster_type": dtype,
            "trapped_count": trapped_count,
            "injured_count": injured_count,
            "vulnerable_groups": vulnerable_groups,
            "water_level_meters": water_level,
            "raw_text": decoded_text,
            "crc_valid": crc_valid
        }


class SatelliteLinkSimulator:
    """
    Simulates radio frequency propagation, rain fade, atmospheric attenuation,
    orbital latency, and automatic packet retransmissions.
    """

    CONSTELLATIONS = {
        "NAVIC_DISASTER_BURST": {
            "name": "NavIC / IRNSS (ISRO Geo-Stationary S-Band)",
            "altitude_km": 36000,
            "baud_rate_bps": 1200,
            "base_latency_ms": 520,
            "nominal_snr_db": 15.5,
            "link_margin_db": 7.2
        },
        "GSAT_7A_TACTICAL": {
            "name": "GSAT-7A Military / Disaster Transponder (ISRO)",
            "altitude_km": 36000,
            "baud_rate_bps": 2400,
            "base_latency_ms": 480,
            "nominal_snr_db": 18.2,
            "link_margin_db": 9.5
        },
        "IRIDIUM_NEXT_SBD": {
            "name": "Iridium-NEXT Short Burst Data (LEO Mesh)",
            "altitude_km": 780,
            "baud_rate_bps": 2400,
            "base_latency_ms": 280,
            "nominal_snr_db": 13.0,
            "link_margin_db": 5.4
        }
    }

    def __init__(self, encoder: Optional[SatellitePacketEncoder] = None):
        self.encoder = encoder or SatellitePacketEncoder()

    def transmit_burst(self, report: Dict[str, Any],
                       constellation_key: str = "NAVIC_DISASTER_BURST",
                       simulated_rain_fade_db: float = 3.5,
                       force_packet_loss: bool = False) -> Dict[str, Any]:
        """
        Simulates end-to-end satellite burst transmission from disaster node to command ground station.
        """
        cfg = self.CONSTELLATIONS.get(constellation_key, self.CONSTELLATIONS["NAVIC_DISASTER_BURST"])

        # 1. Encode packet
        packet_bytes, telemetry = self.encoder.encode_report(report)

        # 2. Compute Link Budget
        # Effective SNR = Nominal SNR - Rain Fade + random atmospheric jitter
        jitter = random.uniform(-0.8, 0.8)
        effective_snr = max(2.0, cfg["nominal_snr_db"] - simulated_rain_fade_db + jitter)
        effective_margin = max(-2.0, cfg["link_margin_db"] - simulated_rain_fade_db + jitter)

        # Packet Loss Probability curve based on link margin
        if force_packet_loss:
            packet_loss_prob = 1.0
        elif effective_margin < 0:
            packet_loss_prob = 0.85 # Link dropped below threshold
        elif effective_margin < 2.0:
            packet_loss_prob = 0.35 # High bit error rate
        elif effective_margin < 4.0:
            packet_loss_prob = 0.10 # Light atmospheric flutter
        else:
            packet_loss_prob = 0.02 # Normal clean link

        simulated_loss = (random.random() < packet_loss_prob)

        # 3. Transmission Duration calculation:
        # Time = Base Latency + (Bits / Baud Rate) + ARQ retransmission delay if lost
        packet_bits = len(packet_bytes) * 8
        airtime_ms = (packet_bits / float(cfg["baud_rate_bps"])) * 1000.0

        retransmissions = 0
        total_time_ms = cfg["base_latency_ms"] + airtime_ms

        if simulated_loss:
            # Trigger ARQ (Automatic Repeat reQuest) round trip
            retransmissions = 1
            total_time_ms += (cfg["base_latency_ms"] * 2) + airtime_ms
            status = "RETRANSMITTED"
        else:
            status = "DELIVERED"

        # Packet ID
        packet_id = f"SAT-{int(time.time()*1000)%1000000:06d}"

        # Decode verification
        decoded = self.encoder.decode_packet(packet_bytes)

        return {
            "packet_id": packet_id,
            "constellation": constellation_key,
            "constellation_name": cfg["name"],
            "raw_bytes_count": telemetry["raw_size_bytes"],
            "compressed_bytes_count": telemetry["compressed_size_bytes"],
            "compression_ratio": telemetry["compression_ratio"],
            "compression_pct": telemetry["compression_pct"],
            "hex_payload": telemetry["hex_dump"],
            "snr_db": round(effective_snr, 1),
            "elevation_deg": round(random.uniform(42.0, 68.0), 1),
            "link_margin_db": round(effective_margin, 1),
            "rain_fade_db": round(simulated_rain_fade_db, 1),
            "packet_loss_simulated": 1 if simulated_loss else 0,
            "retransmissions": retransmissions,
            "transmission_time_ms": round(total_time_ms, 1),
            "status": status,
            "decoded_payload": decoded,
            "simulation_badge": "[SIMULATED SATELLITE BURST: LINK METRICS SYNTHESIZED FOR OFFLINE NODE]",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }

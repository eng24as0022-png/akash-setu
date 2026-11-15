"""
Akash Setu - Incident Duplicate Detection & Consolidation Engine
Module: core/deduplication.py

Calculates multi-factor similarity between new reports and existing active incidents:
- Spatial proximity via Haversine distance (km)
- Temporal proximity (hours)
- Semantic text / token similarity
- Disaster type congruence

Maintains full data provenance:
Original raw messages are never discarded or overwritten.
"""

import math
import datetime
from typing import Dict, Any, List, Optional, Tuple


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in kilometers."""
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2.0) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class IncidentDeduplicator:
    def __init__(self,
                 geo_threshold_km: float = 3.0,
                 time_threshold_hours: float = 6.0,
                 auto_merge_threshold: float = 0.65,
                 flag_threshold: float = 0.45):
        self.geo_threshold_km = geo_threshold_km
        self.time_threshold_hours = time_threshold_hours
        self.auto_merge_threshold = auto_merge_threshold
        self.flag_threshold = flag_threshold

        self.stop_words = {
            "the", "a", "an", "in", "on", "at", "to", "for", "with", "is", "are", "was",
            "were", "and", "or", "of", "from", "by", "urgent", "please", "help", "need"
        }

    def compute_similarity(self, candidate: Dict[str, Any], existing: Dict[str, Any]) -> Dict[str, Any]:
        """
        Computes transparent multi-factor similarity between candidate and existing incident:
        Formula: M = 0.35*L + 0.20*T + 0.25*C + 0.20*D
        Where:
          L: Location / Spatial proximity (0 to 1)
          T: Temporal proximity (0 to 1)
          C: Category congruence (0 to 1)
          D: Description / Semantic text similarity (0 to 1)
        """
        # 1. L: Geo proximity (0.0 to 1.0)
        lat1, lon1 = float(candidate.get("latitude", 0.0)), float(candidate.get("longitude", 0.0))
        lat2, lon2 = float(existing.get("latitude", 0.0)), float(existing.get("longitude", 0.0))
        distance_km = haversine_distance_km(lat1, lon1, lat2, lon2)

        if distance_km <= self.geo_threshold_km:
            L = max(0.0, 1.0 - (distance_km / self.geo_threshold_km))
        else:
            # Check if same named location / landmark as fallback
            c_loc = (candidate.get("location_name") or "").lower().strip()
            e_loc = (existing.get("location_name") or "").lower().strip()
            if c_loc and e_loc and (c_loc in e_loc or e_loc in c_loc):
                L = 0.85
            else:
                L = 0.0

        # 2. T: Temporal proximity (0.0 to 1.0)
        c_time = self._parse_iso(candidate.get("created_at"))
        e_time = self._parse_iso(existing.get("created_at"))
        delta_hours = abs((c_time - e_time).total_seconds()) / 3600.0

        if delta_hours <= self.time_threshold_hours:
            T = max(0.0, 1.0 - (delta_hours / self.time_threshold_hours))
        else:
            T = 0.0

        # 3. C: Disaster Category Congruence (0.0 to 1.0)
        c_type = (candidate.get("disaster_type") or "").upper()
        e_type = (existing.get("disaster_type") or "").upper()
        if c_type == e_type:
            C = 1.0
        elif {c_type, e_type} <= {"FLOOD", "LANDSLIDE"}:
            C = 0.75 # Common compound hazard in cloudbursts
        elif {c_type, e_type} <= {"FIRE", "GAS_LEAKAGE", "EXPLOSION"}:
            C = 0.70
        elif {c_type, e_type} <= {"BUILDING_COLLAPSE", "EARTHQUAKE"}:
            C = 0.80
        elif "RESCUE_REQUEST" in (c_type, e_type):
            C = 0.60
        else:
            C = 0.10

        # 4. D: Description / Text Similarity (0.0 to 1.0)
        c_text = (candidate.get("raw_text") or candidate.get("title") or "").lower()
        e_text = (existing.get("raw_text") or existing.get("title") or "").lower()
        D = self._jaccard_similarity(c_text, e_text)

        # Boost if shared landmarks
        c_loc = (candidate.get("location_name") or "").lower().strip()
        e_loc = (existing.get("location_name") or "").lower().strip()
        if c_loc and e_loc and (c_loc in e_loc or e_loc in c_loc):
            D = min(1.0, D + 0.30)

        # Exact formula: M = 0.35*L + 0.20*T + 0.25*C + 0.20*D
        composite_score = (
            0.35 * L +
            0.20 * T +
            0.25 * C +
            0.20 * D
        )

        is_duplicate = composite_score >= self.auto_merge_threshold
        is_potential = (composite_score >= self.flag_threshold) and not is_duplicate

        return {
            "composite_score": round(composite_score, 3),
            "match_score": round(composite_score, 3),
            "formula": "M = 0.35L + 0.20T + 0.25C + 0.20D",
            "is_duplicate": is_duplicate,
            "is_potential_duplicate": is_potential,
            "distance_km": round(distance_km, 2),
            "delta_hours": round(delta_hours, 2),
            "components": {
                "L_location": round(L, 3),
                "T_time": round(T, 3),
                "C_category": round(C, 3),
                "D_description": round(D, 3),
                "geo_similarity": round(L, 3),
                "time_similarity": round(T, 3),
                "type_similarity": round(C, 3),
                "text_similarity": round(D, 3)
            },
            "status_label": "HIGH_CONFIDENCE_DUPLICATE" if is_duplicate else (
                "POTENTIAL_CO_INCIDENT" if is_potential else "DISTINCT_INCIDENT"
            )
        }

    def find_best_match(self, candidate: Dict[str, Any],
                        active_incidents: List[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Scans all active incidents to find highest-scoring duplicate match.
        Returns (best_incident, match_metrics) or None.
        """
        best_incident = None
        best_metrics = None
        highest_score = 0.0

        for inc in active_incidents:
            # Skip resolved or closed incidents
            if inc.get("status") in ("RESOLVED", "CLOSED"):
                continue

            metrics = self.compute_similarity(candidate, inc)
            if metrics["composite_score"] > highest_score and metrics["composite_score"] >= self.flag_threshold:
                highest_score = metrics["composite_score"]
                best_incident = inc
                best_metrics = metrics

        if best_incident:
            return best_incident, best_metrics
        return None

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        tokens1 = set(w for w in text1.split() if w not in self.stop_words and len(w) > 2)
        tokens2 = set(w for w in text2.split() if w not in self.stop_words and len(w) > 2)

        if not tokens1 or not tokens2:
            return 0.0

        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        return len(intersection) / float(len(union))

    def _parse_iso(self, ts_str: Optional[str]) -> datetime.datetime:
        if not ts_str:
            return datetime.datetime.now(datetime.timezone.utc)
        try:
            # Handle standard ISO strings
            cleaned = ts_str.replace("Z", "+00:00")
            return datetime.datetime.fromisoformat(cleaned)
        except Exception:
            return datetime.datetime.now(datetime.timezone.utc)

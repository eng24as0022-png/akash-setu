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
                 auto_merge_threshold: float = 0.72,
                 flag_threshold: float = 0.48):
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
        Computes transparent multi-factor similarity between candidate and existing incident.
        Returns composite score and individual component metrics.
        """
        # 1. Geo proximity
        lat1, lon1 = float(candidate.get("latitude", 0.0)), float(candidate.get("longitude", 0.0))
        lat2, lon2 = float(existing.get("latitude", 0.0)), float(existing.get("longitude", 0.0))
        distance_km = haversine_distance_km(lat1, lon1, lat2, lon2)

        if distance_km <= self.geo_threshold_km:
            geo_sim = max(0.0, 1.0 - (distance_km / self.geo_threshold_km))
        else:
            geo_sim = 0.0

        # 2. Temporal proximity
        c_time = self._parse_iso(candidate.get("created_at"))
        e_time = self._parse_iso(existing.get("created_at"))
        delta_hours = abs((c_time - e_time).total_seconds()) / 3600.0

        if delta_hours <= self.time_threshold_hours:
            time_sim = max(0.0, 1.0 - (delta_hours / self.time_threshold_hours))
        else:
            time_sim = 0.0

        # 3. Disaster Type Congruence
        c_type = (candidate.get("disaster_type") or "").upper()
        e_type = (existing.get("disaster_type") or "").upper()
        if c_type == e_type:
            type_sim = 1.0
        elif {c_type, e_type} <= {"FLOOD", "LANDSLIDE"}:
            type_sim = 0.7 # Common compound hazard in cloudbursts
        else:
            type_sim = 0.1

        # 4. Semantic Text Similarity (Jaccard + Landmark matching)
        c_text = (candidate.get("raw_text") or candidate.get("title") or "").lower()
        e_text = (existing.get("raw_text") or existing.get("title") or "").lower()
        text_sim = self._jaccard_similarity(c_text, e_text)

        # Boost if same named location / landmark
        c_loc = (candidate.get("location_name") or "").lower().strip()
        e_loc = (existing.get("location_name") or "").lower().strip()
        if c_loc and e_loc and (c_loc in e_loc or e_loc in c_loc):
            text_sim = min(1.0, text_sim + 0.35)

        # Weighted composite score:
        # Spatial is primary in physical disasters (40%), followed by text (25%), type (20%), time (15%)
        composite_score = (
            0.40 * geo_sim +
            0.25 * text_sim +
            0.20 * type_sim +
            0.15 * time_sim
        )

        is_duplicate = composite_score >= self.auto_merge_threshold
        is_potential = (composite_score >= self.flag_threshold) and not is_duplicate

        return {
            "composite_score": round(composite_score, 3),
            "is_duplicate": is_duplicate,
            "is_potential_duplicate": is_potential,
            "distance_km": round(distance_km, 2),
            "delta_hours": round(delta_hours, 2),
            "components": {
                "geo_similarity": round(geo_sim, 3),
                "text_similarity": round(text_sim, 3),
                "type_similarity": round(type_sim, 3),
                "time_similarity": round(time_sim, 3)
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

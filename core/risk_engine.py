"""
Akash Setu - Mathematical Risk-Scoring & Priority Triage Engine
Module: core/risk_engine.py

Calculates an explainable multi-factor risk score R in [0, 100] based on:
1. Hazard severity & phenomenological lethality
2. Humanitarian & demographic vulnerability
3. Critical infrastructure impairment
4. Water level / environmental surge
5. Time decay / Golden Hour escalation

CRITICAL INVARIANT:
Never replaces missing victim counts with 0.
Unknown counts receive a documented PROVISIONAL UNCERTAINTY WEIGHT.
"""

import math
import datetime
from typing import Dict, Any, Optional, List, Tuple


class RiskScoringEngine:
    # Base hazard weights (Max 35)
    HAZARD_BASE_WEIGHTS = {
        "BUILDING_COLLAPSE": 32.0,
        "FLOOD": 28.0,
        "LANDSLIDE": 28.0,
        "FIRE": 26.0,
        "MEDICAL": 25.0,
        "EARTHQUAKE": 24.0,
        "CYCLONE": 20.0,
        "GENERAL_DISASTER": 15.0
    }

    SEVERITY_MULTIPLIER = {
        "CRITICAL": 1.25,
        "HIGH": 1.00,
        "MEDIUM": 0.75,
        "LOW": 0.50
    }

    VULNERABILITY_WEIGHTS = {
        "CRITICAL_MEDICAL": 8.0,
        "INFANTS_CHILDREN": 6.0,
        "PREGNANT_WOMEN": 6.0,
        "HYPOTHERMIA_EXPOSURE": 5.0,
        "ELDERLY": 4.0
    }

    INFRASTRUCTURE_WEIGHTS = {
        "DAM_RISK": 10.0,
        "HOSPITAL_COMPROMISED": 8.0,
        "BRIDGE_COLLAPSE": 7.0,
        "BUILDING_COLLAPSE_RISK": 8.0,
        "POWER_GRID_FAILURE": 4.0,
        "ROAD_HIGHWAY_CUTOFF": 4.0
    }

    # Weight applied when casualty count is genuinely unknown (preserves NULL without assuming 0)
    PROVISIONAL_CASUALTY_WEIGHT = 12.0
    PROVISIONAL_INJURED_WEIGHT = 4.0

    def calculate_risk(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates mathematical risk score and returns a transparent audit breakdown.
        """
        disaster_type = (incident.get("disaster_type") or "GENERAL_DISASTER").upper()
        severity_level = (incident.get("severity_level") or "HIGH").upper()
        vulnerable_groups = incident.get("vulnerable_groups") or []
        infra_damaged = incident.get("infrastructure_damaged") or []
        water_level = incident.get("water_level_meters")
        trapped_count = incident.get("trapped_count")
        injured_count = incident.get("injured_count")
        status = incident.get("status") or "PENDING_TRIAGE"

        is_provisional = False
        provisional_reasons: List[str] = []

        # 1. Base Hazard Severity Score (10 - 35)
        base_h = self.HAZARD_BASE_WEIGHTS.get(disaster_type, 15.0)
        sev_mult = self.SEVERITY_MULTIPLIER.get(severity_level, 1.0)
        s_hazard = min(35.0, base_h * sev_mult)

        # 2. Humanitarian & Victim Score (0 - 35)
        # Trapped component
        if trapped_count is not None:
            # Trapped count is verified: logarithmic scale with linear damping
            s_trapped = min(20.0, 4.0 * math.log(1.0 + trapped_count) + 0.8 * trapped_count)
            trapped_label = f"Verified {trapped_count} persons trapped"
        else:
            # Trapped count is unknown: STRICTLY PRESERVE NULL and apply provisional weight
            s_trapped = self.PROVISIONAL_CASUALTY_WEIGHT
            is_provisional = True
            provisional_reasons.append("Trapped count is unspecified (provisional uncertainty weight applied; preserved as NULL)")
            trapped_label = f"Unknown / Unverified (Provisional weight: {self.PROVISIONAL_CASUALTY_WEIGHT:.1f})"

        # Injured component
        if injured_count is not None:
            s_injured = min(8.0, 1.5 * injured_count)
            injured_label = f"Verified {injured_count} injured"
        else:
            s_injured = self.PROVISIONAL_INJURED_WEIGHT
            injured_label = f"Injured status unconfirmed (Provisional weight: {self.PROVISIONAL_INJURED_WEIGHT:.1f})"

        # Vulnerable demographics
        s_vuln = 0.0
        vuln_breakdown = []
        for v in vulnerable_groups:
            w = self.VULNERABILITY_WEIGHTS.get(v, 3.0)
            s_vuln += w
            vuln_breakdown.append(f"{v} (+{w:.1f})")
        s_vuln = min(15.0, s_vuln)

        s_human = min(35.0, s_trapped + s_injured + s_vuln)

        # 3. Critical Infrastructure & Environmental Surge (0 - 20)
        s_infra = 0.0
        infra_breakdown = []
        for item in infra_damaged:
            w = self.INFRASTRUCTURE_WEIGHTS.get(item, 3.0)
            s_infra += w
            infra_breakdown.append(f"{item} (+{w:.1f})")

        # Water level surge factor
        s_water = 0.0
        if water_level is not None:
            if water_level >= 2.5:
                s_water = 8.0
            elif water_level >= 1.5:
                s_water = 5.0
            elif water_level >= 0.5:
                s_water = 3.0
            infra_breakdown.append(f"Flood Depth {water_level:.1f}m (+{s_water:.1f})")

        s_infra_total = min(20.0, s_infra + s_water)

        # 4. Time Elapsed Urgency (Golden Hour Principle) (0 - 15)
        # Urgency rises as time elapses without active dispatch
        elapsed_hours = self._compute_elapsed_hours(incident.get("created_at"))
        if status in ("PENDING_TRIAGE", "TRIAGED"):
            s_time = min(12.0, 1.8 * math.sqrt(max(0.1, elapsed_hours)))
        elif status == "DISPATCHED":
            # Response underway; urgency stabilized
            s_time = 4.0
        elif status in ("IN_PROGRESS", "ON_SITE"):
            s_time = 2.0
        else: # RESOLVED, CLOSED
            s_time = 0.0

        # Raw composite sum
        composite_raw = s_hazard + s_human + s_infra_total + s_time
        final_risk_score = round(min(100.0, max(5.0, composite_raw)), 1)

        # 5. Priority Classification
        if final_risk_score >= 75.0:
            priority = "P1"
            priority_label = "P1 - CRITICAL / IMMEDIATE LIFE THREAT"
            response_window = "< 15 minutes dispatch target"
        elif final_risk_score >= 55.0:
            priority = "P2"
            priority_label = "P2 - HIGH URGENCY"
            response_window = "15 - 45 minutes dispatch target"
        elif final_risk_score >= 35.0:
            priority = "P3"
            priority_label = "P3 - ELEVATED CONCERN"
            response_window = "45 - 120 minutes dispatch target"
        else:
            priority = "P4"
            priority_label = "P4 - ROUTINE / RECOVERY SUPPORT"
            response_window = "Staged relief distribution"

        breakdown = {
            "hazard_score": round(s_hazard, 1),
            "humanitarian_score": round(s_human, 1),
            "infrastructure_score": round(s_infra_total, 1),
            "time_decay_score": round(s_time, 1),
            "final_score": final_risk_score,
            "priority": priority,
            "priority_label": priority_label,
            "response_window": response_window,
            "elapsed_hours": round(elapsed_hours, 1),
            "trapped_metric": trapped_label,
            "injured_metric": injured_label,
            "vulnerabilities": vuln_breakdown,
            "infrastructure": infra_breakdown,
            "is_provisional": is_provisional,
            "provisional_reasons": provisional_reasons,
            "algorithm_version": "AS-RS-2026.3-EXPERIMENTAL",
            "algorithm_notice": "[EXPERIMENTAL ALGORITHM: MATHEMATICAL MULTI-FACTOR DISASTER RISK METRIC]"
        }

        return breakdown

    def _compute_elapsed_hours(self, created_at_str: Optional[str]) -> float:
        if not created_at_str:
            return 0.5
        try:
            cleaned = created_at_str.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(cleaned)
            now = datetime.datetime.now(datetime.timezone.utc)
            delta = (now - dt).total_seconds() / 3600.0
            return max(0.0, delta)
        except Exception:
            return 0.5

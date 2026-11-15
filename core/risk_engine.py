"""
Akash Setu - Mathematical Emergency Risk-Scoring Engine
Module: core/risk_engine.py

Calculates transparent, multi-factor risk score P in [0, 100]:
  P = 5*S + 5*D + 3*N + 3*T + 2*V + 2*E

Where each factor is rated on a 0-5 scale:
  S: Life-threatening severity (Weight: 25, Multiplier: 5)
  D: Immediate danger          (Weight: 25, Multiplier: 5)
  N: Number of people affected (Weight: 15, Multiplier: 3)
  T: Time sensitivity          (Weight: 15, Multiplier: 3)
  V: Human vulnerability       (Weight: 10, Multiplier: 2)
  E: Escape difficulty         (Weight: 10, Multiplier: 2)

Priority Levels:
  80 - 100: Critical
  60 - 79 : Very High
  40 - 59 : High
  20 - 39 : Moderate
  0  - 19 : Low

Note: These scores are experimental demonstration estimates for an academic prototype.
"""

import math
import datetime
from typing import Dict, Any, Optional, List, Tuple


class RiskScoringEngine:
    """
    Implements the 6-factor mathematical emergency risk scoring model:
    P = 5S + 5D + 3N + 3T + 2V + 2E
    """

    WEIGHTS = {
        "S": 5, # Severity (Max 25)
        "D": 5, # Danger (Max 25)
        "N": 3, # Number of affected (Max 15)
        "T": 3, # Time sensitivity (Max 15)
        "V": 2, # Vulnerability (Max 10)
        "E": 2  # Escape difficulty (Max 10)
    }

    def estimate_factors_from_incident(self, incident: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """
        Estimates the 6 fundamental risk factors (0.0 - 5.0) from incident data.
        Returns None for genuinely unknown factors (strict null preservation).
        """
        disaster_type = (incident.get("disaster_type") or "GENERAL_DISASTER").upper()
        severity_level = (incident.get("severity_level") or "HIGH").upper()
        trapped_count = incident.get("trapped_count")
        injured_count = incident.get("injured_count")
        vulns = incident.get("vulnerable_groups") or []
        infra = incident.get("infrastructure_damaged") or []
        water_level = incident.get("water_level_meters")
        raw_text = (incident.get("raw_text") or incident.get("title") or "").lower()

        # 1. S: Life-Threatening Severity (0 - 5)
        # Assesses phenomenological lethality of the incident
        if any(w in raw_text for w in ["cardiac", "heart attack", "severe bleeding", "bleeding heavily", "unconscious", "suffocating", "cannot breathe", "breathing difficulty", "drowning", "crushed"]):
            S = 5.0
        elif disaster_type in ["BUILDING_COLLAPSE", "FIRE", "GAS_LEAKAGE"]:
            S = 4.5 if severity_level == "CRITICAL" else 4.0
        elif disaster_type in ["FLOOD", "LANDSLIDE"]:
            if water_level and water_level >= 2.0:
                S = 5.0
            elif water_level and water_level >= 1.0:
                S = 4.0
            else:
                S = 3.5
        elif disaster_type == "ROAD_ACCIDENT":
            S = 4.5 if (injured_count and injured_count > 0) else 3.5
        elif disaster_type == "ELECTRICAL_HAZARD":
            S = 4.0
        elif disaster_type == "SHORTAGE":
            S = 2.5
        else:
            S = 3.0 if severity_level == "HIGH" else 2.0

        # 2. D: Immediate Danger (0 - 5)
        # Assesses imminent environmental or biological threat
        if any(w in raw_text for w in ["water rising fast", "fire spreading", "about to give way", "about to collapse", "gas leaking", "flames", "severe bleeding", "bleeding heavily", "cannot breathe", "cardiac", "heart attack"]):
            D = 5.0
        elif any(w in raw_text for w in ["cracks in walls", "submerged", "heavy smoke", "freezing rain"]):
            D = 4.0
        elif disaster_type in ["FIRE", "FLOOD", "GAS_LEAKAGE"]:
            D = 4.0
        elif severity_level == "CRITICAL":
            D = 4.5
        else:
            D = 3.0

        # 3. N: Number of People Affected (0 - 5)
        # Logarithmic scale for affected people
        if trapped_count is not None or injured_count is not None:
            total_affected = (trapped_count or 0) + (injured_count or 0)
            if total_affected >= 20:
                N = 5.0
            elif total_affected >= 10:
                N = 4.0
            elif total_affected >= 5:
                N = 3.0
            elif total_affected >= 2:
                N = 2.0
            elif total_affected == 1:
                N = 1.5 # Single victim
            else:
                N = 1.0
        else:
            # Genuinely unknown affected count -> None!
            N = None

        # 4. T: Time Sensitivity (0 - 5)
        # Golden hour principle
        if any(w in raw_text for w in ["immediately", "urgent", "running out", "hypothermia", "45 minutes", "suffocating", "severe bleeding", "bleeding heavily", "cannot breathe", "cardiac"]):
            T = 5.0
        elif any(w in raw_text for w in ["trapped", "injured", "freezing"]):
            T = 4.0
        elif severity_level in ["CRITICAL", "HIGH"]:
            T = 3.5
        else:
            T = 2.0

        # 5. V: Human Vulnerability (0 - 5)
        # Presence of children, elderly, pregnant, or oxygen-dependent patients
        vuln_points = 1.0
        if "INFANTS_CHILDREN" in vulns or any(w in raw_text for w in ["child", "baby", "infant"]):
            vuln_points += 2.0
        if "PREGNANT_WOMEN" in vulns or "pregnant" in raw_text:
            vuln_points += 2.0
        if "CRITICAL_MEDICAL" in vulns or any(w in raw_text for w in ["dialysis", "oxygen", "cardiac", "severe bleeding", "unconscious", "cannot breathe", "breathing difficulty"]):
            vuln_points += 3.0
        if "ELDERLY" in vulns or any(w in raw_text for w in ["elderly", "aged", "old"]):
            vuln_points += 1.5
        V = min(5.0, vuln_points)

        # 6. E: Escape Difficulty (0 - 5)
        # Trapped under rubble, roof in flood, cut-off mountain ridge, collapsed bridge, or incapacitated patient
        if any(w in raw_text for w in ["under rubble", "bridge washed away", "cut off", "island", "rooftop", "trapped on roof", "in basement"]):
            E = 5.0
        elif any(w in raw_text for w in ["unconscious", "unable to move", "cannot walk", "severe bleeding", "cannot breathe", "bedridden"]):
            E = 4.5
        elif "BRIDGE_COLLAPSE" in infra or "ROAD_HIGHWAY_CUTOFF" in infra:
            E = 4.5
        elif disaster_type in ["BUILDING_COLLAPSE", "FLOOD"]:
            E = 4.0
        elif any(w in raw_text for w in ["stranded", "blocked", "narrow ledge"]):
            E = 3.5
        else:
            E = 2.0

        return {
            "S": round(S, 1),
            "D": round(D, 1),
            "N": round(N, 1) if N is not None else None,
            "T": round(T, 1),
            "V": round(V, 1),
            "E": round(E, 1)
        }

    def calculate_risk(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculates mathematical risk score P = 5S + 5D + 3N + 3T + 2V + 2E
        Handles missing factors using weighted available-factor normalization.
        """
        factors = self.estimate_factors_from_incident(incident)

        S = factors["S"]
        D = factors["D"]
        N = factors["N"]
        T = factors["T"]
        V = factors["V"]
        E = factors["E"]

        is_provisional = False
        reasons = []

        # Check for unknown factors
        # Total possible weight = 25 (S) + 25 (D) + 15 (N) + 15 (T) + 10 (V) + 10 (E) = 100
        available_weight = 0
        weighted_sum = 0.0

        if S is not None:
            weighted_sum += 5.0 * S
            available_weight += 25
            reasons.append(f"Severity S={S:.1f} (+{5.0*S:.1f} pts)")
        else:
            is_provisional = True
            reasons.append("Severity S is unknown")

        if D is not None:
            weighted_sum += 5.0 * D
            available_weight += 25
            reasons.append(f"Immediate Danger D={D:.1f} (+{5.0*D:.1f} pts)")
        else:
            is_provisional = True
            reasons.append("Immediate Danger D is unknown")

        if N is not None:
            weighted_sum += 3.0 * N
            available_weight += 15
            reasons.append(f"Affected People N={N:.1f} (+{3.0*N:.1f} pts)")
        else:
            is_provisional = True
            reasons.append("Affected People N is unstated (provisional score applied; preserved as NULL)")

        if T is not None:
            weighted_sum += 3.0 * T
            available_weight += 15
            reasons.append(f"Time Sensitivity T={T:.1f} (+{3.0*T:.1f} pts)")
        else:
            is_provisional = True
            reasons.append("Time Sensitivity T is unknown")

        if V is not None:
            weighted_sum += 2.0 * V
            available_weight += 10
            reasons.append(f"Human Vulnerability V={V:.1f} (+{2.0*V:.1f} pts)")
        else:
            is_provisional = True
            reasons.append("Vulnerability V is unknown")

        if E is not None:
            weighted_sum += 2.0 * E
            available_weight += 10
            reasons.append(f"Escape Difficulty E={E:.1f} (+{2.0*E:.1f} pts)")
        else:
            is_provisional = True
            reasons.append("Escape Difficulty E is unknown")

        # Weighted Available-Factor Normalization
        if available_weight > 0:
            normalized_score = (weighted_sum / available_weight) * 100.0
        else:
            normalized_score = 50.0

        final_score = round(min(100.0, max(0.0, normalized_score)), 1)

        # Priority Level Mapping
        # 80 - 100: Critical
        # 60 - 79 : Very High
        # 40 - 59 : High
        # 20 - 39 : Moderate
        # 0  - 19 : Low
        if final_score >= 80.0:
            priority = "Critical"
            priority_code = "P1"
            response_window = "< 15 minutes immediate dispatch"
        elif final_score >= 60.0:
            priority = "Very High"
            priority_code = "P2"
            response_window = "15 - 45 minutes urgent dispatch"
        elif final_score >= 40.0:
            priority = "High"
            priority_code = "P3"
            response_window = "45 - 120 minutes priority response"
        elif final_score >= 20.0:
            priority = "Moderate"
            priority_code = "P4"
            response_window = "Staged relief and monitoring"
        else:
            priority = "Low"
            priority_code = "P5"
            response_window = "Standard logistics support"

        return {
            "final_score": final_score,
            "priority": priority_code,
            "priority_label": f"{priority} ({final_score}/100)",
            "priority_tier": priority,
            "response_window": response_window,
            "factors": {
                "S_severity": S,
                "D_danger": D,
                "N_affected": N,
                "T_time": T,
                "V_vulnerability": V,
                "E_escape": E
            },
            "formula": "P = 5S + 5D + 3N + 3T + 2V + 2E",
            "is_provisional": is_provisional,
            "reasons": reasons,
            "algorithm_version": "AS-RS-2026.4-COLLEGE-PROTOTYPE",
            "algorithm_notice": "Academic Prototype Demonstration Estimates — Not for real emergency use."
        }

"""
Akash Setu - Disaster AI Classifier & NLP Extraction Engine
Module: core/classifier.py

Provides dual-mode classification:
1. External LLM (Gemini API) if GEMINI_API_KEY is configured.
2. High-precision Local NLP Rule-based Disaster Engine (autonomous fallback).
   Guarantees 100% offline functionality on air-gapped disaster command servers.

Strict Rule:
Preserves missing counts as None. Never silently coerces unknown trapped/injured to 0.
"""

import os
import re
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List, Tuple


class DisasterClassifier:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")

        # Lexicon for Disaster Category classification
        self.category_keywords = {
            "FLOOD": [
                "flood", "flooding", "water rising", "submerged", "drowning", "river overflow",
                "inundated", "washed away", "flash flood", "cloudburst", "water level", "dam breach",
                "torrential", "overflowing", "deluge", "pali", "nadi", "water surge", "mandakini"
            ],
            "LANDSLIDE": [
                "landslide", "mudslide", "rockfall", "debris flow", "slope failure", "boulder",
                "hill collapsed", "earthslip", "highway blocked by rocks", "sliding hill", "mountain slide"
            ],
            "BUILDING_COLLAPSE": [
                "building collapse", "collapsed roof", "debris", "rubble", "under rubble",
                "crushed structure", "hotel fell", "lodge collapsed", "structural failure",
                "trapped under concrete", "cracked walls", "caved in"
            ],
            "EARTHQUAKE": [
                "earthquake", "tremor", "aftershock", "ground shaking", "richter", "epicenter",
                "seismic", "quake"
            ],
            "FIRE": [
                "fire", "blaze", "burning", "smoke", "flames", "inferno", "forest fire",
                "cylinder blast", "suffocating smoke"
            ],
            "ROAD_ACCIDENT": [
                "road accident", "car crash", "bus accident", "bus fell", "vehicle collision",
                "overturned", "highway crash", "truck accident", "accident", "fell into gorge"
            ],
            "MEDICAL": [
                "medical emergency", "cardiac", "heart attack", "stroke", "bleeding", "severe bleeding",
                "severe fracture", "oxygen", "dialysis", "amputation", "hypothermia", "unconscious",
                "cannot breathe", "breathing difficulty", "head trauma", "snakebite", "diabetic emergency", "asthma"
            ],
            "GAS_LEAKAGE": [
                "gas leak", "gas leakage", "cylinder leak", "toxic fumes", "chemical leak",
                "lpg leak", "poisonous gas", "suffocating gas", "methane leak"
            ],
            "ELECTRICAL_HAZARD": [
                "electrical hazard", "electric shock", "short circuit", "live wire", "high voltage line",
                "transformer blast", "snapped power line", "electrocution", "power wire spark"
            ],
            "SHORTAGE": [
                "food shortage", "water shortage", "no food", "no drinking water", "starvation",
                "starving", "ration running out", "supplies exhausted", "need food and water"
            ],
            "RESCUE_REQUEST": [
                "rescue request", "please rescue", "need evacuation", "stranded", "trapped",
                "send rescue team", "airlift needed", "help immediately", "rescue us"
            ],
            "CYCLONE": [
                "cyclone", "hurricane", "typhoon", "gale winds", "storm surge", "high winds",
                "roof blown off", "uprooted trees"
            ]
        }

        # Critical urgency multipliers
        self.urgency_keywords = {
            "CRITICAL": [
                "immediately", "urgent", "dying", "suffocating", "water rising fast", "oxygen running out",
                "about to collapse", "critical", "children drowning", "cannot breathe", "unconscious",
                "blood loss", "emergency now", "help immediately", "grave danger", "chest deep water"
            ],
            "HIGH": [
                "trapped", "injured", "no food", "stranded", "cut off", "hypothermia", "elderly sick",
                "crying for help", "no power", "shelter destroyed", "rapidly worsen"
            ],
            "MEDIUM": [
                "road blocked", "need supplies", "isolated", "property damage", "phone dead",
                "water entering courtyard", "waiting for rescue"
            ],
            "LOW": [
                "inquiry", "status check", "minor damage", "water receding", "safe for now",
                "requesting general update"
            ]
        }

        # Vulnerable demographics keywords
        self.vulnerability_patterns = {
            "INFANTS_CHILDREN": [r"\bbab(y|ies)\b", r"\binfant(s)?\b", r"\bchild(ren)?\b", r"\btoddler(s)?\b", r"\bkid(s)?\b", r"\bminor(s)?\b"],
            "PREGNANT_WOMEN": [r"\bpregnant\b", r"\blabor\b", r"\blabour\b", r"\bexpecting mother\b"],
            "ELDERLY": [r"\belderly\b", r"\bsenior citizen(s)?\b", r"\bold (man|woman|people|person|folks)\b", r"\baged\b", r"\bgrand(mother|father|parents)\b"],
            "CRITICAL_MEDICAL": [r"\bdialysis\b", r"\boxygen (cylinder|concentrator|running out)\b", r"\binsulin\b", r"\bcardiac patient\b", r"\bventilator\b", r"\bchemotherapy\b"],
            "HYPOTHERMIA_EXPOSURE": [r"\bhypothermia\b", r"\bfreezing\b", r"\bextreme cold\b", r"\bshivering\b", r"\bno blankets\b", r"\bwet clothes in snow\b"]
        }

        # Infrastructure risk markers
        self.infrastructure_patterns = {
            "BRIDGE_COLLAPSE": [
                r"\bbridge\s+(collapsed|washed away|cracked|broken|breached|underwater|submerged)\b",
                r"\bbreached\s+bridge\b",
                r"\bfootbridge\s+(washed away|collapsed)\b"
            ],
            "HOSPITAL_COMPROMISED": [
                r"\bhospital\s+(flooded|collapsed|cut off|evacuated|inundated)\b",
                r"\bhealth\s+cent(re|er)\b",
                r"\bclinic\b",
                r"\bprimary\s+health\b"
            ],
            "POWER_GRID_FAILURE": [
                r"\btransformer\s+(blast|submerged|explosion)\b",
                r"\bpower\s+(outage|failure|cut|line\s+snapped)\b",
                r"\bgenerator\s+(flooded|dead|failed)\b"
            ],
            "DAM_RISK": [
                r"\bdam\s+(overflowing|breach|gates opened|spillway)\b",
                r"\bbarrage\b",
                r"\bretaining\s+wall\b"
            ],
            "ROAD_HIGHWAY_CUTOFF": [
                r"\bhighway\s+(blocked|washed away|buried)\b",
                r"\broad\s+(cave-in|cut off|closed|blocked|washed away)\b"
            ],
            "BUILDING_COLLAPSE_RISK": [
                r"\babout\s+to\s+give\s+way\b",
                r"\bcracks?\s+in\s+walls?\b",
                r"\bstructural\s+(cracks|failure)\b"
            ]
        }

    def classify_emergency(self, raw_text: str, channel: str = "WEB") -> Dict[str, Any]:
        """
        Classifies emergency text.
        Attempts LLM first if configured; always falls back smoothly to deterministic local NLP engine.
        """
        if self.api_key:
            try:
                llm_result = self._call_gemini_api(raw_text)
                if llm_result:
                    return llm_result
            except Exception as e:
                # Silently catch and fall back to local rule-based classifier
                pass

        return self._local_nlp_classifier(raw_text, channel)

    def _call_gemini_api(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """Invokes external Gemini API if an API key is provided."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"
        prompt = f"""
You are Akash Setu AI Disaster Triage Core.
Analyze this emergency message:
"{raw_text}"

Return STRICT JSON with keys:
- disaster_type: one of ["FLOOD", "LANDSLIDE", "BUILDING_COLLAPSE", "EARTHQUAKE", "FIRE", "MEDICAL", "CYCLONE", "GENERAL_DISASTER"]
- severity_level: one of ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
- trapped_count: integer or null if not stated (NEVER assume 0 if unknown)
- injured_count: integer or null if not stated
- casualties_count: integer or null if not stated
- vulnerable_groups: list of ["INFANTS_CHILDREN", "PREGNANT_WOMEN", "ELDERLY", "CRITICAL_MEDICAL", "HYPOTHERMIA_EXPOSURE"]
- infrastructure_damaged: list of damaged infrastructure strings
- water_level_meters: float or null
- confidence: float 0.0 to 1.0
- summary_title: short title
"""
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"response_mime_type": "application/json"}
        }).encode("utf-8")

        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidate = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(candidate)
            parsed["classifier_engine"] = "GEMINI_1.5_FLASH_CLOUD_AI"
            parsed["limitation_notice"] = "Classified via Cloud LLM API."
            return parsed

    def _local_nlp_classifier(self, text: str, channel: str) -> Dict[str, Any]:
        """
        High-precision Deterministic Local NLP Disaster Classification Engine.
        Autonomous, zero network dependencies, 100% transparent.
        """
        text_lower = text.lower()

        # 1. Disaster Category Scoring
        category_scores: Dict[str, int] = {}
        for category, keywords in self.category_keywords.items():
            score = 0
            for kw in keywords:
                if kw in text_lower:
                    score += 2 if len(kw.split()) > 1 else 1
            category_scores[category] = score

        best_category = max(category_scores, key=category_scores.get)
        if category_scores[best_category] == 0:
            best_category = "GENERAL_DISASTER"

        # 2. Entity Extraction: Trapped, Injured, Casualties (STRICT NULL PRESERVATION)
        trapped_count = self._extract_number_with_context(
            text_lower,
            [r"(\d+)\s*(people|persons|pilgrims|tourists|villagers|locals|souls)?\s*(are\s*)?trapped",
             r"trapped\s*(\d+)",
             r"(\d+)\s*(people|persons)?\s*under\s*(the\s*)?(rubble|debris|mud|water)",
             r"stranded\s*(\d+)",
             r"(\d+)\s*(people|persons|passengers)?\s*stranded"]
        )

        injured_count = self._extract_number_with_context(
            text_lower,
            [r"(\d+)\s*(people|persons)?\s*(severely\s*)?(injured|hurt|wounded|bleeding)",
             r"injur(ed|ies)\s*(\d+)",
             r"(\d+)\s*casualties\s*reported"]
        )

        fatalities_count = self._extract_number_with_context(
            text_lower,
            [r"(\d+)\s*(people|persons)?\s*(dead|died|fatalities|bodies|deceased)",
             r"deaths\s*(\d+)"]
        )

        # 3. Extract water level if flood
        water_level_meters = self._extract_water_level(text_lower)

        # 4. Extract vulnerable groups
        detected_vulnerabilities: List[str] = []
        for group, patterns in self.vulnerability_patterns.items():
            for pat in patterns:
                if re.search(pat, text_lower):
                    detected_vulnerabilities.append(group)
                    break

        # 5. Urgency & Severity Scoring (combines keywords, victim volume, and environmental extremes)
        urgency_points = 0
        for kw in self.urgency_keywords["CRITICAL"]:
            if kw in text_lower:
                urgency_points += 4
        for kw in self.urgency_keywords["HIGH"]:
            if kw in text_lower:
                urgency_points += 2
        for kw in self.urgency_keywords["MEDIUM"]:
            if kw in text_lower:
                urgency_points += 1

        # Elevate urgency if extreme hazard conditions detected
        if water_level_meters and water_level_meters >= 2.0:
            urgency_points += 3 # High water level is inherently life-threatening
        if trapped_count and trapped_count >= 10:
            urgency_points += 3 # Mass casualty / mass trapped
        if "INFANTS_CHILDREN" in detected_vulnerabilities or "CRITICAL_MEDICAL" in detected_vulnerabilities:
            urgency_points += 2

        if urgency_points >= 4:
            severity = "CRITICAL"
        elif urgency_points >= 2:
            severity = "HIGH"
        elif urgency_points >= 1:
            severity = "MEDIUM"
        else:
            severity = "LOW"

        # 6. Extract infrastructure damage
        detected_infra: List[str] = []
        for infra, patterns in self.infrastructure_patterns.items():
            for pat in patterns:
                if re.search(pat, text_lower):
                    detected_infra.append(infra)
                    break

        # Generate a clear incident title
        summary_title = self._generate_summary_title(best_category, severity, trapped_count, text)

        confidence = 0.88 if category_scores.get(best_category, 0) > 0 else 0.65

        # Check for satellite burst compression artifact markers
        is_satellite = (channel == "SATELLITE_BURST")

        return {
            "disaster_type": best_category,
            "severity_level": severity,
            "trapped_count": trapped_count,  # None if unspecified!
            "injured_count": injured_count,  # None if unspecified!
            "casualties_count": fatalities_count,  # None if unspecified!
            "vulnerable_groups": detected_vulnerabilities,
            "infrastructure_damaged": detected_infra,
            "water_level_meters": water_level_meters,
            "confidence": confidence,
            "summary_title": summary_title,
            "classifier_engine": "LOCAL_NLP_RULE_BASED (STANDALONE FALLBACK)",
            "limitation_notice": (
                "Using built-in deterministic disaster NLP classifier. "
                "Autonomous, zero cloud API reliance, optimal for air-gapped satellite node."
            )
        }

    def _extract_number_with_context(self, text: str, patterns: List[str]) -> Optional[int]:
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                for grp in match.groups():
                    if grp and grp.isdigit():
                        return int(grp)
        return None

    def _extract_water_level(self, text: str) -> Optional[float]:
        # 1. Matches "water level is 2.8 meters", "water depth 1.5m", "water level 2 meters"
        lvl_match = re.search(r"water\s+(?:level|depth)?\s*(?:is|reaching|up\s+to|of)?\s*(\d+(?:\.\d+)?)\s*(?:meters|meter|mtrs|m)\b", text)
        if lvl_match:
            return float(lvl_match.group(1))

        # 2. Matches "2.8 meters of water", "2.5m flood", "3 meters deep"
        meter_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:meters|meter|mtrs|m)\s*(?:of\s+water|water|deep|high)", text)
        if meter_match:
            return float(meter_match.group(1))

        # 3. Feet measurements: "8 feet of water", "10ft deep"
        feet_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:feet|ft)\s*(?:of\s+water|water|deep|high)", text)
        if feet_match:
            return round(float(feet_match.group(1)) * 0.3048, 2)

        if "neck deep" in text or "chest deep" in text or "chest high" in text:
            return 1.4
        if "waist deep" in text or "waist high" in text:
            return 1.0
        if "knee deep" in text or "knee high" in text:
            return 0.5

        return None

    def _generate_summary_title(self, category: str, severity: str,
                                trapped: Optional[int], text: str) -> str:
        words = text.strip().split()
        snippet = " ".join(words[:6]) + ("..." if len(words) > 6 else "")
        if trapped is not None:
            return f"{severity} {category}: {trapped} persons trapped ({snippet})"
        return f"{severity} {category}: {snippet}"

# Akash Setu (आकाश सेतु)
### Tactical Disaster Response & Satellite Triage Command Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Offline-First](https://img.shields.io/badge/Air--Gapped-Ready-10b981.svg)]()
[![Satellite-Comm](https://img.shields.io/badge/Satellite--Simulator-NavIC%20%7C%20GSAT%20%7C%20Iridium-06b6d4.svg)]()
[![Test-Suite](https://img.shields.io/badge/Automated--Tests-14%20Passing-success.svg)]()

> **Mission Objective**: Akash Setu ("Celestial Bridge") is an emergency disaster response and humanitarian tactical triage system built for extreme crisis zones where cellular towers, power lines, and terrestrial internet have failed. It provides multi-channel emergency message intake, dual-mode AI/NLP classification, multi-factor incident deduplication, a mathematical risk-scoring engine, low-bandwidth satellite burst packet simulation, interactive geospatial mapping, and rescue fleet coordination.

---

## 1. System Architecture

```mermaid
flowchart TD
    subgraph INTAKE["1. Multi-Channel Emergency Intake"]
        A1["Citizen Web SOS"] --> INGEST["Intake Pipeline"]
        A2["Satellite Burst Uplink (NavIC/GSAT/Iridium)"] --> SAT_DEC["Satellite Binary Decoder"] --> INGEST
        A3["Emergency SMS Gateway"] --> INGEST
        A4["HF/VHF Field Radio Relay"] --> INGEST
    end

    subgraph PROVENANCE["2. Verbatim Provenance & Storage"]
        INGEST --> DB_RAW["Raw Messages Store\n(Preserved Verbatim, Strict NULL Retention)"]
    end

    subgraph INTELLIGENCE["3. Automated Triage Engine"]
        DB_RAW --> CLS["Dual-Mode Disaster Classifier\n(Local NLP Heuristic + Optional Gemini Cloud)"]
        CLS --> DUP["Multi-Factor Deduplicator\n(Haversine Distance + Jaccard + Time)"]
        DUP --> RISK["Mathematical Risk-Scoring Engine\n(Hazard + Human + Infra + Time)"]
    end

    subgraph DISPATCH["4. Operations & Command Center"]
        RISK --> QUEUE["Priority Queue (P1, P2, P3, P4)"]
        QUEUE --> MAP["Geospatial Vector Map\n(Mandakini & Chamoli Valley Relief)"]
        QUEUE --> FLEET["Rescue Fleet Dispatcher\n(NDRF, SDRF, IAF Heli, ITBP)"]
        FLEET --> AUDIT["Operational Audit Trail"]
    end
```

---

## 2. Core Functional Modules

### A. Mathematical Risk-Scoring Algorithm (`core/risk_engine.py`)
Every emergency is evaluated by a multi-factor risk model yielding an explainable score $R \in [5, 100]$:

$$R = \min\left(100.0, \max\left(5.0, S_{\text{hazard}} + S_{\text{human}} + S_{\text{infra}} + S_{\text{time}}\right)\right)$$

Where:
1. **Hazard Lethality ($S_{\text{hazard}} \in [10, 35]$)**:
   - Phenomenological base weight: Building Collapse ($32$), Flash Flood ($28$), Landslide ($28$), Fire ($26$), Medical ($25$), Earthquake ($24$), Cyclone ($20$).
   - Scaled by severity rating: Critical ($\times 1.25$), High ($\times 1.0$), Medium ($\times 0.75$), Low ($\times 0.50$).

2. **Humanitarian & Vulnerability Impact ($S_{\text{human}} \in [0, 35]$)**:
   - **Strict Missing-Value Preservation**: If the trapped count $N_{\text{trapped}}$ is unknown, it is **never** silently coerced to zero. Instead, it is preserved as `NULL` and an explicit **Provisional Uncertainty Weight** ($12.0$ points) is applied, tagging the incident with `[PROVISIONAL SCORE APPLIED: CASUALTY DATA PENDING VERIFICATION]`.
   - If verified: $S_{\text{trapped}} = \min(20.0, 4.0 \cdot \ln(1 + N_{\text{trapped}}) + 0.8 \cdot N_{\text{trapped}})$.
   - Vulnerabilities: Infants/Children ($+6.0$), Pregnant Women ($+6.0$), Critical Medical/Dialysis/Oxygen ($+8.0$), Hypothermia ($+5.0$), Elderly ($+4.0$).

3. **Critical Infrastructure & Environmental Surge ($S_{\text{infra}} \in [0, 20]$)**:
   - Dam Breach Risk ($+10.0$), Submerged Hospital ($+8.0$), Bridge Washed Away / Isolation ($+7.0$), Power Grid Failure ($+4.0$).
   - Flood depth factor: $h \ge 2.5\text{m} \implies +8.0$, $1.5\text{m} \le h < 2.5\text{m} \implies +5.0$, $0.5\text{m} \le h < 1.5\text{m} \implies +3.0$.

4. **Time Decay / Golden Hour Escalation ($S_{\text{time}} \in [0, 15]$)**:
   - Urgency scales with elapsed hours $\Delta t$ without response: $S_{\text{time}} = \min(12.0, 1.8 \cdot \sqrt{\Delta t})$.
   - Once a rescue unit is dispatched, urgency stabilizes.

#### Priority Triage Scale:
- **P1 - CRITICAL / IMMEDIATE LIFE THREAT** ($R \ge 80$): Immediate aerial winch/motorboat deployment (< 15 min target).
- **P2 - HIGH URGENCY** ($60 \le R < 80$): Rapid ground rescue deployment (15 - 45 min target).
- **P3 - ELEVATED CONCERN** ($40 \le R < 60$): Resource mobilization and staging.
- **P4 - ROUTINE / RECOVERY SUPPORT** ($R < 40$): Staged relief supply.

---

### B. Dual-Mode AI Disaster Classifier (`core/classifier.py`)
- **Cloud LLM Connector**: Calls the Gemini API if `GEMINI_API_KEY` is configured in the environment.
- **Deterministic Local Disaster NLP Engine (Autonomous Fallback)**: Built-in keyword scoring, entity extraction regexes, and vulnerability analyzers. Requires zero internet connectivity, zero API keys, and guarantees 100% offline functionality on air-gapped disaster command servers.
- **Labels**: Clearly marked with `[CLASSIFICATION_ENGINE: LOCAL_NLP_RULE_BASED (STANDALONE FALLBACK)]`.

---

### C. Multi-Factor Deduplication & Incident Consolidation (`core/deduplication.py`)
In mass casualty events, dozens of panicked relatives and observers submit duplicate reports for the same incident. Akash Setu calculates a transparent similarity score:

$$S_{\text{composite}} = 0.40 \cdot S_{\text{geo}} + 0.25 \cdot S_{\text{text}} + 0.20 \cdot S_{\text{type}} + 0.15 \cdot S_{\text{time}}$$

- **Spatial Proximity ($S_{\text{geo}}$)**: Computed via Haversine great-circle formula:
  $$D = 2R \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta\phi}{2}\right) + \cos\phi_1\cos\phi_2\sin^2\left(\frac{\Delta\lambda}{2}\right)}\right)$$
- If $S_{\text{composite}} \ge 0.72$: Identified as a high-confidence duplicate. The raw message is attached to the primary incident, duplicate count is incremented, and missing values are aggregated without losing provenance.
- If $0.48 \le S_{\text{composite}} < 0.72$: Flagged as `POTENTIAL_CO_INCIDENT` for manual verification.

---

### D. Low-Bandwidth Satellite Communication Simulator (`core/satellite_sim.py`)
Simulates tactical emergency satellite uplinks over constrained radio channels (1200 - 2400 bps):
1. **Binary Packet Compactor**:
   - 17-byte fixed header: Magic (`0x4153`), Version, Flags, 32-bit fixed-point Latitude/Longitude ($\approx 0.1$m precision), Disaster Enum, Packed Casualties Nibbles, Vulnerability Bitmask, Water Level in decimeters.
   - Variable DEFLATE compressed text payload.
   - CRC-16-CCITT checksum for corruption detection.
   - **Compression Performance**: Compresses $\approx 280$ bytes of JSON down to $45 - 55$ bytes ($> 75\%$ bandwidth reduction).
2. **RF Link Budget & Constellation Modeling**:
   - Profiles: NavIC / IRNSS (ISRO S-Band), GSAT-7A (ISRO Tactical), Iridium-NEXT (LEO).
   - Simulates Rain Fade attenuation (0 to 10 dB) based on cloudburst conditions.
   - Calculates effective Signal-to-Noise Ratio (SNR) and Link Margin.
   - Models Automatic Repeat reQuest (ARQ) retransmission when packet loss occurs.
   - Live Hex Dump terminal viewer with byte-by-byte telemetry.
- **Notice**: All transmissions are explicitly labeled `[SIMULATED SATELLITE BURST: LINK METRICS SYNTHESIZED FOR OFFLINE NODE]`.

---

### E. Rescue Fleet & Mission Control Dashboard
- **Fleet Roster**: Coordinates NDRF (Flood Rescue), SDRF (Mountain Rescue), IAF 152 Helicopter Unit (ALH Dhruv Mk-III), ITBP (Collapse Search), Red Cross Emergency Surgery Unit, and Civil Defence.
- **Dispatch Workflow**: Assigns specialized teams to incidents, tracks team capacity, equipment inventory, and logs every action in the immutable audit trail.

---

### F. Interactive Geospatial Map (`static/js/map.js`)
- **100% Offline Vector Canvas Engine**: Custom cartographic engine rendering the Himalayan disaster relief terrain (Mandakini and Alaknanda rivers, Kedarnath shrine, Gaurikund, Sonprayag, Guptkashi, Joshimath, Karnaprayag).
- **Features**: Pan, zoom, color-coded priority pins, pulsing danger beacons for P1 critical incidents, rescue team coverage rings, and interactive tooltips.

---

## 3. Realistic Disaster Scenario Dataset

Pre-configured with a realistic **Mandakini Valley & Chamoli Himalayan Cloudburst Crisis**:
- **16 Realistic Incidents**: Rooftop flooding at Sonprayag, landslide crushing vehicles at Gaurikund, Agastyamuni PHC generator failure with oxygen-dependent patients, hypothermic trekkers near Tungnath, bus stranded at Banswara, and high-altitude bridge cutoffs.
- **Includes Duplicate Clusters**: Tests both automated deduplication and manual consolidation.
- **Includes Unverified Victim Counts**: Demonstrates strict `NULL` preservation and provisional uncertainty scoring.
- **6 Specialized Field Rescue Teams**: Initialized with tactical bases, equipment inventories, and operational radio call-signs.

---

## 4. How to Run Locally

### Prerequisites
- **Python 3.10+** (Python 3.12 recommended).
- **Zero external packages required**: The application runs entirely on Python's built-in standard library (`http.server`, `sqlite3`, `zlib`, `struct`, `urllib`).

### Step 1: Clone or Navigate to Project
```powershell
cd "C:\Users\Vinay M\.gemini\antigravity\scratch\akash-setu"
```

### Step 2: Launch the Mission Control Server
```powershell
python server.py 8080
```
*Or double-click `run_app.bat` on Windows.*

### Step 3: Open in Browser
Navigate to:
```
http://localhost:8080
```

---

## 5. Running Automated Tests

Run the full verification test suite:
```powershell
python tests\test_all.py
```
This runs 14 automated unit and integration tests covering:
- Verbatim raw message preservation.
- Strict `NULL` casualty preservation (never 0).
- Local NLP classifier and water level extraction.
- Haversine distance and multi-factor duplicate detection.
- Mathematical risk-scoring and provisional uncertainty scoring.
- Binary satellite packet compaction, CRC16 verification, and decoding.
- Constellation link budget and ARQ retransmission.
- REST API request handling and triage flow.

---

## 6. Disclosures, Alternatives & Limitations

In accordance with system design constraints:
1. **Satellite Transmissions**: Real physical satellite transmitters require dedicated RF hardware (such as an ISRO NavIC S-band receiver module or Iridium 9603 transceiver) and licensed spectrum. Akash Setu implements an authentic binary packet encoder, Link Margin/Rain Fade RF physics simulator, and ARQ protocol that mirrors real hardware behavior. All outputs are clearly tagged with `[SIMULATED SATELLITE BURST]`.
2. **AI Classification**: While cloud LLM support (Gemini) is built-in via `GEMINI_API_KEY`, the platform defaults to an autonomous, high-precision Local Disaster NLP Engine so that field operations centers retain 100% functionality during complete internet blackouts.
3. **Cartography**: In air-gapped disaster scenarios where external map tile servers are unreachable, the platform utilizes a built-in high-precision Geospatial Vector Canvas with true GPS projections.
4. **Data Integrity**: In compliance with humanitarian disaster response standards, unknown casualty counts are strictly preserved as `NULL` and receive a provisional uncertainty weight; missing numbers are never assumed to be zero.

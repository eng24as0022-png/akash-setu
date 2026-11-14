/**
 * Akash Setu - Satellite Communications Simulator Interface
 * Module: static/js/satellite.js
 *
 * Real-time packet compressor, link margin estimator, burst transmitter,
 * and hex dump telemetry inspector.
 */

class SatelliteSimulatorUI {
    constructor(app) {
        this.app = app;
        this.initElements();
        this.initEvents();
        this.refreshStatus();
    }

    initElements() {
        this.msgInput = document.getElementById("satBurstMsgInput");
        this.constellationSelect = document.getElementById("satConstellationSelect");
        this.rainFadeSlider = document.getElementById("satRainFadeSlider");
        this.rainFadeVal = document.getElementById("satRainFadeVal");
        this.forceLossCheck = document.getElementById("satForceLossCheck");
        this.btnTransmit = document.getElementById("btnSatTransmitBurst");
        
        // Gauges & telemetry displays
        this.gaugeRawBytes = document.getElementById("gaugeRawBytes");
        this.gaugeCompBytes = document.getElementById("gaugeCompBytes");
        this.gaugeCompPct = document.getElementById("gaugeCompPct");
        this.gaugeSnr = document.getElementById("gaugeSnr");
        this.gaugeMargin = document.getElementById("gaugeMargin");
        this.compMeterFill = document.getElementById("compMeterFill");
        this.hexTerminal = document.getElementById("satHexDumpTerminal");
        this.recentPacketsTable = document.getElementById("satRecentPacketsBody");
    }

    initEvents() {
        if (this.msgInput) {
            this.msgInput.addEventListener("input", () => this.updateByteEstimates());
        }

        if (this.rainFadeSlider) {
            this.rainFadeSlider.addEventListener("input", (e) => {
                const val = parseFloat(e.target.value);
                this.rainFadeVal.textContent = `${val.toFixed(1)} dB`;
                this.updateLinkBudgetPreview(val);
            });
        }

        if (this.btnTransmit) {
            this.btnTransmit.addEventListener("click", () => this.transmitBurst());
        }
    }

    updateByteEstimates() {
        const text = this.msgInput.value.trim();
        const rawBytes = text.length > 0 ? (text.length + 120) : 120;
        // Approximation of Akash Setu compact binary packet
        const compBytes = text.length > 0 ? (19 + Math.min(64, Math.floor(text.length * 0.45))) : 19;
        const ratio = Math.max(0, 1.0 - (compBytes / rawBytes));
        const pct = Math.round(ratio * 100);

        if (this.gaugeRawBytes) this.gaugeRawBytes.textContent = `${rawBytes} B`;
        if (this.gaugeCompBytes) this.gaugeCompBytes.textContent = `${compBytes} B`;
        if (this.gaugeCompPct) this.gaugeCompPct.textContent = `${pct}%`;
        if (this.compMeterFill) this.compMeterFill.style.width = `${pct}%`;
    }

    updateLinkBudgetPreview(rainFadeDb) {
        const constel = this.constellationSelect ? this.constellationSelect.value : "NAVIC_DISASTER_BURST";
        const nominalSnr = constel === "GSAT_7A_TACTICAL" ? 18.2 : (constel === "IRIDIUM_NEXT_SBD" ? 13.0 : 15.5);
        const nominalMargin = constel === "GSAT_7A_TACTICAL" ? 9.5 : (constel === "IRIDIUM_NEXT_SBD" ? 5.4 : 7.2);

        const estSnr = Math.max(2.0, nominalSnr - rainFadeDb);
        const estMargin = Math.max(-3.0, nominalMargin - rainFadeDb);

        if (this.gaugeSnr) {
            this.gaugeSnr.textContent = `${estSnr.toFixed(1)} dB`;
            this.gaugeSnr.style.color = estSnr < 8.0 ? "#ef4444" : "#38bdf8";
        }
        if (this.gaugeMargin) {
            this.gaugeMargin.textContent = `${estMargin.toFixed(1)} dB`;
            this.gaugeMargin.style.color = estMargin < 1.0 ? "#ef4444" : "#10b981";
        }
    }

    async transmitBurst() {
        const text = this.msgInput.value.trim();
        if (!text) {
            this.app.showToast("Please enter an emergency burst message.", "error");
            return;
        }

        const constellation = this.constellationSelect.value;
        const rainFade = parseFloat(this.rainFadeSlider.value);
        const forceLoss = this.forceLossCheck ? this.forceLossCheck.checked : false;

        this.btnTransmit.disabled = true;
        this.btnTransmit.textContent = "Uplinking to Satellite...";
        this.hexTerminal.textContent = "[UPLINK IN PROGRESS] Modulating packet into S-band burst...\nConnecting to satellite transponder...";

        try {
            const resp = await fetch("/api/satellite/transmit", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: jsonString({
                    raw_text: text,
                    constellation: constellation,
                    simulated_rain_fade_db: rainFade,
                    force_packet_loss: forceLoss,
                    latitude: 30.6315,
                    longitude: 79.0028,
                    location_name: "Sonprayag Satellite Field Terminal",
                    district: "Rudraprayag"
                })
            });

            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error || "Burst transmission failed");

            const t = data.transmission;
            this.displayHexDump(t);
            this.app.showToast(
                `Burst ${t.packet_id} ${t.status}: ${t.compressed_bytes_count} bytes (${t.compression_pct}% reduction)`,
                "sat"
            );

            // Clear input & refresh queues
            this.msgInput.value = "";
            this.updateByteEstimates();
            this.refreshStatus();
            this.app.loadIncidents();
            this.app.loadAnalytics();

        } catch (err) {
            this.app.showToast(`Transmission error: ${err.message}`, "error");
            this.hexTerminal.textContent = `[TRANSMISSION ERROR] ${err.message}`;
        } finally {
            this.btnTransmit.disabled = false;
            this.btnTransmit.textContent = "Transmit Satellite Burst Packet 📡";
        }
    }

    displayHexDump(tx) {
        const lines = [
            `================================================================`,
            `  AKASH SETU SATELLITE BURST TELEMETRY - ${tx.packet_id}`,
            `================================================================`,
            `Status:            ${tx.status} ${tx.retransmissions > 0 ? '(ARQ Retransmit Succeeded)' : '(First Pass)'}`,
            `Constellation:     ${tx.constellation_name}`,
            `Payload Reduction: ${tx.raw_bytes_count} Bytes ➔ ${tx.compressed_bytes_count} Bytes (${tx.compression_pct}%)`,
            `Radio SNR:         ${tx.snr_db} dB  |  Link Margin: ${tx.link_margin_db} dB`,
            `Elevation Angle:   ${tx.elevation_deg}°  |  Rain Attenuation: ${tx.rain_fade_db} dB`,
            `Uplink Latency:    ${tx.transmission_time_ms} ms (Simulated Speed: 1200 bps)`,
            `Notice:            ${tx.simulation_badge}`,
            `----------------------------------------------------------------`,
            `RAW BINARY PACKET HEX DUMP (Format: AS-Protocol-v1):`,
            tx.hex_payload,
            `----------------------------------------------------------------`,
            `DECODED TELEMETRY FIELDS:`,
            `Lat/Lon:          ${tx.decoded_payload.latitude.toFixed(6)}°N, ${tx.decoded_payload.longitude.toFixed(6)}°E`,
            `Hazard Type:      ${tx.decoded_payload.disaster_type}`,
            `Trapped:          ${tx.decoded_payload.trapped_count !== null ? tx.decoded_payload.trapped_count : 'UNKNOWN (NULL PRESERVED)'}`,
            `Injured:          ${tx.decoded_payload.injured_count !== null ? tx.decoded_payload.injured_count : 'UNKNOWN (NULL PRESERVED)'}`,
            `Water Level:      ${tx.decoded_payload.water_level_meters !== null ? tx.decoded_payload.water_level_meters + ' m' : 'N/A'}`,
            `CRC Checksum:     ${tx.decoded_payload.crc_valid ? 'VALID [0xOK]' : 'CHECKSUM_FAILED'}`,
            `Payload Text:     "${tx.decoded_payload.raw_text}"`,
            `================================================================`
        ];
        this.hexTerminal.textContent = lines.join("\n");
    }

    async refreshStatus() {
        try {
            const resp = await fetch("/api/satellite/status");
            const data = await resp.json();
            this.renderRecentTable(data.recent_transmissions || []);
        } catch (err) {
            console.error("Failed to fetch satellite status", err);
        }
    }

    renderRecentTable(logs) {
        if (!this.recentPacketsTable) return;
        if (logs.length === 0) {
            this.recentPacketsTable.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-dim);padding:1rem;">No satellite transmissions logged yet.</td></tr>`;
            return;
        }

        this.recentPacketsTable.innerHTML = logs.map(l => {
            const timeStr = new Date(l.timestamp).toLocaleTimeString();
            const statusClass = l.status === "DELIVERED" ? "text-emerald" : (l.status === "RETRANSMITTED" ? "text-amber" : "text-crit");
            return `
                <tr>
                    <td style="font-family:var(--font-mono);color:#38bdf8;">${l.packet_id}</td>
                    <td>${l.constellation.split('_')[0]}</td>
                    <td>${l.raw_bytes_count}B ➔ <strong style="color:#fff;">${l.compressed_bytes_count}B</strong></td>
                    <td style="color:#10b981;font-weight:700;">${Math.round(l.compression_ratio * 100)}%</td>
                    <td>${l.snr_db} dB</td>
                    <td style="font-family:var(--font-mono);">${l.transmission_time_ms} ms</td>
                    <td class="${statusClass}"><strong>${l.status}</strong></td>
                </tr>
            `;
        }).join("");
    }
}

function jsonString(obj) {
    return JSON.stringify(obj);
}

window.SatelliteSimulatorUI = SatelliteSimulatorUI;

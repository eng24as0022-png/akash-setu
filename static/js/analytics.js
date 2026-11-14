/**
 * Akash Setu - Disaster Analytics & KPI Engine
 * Module: static/js/analytics.js
 *
 * Self-contained HTML5 Canvas chart renderer (zero external library dependency).
 * Renders priority distributions, disaster category donuts, status pipelines,
 * and humanitarian casualty tallies.
 */

class AkashAnalyticsEngine {
    constructor() {
        this.data = null;
    }

    render(summaryData) {
        this.data = summaryData;
        if (!summaryData) return;

        this.updateKPIs(summaryData);
        this.renderPriorityChart("chartPriorityCanvas", summaryData.priority_distribution || {});
        this.renderCategoryDonut("chartCategoryCanvas", summaryData.disaster_type_distribution || {});
        this.renderStatusPipeline("chartStatusCanvas", summaryData.status_distribution || {});
    }

    updateKPIs(data) {
        const hum = data.humanitarian_impact || {};
        const sat = data.satellite_network || {};

        this.setText("kpiTotalTrapped", hum.total_trapped ?? 0);
        this.setText("kpiTotalInjured", hum.total_injured ?? 0);
        this.setText("kpiTotalFatalities", hum.total_fatalities ?? 0);
        this.setText("kpiUnknownTrapped", hum.incidents_with_unknown_trapped_count ?? 0);

        this.setText("kpiSatPackets", sat.total_packets ?? 0);
        this.setText("kpiSatCompression", `${sat.avg_compression_pct ?? 0}%`);
        this.setText("kpiSatLatency", `${sat.avg_latency_ms ?? 0} ms`);
        this.setText("kpiSatLossRecovered", sat.loss_events_recovered ?? 0);
    }

    setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    renderPriorityChart(canvasId, priorities) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width = canvas.parentElement.clientWidth || 360;
        const h = canvas.height = 220;

        ctx.clearRect(0, 0, w, h);

        const keys = ["P1", "P2", "P3", "P4"];
        const colors = ["#ef4444", "#f59e0b", "#eab308", "#38bdf8"];
        const labels = ["P1 Critical", "P2 Urgent", "P3 Elevated", "P4 Standard"];
        const values = keys.map(k => priorities[k] || 0);
        const maxVal = Math.max(1, ...values);

        const barWidth = 44;
        const spacing = (w - (barWidth * 4)) / 5;

        // Draw axes lines
        ctx.strokeStyle = "#1e293b";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(30, 20);
        ctx.lineTo(30, h - 35);
        ctx.lineTo(w - 20, h - 35);
        ctx.stroke();

        for (let i = 0; i < 4; i++) {
            const x = spacing + i * (barWidth + spacing);
            const barH = (values[i] / maxVal) * (h - 75);
            const y = (h - 35) - barH;

            // Bar fill
            ctx.fillStyle = colors[i];
            ctx.beginPath();
            ctx.roundRect(x, y, barWidth, barH, [4, 4, 0, 0]);
            ctx.fill();

            // Value text
            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 12px ui-monospace, monospace";
            ctx.textAlign = "center";
            ctx.fillText(values[i], x + barWidth / 2, y - 6);

            // Label text
            ctx.fillStyle = "#94a3b8";
            ctx.font = "10px sans-serif";
            ctx.fillText(keys[i], x + barWidth / 2, h - 18);
        }
    }

    renderCategoryDonut(canvasId, types) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width = canvas.parentElement.clientWidth || 360;
        const h = canvas.height = 220;

        ctx.clearRect(0, 0, w, h);

        const keys = Object.keys(types);
        const values = Object.values(types);
        const total = values.reduce((a, b) => a + b, 0);

        if (total === 0) {
            ctx.fillStyle = "#64748b";
            ctx.textAlign = "center";
            ctx.fillText("No disaster data recorded", w / 2, h / 2);
            return;
        }

        const colors = ["#0284c7", "#f59e0b", "#ef4444", "#10b981", "#8b5cf6", "#ec4899", "#64748b"];
        const centerX = w * 0.35;
        const centerY = h / 2;
        const radius = Math.min(centerX, centerY) - 15;
        const innerRadius = radius * 0.58;

        let startAngle = -Math.PI / 2;

        for (let i = 0; i < keys.length; i++) {
            const sliceAngle = (values[i] / total) * (Math.PI * 2);
            const endAngle = startAngle + sliceAngle;

            ctx.fillStyle = colors[i % colors.length];
            ctx.beginPath();
            ctx.arc(centerX, centerY, radius, startAngle, endAngle);
            ctx.arc(centerX, centerY, innerRadius, endAngle, startAngle, true);
            ctx.closePath();
            ctx.fill();

            startAngle = endAngle;
        }

        // Center total text
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 16px ui-monospace, monospace";
        ctx.textAlign = "center";
        ctx.fillText(total, centerX, centerY + 2);
        ctx.font = "9px sans-serif";
        ctx.fillStyle = "#94a3b8";
        ctx.fillText("INCIDENTS", centerX, centerY + 16);

        // Legend on right
        const legendX = w * 0.65;
        ctx.textAlign = "left";
        ctx.font = "11px sans-serif";

        for (let i = 0; i < Math.min(6, keys.length); i++) {
            const ly = 35 + i * 26;
            ctx.fillStyle = colors[i % colors.length];
            ctx.fillRect(legendX, ly - 9, 10, 10);

            ctx.fillStyle = "#e2e8f0";
            const label = keys[i].replace("_", " ").toLowerCase();
            const capLabel = label.charAt(0).toUpperCase() + label.slice(1);
            ctx.fillText(`${capLabel} (${values[i]})`, legendX + 16, ly);
        }
    }

    renderStatusPipeline(canvasId, statuses) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        const w = canvas.width = canvas.parentElement.clientWidth || 360;
        const h = canvas.height = 220;

        ctx.clearRect(0, 0, w, h);

        const stages = [
            { key: "PENDING_TRIAGE", label: "Triage Intake", color: "#f59e0b" },
            { key: "DISPATCHED", label: "Dispatched", color: "#0ea5e9" },
            { key: "IN_PROGRESS", label: "On Scene / Action", color: "#8b5cf6" },
            { key: "RESOLVED", label: "Resolved / Safe", color: "#10b981" }
        ];

        const rowHeight = 36;
        const maxVal = Math.max(1, ...stages.map(s => statuses[s.key] || 0));

        stages.forEach((s, idx) => {
            const y = 25 + idx * (rowHeight + 12);
            const val = statuses[s.key] || 0;
            const barW = Math.max(20, (val / maxVal) * (w - 180));

            // Stage Label
            ctx.fillStyle = "#cbd5e1";
            ctx.font = "11px sans-serif";
            ctx.textAlign = "left";
            ctx.fillText(s.label, 20, y + 14);

            // Bar background
            ctx.fillStyle = "#1e293b";
            ctx.beginPath();
            ctx.roundRect(130, y, w - 160, 20, 4);
            ctx.fill();

            // Progress Bar
            ctx.fillStyle = s.color;
            ctx.beginPath();
            ctx.roundRect(130, y, barW, 20, 4);
            ctx.fill();

            // Count text
            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 11px ui-monospace, monospace";
            ctx.textAlign = "right";
            ctx.fillText(`${val} units`, w - 38, y + 14);
        });
    }
}

window.AkashAnalyticsEngine = AkashAnalyticsEngine;

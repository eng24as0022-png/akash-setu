/**
 * Akash Setu - Central Mission Control Application
 * Module: static/js/app.js
 *
 * Coordinates triage intake, geospatial mapping, fleet dispatch,
 * duplicate consolidation, and satellite link simulations.
 */

class AkashSetuApp {
    constructor() {
        this.incidents = [];
        this.teams = [];
        this.selectedIncidentId = null;
        this.activeTab = "triage";

        this.initTabs();
        this.initFilterEvents();
        this.initSOSForm();
        this.initDemoReset();

        // Initialize sub-engines
        this.mapEngine = new AkashMapEngine("disasterMapCanvas", (inc) => this.selectIncident(inc.id));
        this.analyticsEngine = new AkashAnalyticsEngine();
        this.satelliteUI = new SatelliteSimulatorUI(this);

        // Initial Data Load
        this.refreshAll();

        // Auto-refresh poll every 8 seconds for real-time mission status
        setInterval(() => this.backgroundPoll(), 8000);
    }

    initTabs() {
        const tabBtns = document.querySelectorAll(".nav-tab-btn");
        tabBtns.forEach(btn => {
            btn.addEventListener("click", () => {
                const targetView = btn.dataset.view;
                this.switchTab(targetView);
            });
        });
    }

    switchTab(tabName) {
        this.activeTab = tabName;

        // Update button states
        document.querySelectorAll(".nav-tab-btn").forEach(b => {
            b.classList.toggle("active", b.dataset.view === tabName);
        });

        // Update view visibility
        document.querySelectorAll(".view-panel").forEach(p => {
            p.classList.toggle("active", p.id === `view-${tabName}`);
        });

        if (tabName === "map") {
            setTimeout(() => {
                this.mapEngine.resize();
                this.mapEngine.setData(this.incidents, this.teams);
            }, 50);
        } else if (tabName === "analytics") {
            this.loadAnalytics();
        } else if (tabName === "satellite") {
            this.satelliteUI.refreshStatus();
        }
    }

    initFilterEvents() {
        const filterPriority = document.getElementById("filterPriority");
        const filterStatus = document.getElementById("filterStatus");
        const filterType = document.getElementById("filterType");
        const searchInput = document.getElementById("searchIncidentInput");

        const onChange = () => this.loadIncidents();

        if (filterPriority) filterPriority.addEventListener("change", onChange);
        if (filterStatus) filterStatus.addEventListener("change", onChange);
        if (filterType) filterType.addEventListener("change", onChange);
        if (searchInput) searchInput.addEventListener("input", () => this.debounce(onChange, 300)());
    }

    debounce(fn, delay) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn(...args), delay);
        };
    }

    initSOSForm() {
        const form = document.getElementById("sosIntakeForm");
        if (!form) return;

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById("btnSubmitSOS");
            submitBtn.disabled = true;
            submitBtn.textContent = "Processing & Triaging...";

            try {
                // Collect form fields
                const rawText = document.getElementById("sosRawText").value.trim();
                const locationName = document.getElementById("sosLocationName").value.trim();
                const latVal = document.getElementById("sosLatitude").value;
                const lonVal = document.getElementById("sosLongitude").value;
                const trappedVal = document.getElementById("sosTrappedCount").value;
                const injuredVal = document.getElementById("sosInjuredCount").value;
                const waterVal = document.getElementById("sosWaterLevel").value;
                const contactVal = document.getElementById("sosContact").value.trim();
                const channelVal = document.getElementById("sosChannel").value;

                // Vulnerabilities
                const vulnChecks = document.querySelectorAll("input[name='sosVuln']:checked");
                const vulnGroups = Array.from(vulnChecks).map(c => c.value);

                const payload = {
                    raw_text: rawText,
                    location_name: locationName || "Uttarakhand Disaster Sector",
                    latitude: latVal ? parseFloat(latVal) : 30.6315,
                    longitude: lonVal ? parseFloat(lonVal) : 79.0028,
                    trapped_count: trappedVal !== "" ? parseInt(trappedVal) : null, // NULL preservation
                    injured_count: injuredVal !== "" ? parseInt(injuredVal) : null,
                    water_level_meters: waterVal !== "" ? parseFloat(waterVal) : null,
                    sender_contact: contactVal || "Citizen SOS",
                    channel: channelVal,
                    vulnerable_groups: vulnGroups
                };

                const resp = await fetch("/api/emergency/submit", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                const data = await resp.json();
                if (!resp.ok) throw new Error(data.error || "Failed to submit emergency report");

                if (data.is_duplicate_merged) {
                    this.showToast(
                        `Report auto-consolidated into Incident ${data.duplicate_metrics.incident_code} (${data.duplicate_metrics.confidence_pct}% match)!`,
                        "success"
                    );
                } else {
                    this.showToast(`Emergency logged: ${data.incident.incident_code} [Priority ${data.incident.priority_level}]`, "success");
                }

                form.reset();
                this.loadIncidents();
                this.loadAnalytics();
                this.switchTab("triage");
                this.selectIncident(data.incident_id);

            } catch (err) {
                this.showToast(`Submission Error: ${err.message}`, "error");
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "Submit Emergency Triage Report 🚨";
            }
        });
    }

    initDemoReset() {
        const btnReset = document.getElementById("btnResetDemo");
        if (btnReset) {
            btnReset.addEventListener("click", async () => {
                if (!confirm("Reset Akash Setu database to fresh Himalayan disaster scenario?")) return;
                btnReset.textContent = "Resetting...";
                try {
                    const resp = await fetch("/api/system/reset-demo", { method: "POST" });
                    const data = await resp.json();
                    this.showToast(data.message, "success");
                    this.refreshAll();
                } catch (err) {
                    this.showToast(`Reset error: ${err.message}`, "error");
                } finally {
                    btnReset.textContent = "↺ Reset Scenario";
                }
            });
        }
    }

    async refreshAll() {
        await Promise.all([
            this.loadIncidents(),
            this.loadTeams(),
            this.loadAnalytics()
        ]);
    }

    async backgroundPoll() {
        // Silent background refresh
        try {
            await this.loadIncidents(true);
            await this.loadTeams(true);
        } catch (e) {}
    }

    async loadIncidents(isSilent = false) {
        const p = document.getElementById("filterPriority")?.value || "ALL";
        const s = document.getElementById("filterStatus")?.value || "ALL";
        const t = document.getElementById("filterType")?.value || "ALL";
        const q = document.getElementById("searchIncidentInput")?.value || "";

        const params = new URLSearchParams();
        if (p !== "ALL") params.append("priority", p);
        if (s !== "ALL") params.append("status", s);
        if (t !== "ALL") params.append("disaster_type", t);
        if (q) params.append("search", q);

        try {
            const resp = await fetch(`/api/incidents?${params.toString()}`);
            const data = await resp.json();
            this.incidents = data.incidents || [];

            this.renderIncidentQueue();
            this.mapEngine.setData(this.incidents, this.teams);
            this.updateHeaderKPIs();

            // Auto-select top incident if none selected
            if (!this.selectedIncidentId && this.incidents.length > 0) {
                this.selectIncident(this.incidents[0].id);
            }
        } catch (err) {
            if (!isSilent) this.showToast(`Failed to load incidents: ${err.message}`, "error");
        }
    }

    updateHeaderKPIs() {
        const p1Count = this.incidents.filter(i => i.priority_level === "P1" && i.status !== "RESOLVED" && i.status !== "CLOSED").length;
        const totalActive = this.incidents.filter(i => i.status !== "RESOLVED" && i.status !== "CLOSED").length;
        const deployedTeams = this.teams.filter(t => t.status === "DISPATCHED" || t.status === "ON_SITE").length;

        let trappedSum = 0;
        this.incidents.forEach(i => {
            if (i.trapped_count !== null && i.status !== "RESOLVED" && i.status !== "CLOSED") {
                trappedSum += i.trapped_count;
            }
        });

        this.setText("headerKpiP1", p1Count);
        this.setText("headerKpiActive", totalActive);
        this.setText("headerKpiTeams", deployedTeams);
        this.setText("headerKpiTrapped", trappedSum);

        const p1TabBadge = document.getElementById("badgeTabP1");
        if (p1TabBadge) {
            p1TabBadge.textContent = p1Count;
            p1TabBadge.classList.toggle("active-p1", p1Count > 0);
        }
    }

    renderIncidentQueue() {
        const container = document.getElementById("incidentQueueContainer");
        if (!container) return;

        if (this.incidents.length === 0) {
            container.innerHTML = `
                <div style="text-align:center;padding:3rem 1rem;color:var(--text-dim);">
                    <h3>No incidents matching criteria</h3>
                    <p style="font-size:0.85rem;margin-top:0.4rem;">Adjust filters or submit a new emergency report.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.incidents.map(inc => {
            const isSelected = inc.id === this.selectedIncidentId ? "selected" : "";
            const priorityClass = inc.priority_level.toLowerCase();

            // Strict Null Preservation in display
            const trappedText = inc.trapped_count !== null ? `${inc.trapped_count} Trapped` : "Trapped Count Unconfirmed (NULL)";
            const waterText = inc.water_level_meters !== null ? ` • 🌊 ${inc.water_level_meters}m Flood` : "";

            const vulns = inc.vulnerable_groups || [];
            const vulnTags = vulns.slice(0, 3).map(v => `<span class="tag-vuln">${v}</span>`).join("");

            const dupBadge = inc.duplicate_count > 0 ? `<span class="tag-infra">${inc.duplicate_count} DUPLICATES LINKED</span>` : "";

            return `
                <div class="incident-card ${priorityClass} ${isSelected}" onclick="app.selectIncident(${inc.id})">
                    <div class="card-top">
                        <span class="card-code">${inc.incident_code}</span>
                        <div class="card-badges">
                            <span class="priority-pill ${priorityClass}">${inc.priority_level}</span>
                            <span class="status-pill">${inc.status}</span>
                        </div>
                    </div>
                    <div class="card-title">${this.escapeHtml(inc.title)}</div>
                    <div class="card-meta">
                        <span class="card-meta-item">📍 ${this.escapeHtml(inc.location_name)}</span>
                        <span class="card-meta-item">⚠️ ${inc.disaster_type}</span>
                        <span class="card-meta-item">👥 ${trappedText}${waterText}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div class="card-tags">
                            ${vulnTags}
                            ${dupBadge}
                        </div>
                        <div class="card-risk-score" style="color:${this.getRiskColor(inc.risk_score)};">
                            ${inc.risk_score}<span style="font-size:0.7rem;color:var(--text-dim);">/100</span>
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    }

    async selectIncident(incidentId) {
        this.selectedIncidentId = incidentId;
        this.renderIncidentQueue();

        const drawer = document.getElementById("incidentDetailPanel");
        if (!drawer) return;

        try {
            const resp = await fetch(`/api/incidents/${incidentId}`);
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error);

            this.renderDetailDrawer(data.incident);
        } catch (err) {
            drawer.innerHTML = `<div style="color:var(--p1-crit);padding:1rem;">Failed to load incident details: ${err.message}</div>`;
        }
    }

    renderDetailDrawer(inc) {
        const drawer = document.getElementById("incidentDetailPanel");
        if (!drawer) return;

        const pClass = inc.priority_level.toLowerCase();
        const math = inc.risk_breakdown || {};
        const meta = inc.ai_classification_meta || {};

        // Available rescue teams for dispatch dropdown
        const availableTeams = this.teams.filter(t => t.status === "AVAILABLE");
        const teamOptions = availableTeams.map(t => `<option value="${t.id}">${t.name} (${t.agency})</option>`).join("");

        // Timeline items
        const timelineHtml = (inc.updates || []).map(u => `
            <div class="timeline-item">
                <div class="timeline-time">${new Date(u.timestamp).toLocaleTimeString()} - ${this.escapeHtml(u.author)}</div>
                <div style="color:#f1f5f9;margin-top:2px;">${this.escapeHtml(u.message)}</div>
            </div>
        `).join("");

        // Raw messages section strictly verbatim
        const rawMsgsHtml = (inc.raw_messages || []).map(m => `
            <div class="raw-message-box">
                <div class="raw-msg-header">
                    <span>TRANSMISSION CHANNEL: ${m.channel}</span>
                    <span>SENDER: ${this.escapeHtml(m.sender_contact || 'Unknown')}</span>
                    <span>${new Date(m.received_at).toLocaleTimeString()}</span>
                </div>
                <div>"${this.escapeHtml(m.raw_text)}"</div>
            </div>
        `).join("");

        drawer.innerHTML = `
            <div class="detail-header">
                <div class="detail-code-row">
                    <span class="card-code" style="font-size:0.95rem;">${inc.incident_code}</span>
                    <div style="display:flex;gap:0.4rem;">
                        <span class="priority-pill ${pClass}">${inc.priority_level}</span>
                        <span class="status-pill">${inc.status}</span>
                    </div>
                </div>
                <div class="detail-title">${this.escapeHtml(inc.title)}</div>
                <div style="font-size:0.8rem;color:var(--text-muted);margin-top:0.3rem;">
                    📍 ${this.escapeHtml(inc.location_name)}, ${this.escapeHtml(inc.district)} [${inc.latitude.toFixed(4)}°N, ${inc.longitude.toFixed(4)}°E]
                </div>
            </div>

            <!-- 1. Preserved Raw Emergency Text Verbatim -->
            <div class="section-label">📜 Verbatim Raw Message Intake (Preserved Proof)</div>
            ${rawMsgsHtml || '<div style="color:var(--text-dim);font-size:0.8rem;">No raw message recorded.</div>'}

            <!-- 2. Mathematical Risk-Scoring Audit Trace -->
            <div class="section-label">📐 Mathematical Risk Score Algorithm (AS-RS-2026.3)</div>
            <div class="math-risk-card">
                <div class="math-title">
                    <span>COMPOSITE RISK R = ${inc.risk_score} / 100</span>
                    <span style="font-size:0.75rem;color:var(--text-dim);">${math.response_window || ''}</span>
                </div>
                <div class="math-formula-box">
                    Formula: R = min(100, S_hazard + S_human + S_infra + S_time)
                </div>
                <div class="math-grid">
                    <div class="math-stat">
                        <div class="math-stat-label">Hazard Factor</div>
                        <div class="math-stat-val">${math.hazard_score ?? 0} pts (${inc.disaster_type})</div>
                    </div>
                    <div class="math-stat">
                        <div class="math-stat-label">Humanitarian / Victims</div>
                        <div class="math-stat-val">${math.humanitarian_score ?? 0} pts</div>
                    </div>
                    <div class="math-stat">
                        <div class="math-stat-label">Critical Infrastructure</div>
                        <div class="math-stat-val">${math.infrastructure_score ?? 0} pts</div>
                    </div>
                    <div class="math-stat">
                        <div class="math-stat-label">Time Escalation</div>
                        <div class="math-stat-val">${math.time_decay_score ?? 0} pts (${math.elapsed_hours ?? 0} hrs elapsed)</div>
                    </div>
                </div>
                ${math.is_provisional ? `
                    <div class="provisional-badge">
                        ⚠️ <strong>[PROVISIONAL SCORE APPLIED]</strong><br>
                        ${(math.provisional_reasons || []).join("<br>")}
                    </div>
                ` : ''}
                <div style="font-size:0.7rem;color:var(--text-dim);margin-top:0.4rem;">
                    Notice: ${math.algorithm_notice || '[MATHEMATICAL MULTI-FACTOR DISASTER RISK METRIC]'}
                </div>
            </div>

            <!-- 3. AI / NLP Classifier Meta -->
            <div class="section-label">🤖 NLP Classifier Meta & Entities</div>
            <div style="background:#172239;border:1px solid var(--border-color);padding:0.7rem;border-radius:6px;font-size:0.75rem;margin-bottom:1rem;">
                <div>Engine: <strong style="color:#38bdf8;">${meta.classifier_engine || 'LOCAL_NLP_RULE_BASED'}</strong> (Confidence: ${Math.round((meta.confidence || 0.85)*100)}%)</div>
                <div style="color:var(--text-dim);margin-top:2px;">${meta.limitation_notice || ''}</div>
                <div style="margin-top:0.4rem;display:flex;gap:0.4rem;flex-wrap:wrap;">
                    <span class="equip-chip">Trapped: ${inc.trapped_count !== null ? inc.trapped_count : 'UNKNOWN (NULL)'}</span>
                    <span class="equip-chip">Injured: ${inc.injured_count !== null ? inc.injured_count : 'UNKNOWN (NULL)'}</span>
                    <span class="equip-chip">Water: ${inc.water_level_meters !== null ? inc.water_level_meters + 'm' : 'N/A'}</span>
                </div>
            </div>

            <!-- 4. Team Dispatch & Status Actions -->
            <div class="section-label">🚁 Dispatch & Mission Assignment</div>
            <div class="dispatch-action-box">
                ${inc.assigned_team_name ? `
                    <div style="background:#0f172a;padding:0.6rem;border-radius:4px;border-left:3px solid #10b981;margin-bottom:0.7rem;">
                        <div style="font-size:0.72rem;color:var(--text-dim);">ASSIGNED RESCUE TEAM</div>
                        <div style="font-weight:700;color:#fff;font-size:0.9rem;">${this.escapeHtml(inc.assigned_team_name)}</div>
                        <div style="font-size:0.75rem;color:#38bdf8;">${inc.assigned_team_agency} • ${inc.assigned_team_contact}</div>
                    </div>
                ` : `
                    <div style="margin-bottom:0.7rem;">
                        <label style="font-size:0.75rem;color:var(--text-muted);display:block;margin-bottom:0.25rem;">Select Available Rescue Team:</label>
                        <select id="selectDispatchTeam" class="filter-select" style="width:100%;margin-bottom:0.5rem;">
                            ${teamOptions || '<option value="">No teams currently available</option>'}
                        </select>
                        <button class="btn-primary" onclick="app.dispatchTeamToSelected(${inc.id})" ${availableTeams.length === 0 ? 'disabled' : ''}>
                            Dispatch Rescue Unit 🚁
                        </button>
                    </div>
                `}

                <div style="display:flex;gap:0.5rem;align-items:center;margin-top:0.5rem;">
                    <label style="font-size:0.75rem;color:var(--text-muted);white-space:nowrap;">Update Status:</label>
                    <select id="selectUpdateStatus" class="filter-select" style="flex:1;" onchange="app.updateSelectedStatus(${inc.id}, this.value)">
                        <option value="PENDING_TRIAGE" ${inc.status === 'PENDING_TRIAGE' ? 'selected' : ''}>PENDING TRIAGE</option>
                        <option value="TRIAGED" ${inc.status === 'TRIAGED' ? 'selected' : ''}>TRIAGED</option>
                        <option value="DISPATCHED" ${inc.status === 'DISPATCHED' ? 'selected' : ''}>DISPATCHED</option>
                        <option value="IN_PROGRESS" ${inc.status === 'IN_PROGRESS' ? 'selected' : ''}>IN PROGRESS / ON SITE</option>
                        <option value="RESOLVED" ${inc.status === 'RESOLVED' ? 'selected' : ''}>RESOLVED / SAFE</option>
                        <option value="CLOSED" ${inc.status === 'CLOSED' ? 'selected' : ''}>CLOSED (CONSOLIDATED)</option>
                    </select>
                </div>
            </div>

            <!-- 5. Operational Audit Trail -->
            <div class="section-label">⏱️ Operational Audit Log</div>
            <div class="timeline-container">
                ${timelineHtml}
            </div>
        `;
    }

    async dispatchTeamToSelected(incidentId) {
        const select = document.getElementById("selectDispatchTeam");
        if (!select || !select.value) return;

        const teamId = parseInt(select.value);
        try {
            const resp = await fetch(`/api/incidents/${incidentId}/dispatch`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ team_id: teamId, author: "Mission Commander", notes: "Emergency operational dispatch" })
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error);

            this.showToast("Rescue team dispatched successfully!", "success");
            this.refreshAll();
            this.selectIncident(incidentId);
        } catch (err) {
            this.showToast(`Dispatch failed: ${err.message}`, "error");
        }
    }

    async updateSelectedStatus(incidentId, newStatus) {
        try {
            const resp = await fetch(`/api/incidents/${incidentId}/status`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: newStatus, author: "Disaster Operations Lead" })
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error);

            this.showToast(`Status updated to ${newStatus}`, "success");
            this.refreshAll();
            this.selectIncident(incidentId);
        } catch (err) {
            this.showToast(`Status update failed: ${err.message}`, "error");
        }
    }

    async loadTeams(isSilent = false) {
        try {
            const resp = await fetch("/api/teams");
            const data = await resp.json();
            this.teams = data.teams || [];
            this.renderTeamsRoster();
            this.mapEngine.setData(this.incidents, this.teams);
            this.updateHeaderKPIs();
        } catch (err) {
            if (!isSilent) this.showToast(`Failed to load rescue teams: ${err.message}`, "error");
        }
    }

    renderTeamsRoster() {
        const container = document.getElementById("teamsGridContainer");
        if (!container) return;

        container.innerHTML = this.teams.map(tm => {
            const isAvail = tm.status === "AVAILABLE";
            const statusClass = isAvail ? "available" : "dispatched";

            const equipChips = (tm.equipment || []).map(e => `<span class="equip-chip">${e.replace(/_/g, ' ')}</span>`).join("");

            return `
                <div class="team-card ${statusClass}">
                    <div>
                        <div class="team-agency">${tm.agency} • ${tm.team_code}</div>
                        <div class="team-name">${this.escapeHtml(tm.name)}</div>
                        <div style="font-size:0.8rem;color:var(--text-muted);margin-bottom:0.4rem;">
                            Leader: ${this.escapeHtml(tm.leader_name)} | 📞 ${tm.contact}
                        </div>
                        <div style="font-size:0.75rem;color:var(--text-dim);margin-bottom:0.6rem;">
                            Base: ${this.escapeHtml(tm.base_location)} • Capacity: ${tm.capacity_persons} pax
                        </div>
                        <div style="font-size:0.75rem;color:var(--text-muted);font-weight:600;margin-bottom:0.2rem;">Equipment Inventory:</div>
                        <div class="team-equipment-list">
                            ${equipChips}
                        </div>
                        ${tm.assigned_incident_code ? `
                            <div style="background:rgba(245,158,11,0.15);border:1px solid rgba(245,158,11,0.3);padding:0.4rem 0.6rem;border-radius:4px;font-size:0.75rem;color:#fde68a;margin-top:0.6rem;">
                                Assigned Mission: <strong>${tm.assigned_incident_code}</strong> - ${this.escapeHtml(tm.assigned_incident_title || '')}
                            </div>
                        ` : ''}
                    </div>

                    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:1rem;border-top:1px solid var(--border-color);padding-top:0.75rem;">
                        <span class="status-pill" style="color:${isAvail ? '#10b981' : '#f59e0b'};">${tm.status}</span>
                        <div style="display:flex;gap:0.4rem;">
                            <button class="btn-secondary" style="font-size:0.72rem;" onclick="app.setTeamStatus(${tm.id}, '${isAvail ? 'STANDBY' : 'AVAILABLE'}')">
                                ${isAvail ? 'Set Standby' : 'Set Available'}
                            </button>
                        </div>
                    </div>
                </div>
            `;
        }).join("");
    }

    async setTeamStatus(teamId, newStatus) {
        try {
            const resp = await fetch(`/api/teams/${teamId}/status`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ status: newStatus })
            });
            const data = await resp.json();
            if (!resp.ok) throw new Error(data.error);

            this.showToast(`Team status set to ${newStatus}`, "success");
            this.loadTeams();
        } catch (err) {
            this.showToast(`Failed: ${err.message}`, "error");
        }
    }

    async loadAnalytics() {
        try {
            const resp = await fetch("/api/analytics");
            const data = await resp.json();
            this.analyticsEngine.render(data);
        } catch (err) {
            console.error("Failed to load analytics", err);
        }
    }

    getRiskColor(score) {
        if (score >= 80) return "var(--p1-crit)";
        if (score >= 60) return "var(--p2-high)";
        if (score >= 40) return "var(--p3-med)";
        return "var(--p4-low)";
    }

    showToast(message, type = "info") {
        const container = document.getElementById("toastContainer");
        if (!container) return;

        const toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.innerHTML = `
            <span>${type === 'error' ? '❌' : (type === 'sat' ? '📡' : '✅')}</span>
            <span>${this.escapeHtml(message)}</span>
        `;

        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, 4500);
    }

    setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    escapeHtml(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}

window.addEventListener("DOMContentLoaded", () => {
    window.app = new AkashSetuApp();
});

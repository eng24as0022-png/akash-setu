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
        this.authToken = localStorage.getItem("akash_commander_token");
        this.authEmail = localStorage.getItem("akash_commander_email") || "eng24as0022@dsu.edu.in";

        this.initHeroButtons();
        this.initTabs();
        this.initFilterEvents();
        this.initSOSForm();
        this.initDemoReset();
        this.initAuth();

        // Initialize sub-engines
        this.mapEngine = new AkashMapEngine("disasterMapCanvas", (inc) => this.selectIncident(inc.id));
        this.analyticsEngine = new AkashAnalyticsEngine();
        this.satelliteUI = new SatelliteSimulatorUI(this);

        // Initial Data Load
        this.refreshAll();
        this.updateAuthUI();

        // Auto-refresh poll every 7 seconds for real-time mission status
        setInterval(() => this.backgroundPoll(), 7000);
    }

    initHeroButtons() {
        const btnSOS = document.getElementById("heroBtnSOS");
        const btnLogin = document.getElementById("heroBtnLogin");

        if (btnSOS) {
            btnSOS.addEventListener("click", () => {
                this.switchTab("sos");
                const nameInput = document.getElementById("sosPersonName");
                if (nameInput) nameInput.focus();
                // Ensure form is visible and confirmation card hidden for new report
                const confCard = document.getElementById("sosConfirmationCard");
                const form = document.getElementById("sosIntakeForm");
                if (confCard) confCard.style.display = "none";
                if (form) form.style.display = "block";
            });
        }

        if (btnLogin) {
            btnLogin.addEventListener("click", () => {
                if (this.authToken) {
                    this.switchTab("triage");
                    this.showToast(`Active Rescue Commander session: ${this.authEmail}`, "success");
                } else {
                    const modal = document.getElementById("authModal");
                    if (modal) modal.style.display = "flex";
                }
            });
        }
    }

    initAuth() {
        const btnAuth = document.getElementById("btnCommanderAuth");
        const modal = document.getElementById("authModal");
        const btnCloseModal = document.getElementById("btnCloseAuthModal");
        const btnModalSubmit = document.getElementById("btnModalSubmitAuth");
        const emailInput = document.getElementById("modalRescueEmail");
        const passwordInput = document.getElementById("modalAuthPasscodeInput");
        const btnFleetLogin = document.getElementById("btnFleetLogin");
        const fleetInput = document.getElementById("fleetAuthPasscodeInput");

        if (btnAuth) {
            btnAuth.addEventListener("click", () => {
                if (this.authToken) {
                    if (confirm(`Logged in as ${this.authEmail}. Sign out of Rescue Commander mode?`)) {
                        this.logoutCommander();
                    }
                } else {
                    modal.style.display = "flex";
                    if (emailInput) emailInput.focus();
                }
            });
        }

        if (btnCloseModal) {
            btnCloseModal.addEventListener("click", () => {
                modal.style.display = "none";
                const errBox = document.getElementById("loginErrorAlert");
                if (errBox) errBox.style.display = "none";
            });
        }

        const handleModalLogin = () => {
            const email = (emailInput ? emailInput.value : "").trim();
            const password = (passwordInput ? passwordInput.value : "").trim();
            this.loginRescueTeam(email, password);
        };

        if (btnModalSubmit) {
            btnModalSubmit.addEventListener("click", handleModalLogin);
        }

        if (passwordInput) {
            passwordInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter") handleModalLogin();
            });
        }

        if (emailInput) {
            emailInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter" && passwordInput) passwordInput.focus();
            });
        }

        if (btnFleetLogin) {
            btnFleetLogin.addEventListener("click", () => {
                const code = fleetInput.value.trim();
                this.loginRescueTeam("eng24as0022@dsu.edu.in", code);
            });
        }

        if (fleetInput) {
            fleetInput.addEventListener("keydown", (e) => {
                if (e.key === "Enter") {
                    this.loginRescueTeam("eng24as0022@dsu.edu.in", fleetInput.value.trim());
                }
            });
        }
    }

    async loginRescueTeam(email, password) {
        const errBox = document.getElementById("loginErrorAlert");
        if (errBox) errBox.style.display = "none";

        if (!email && !password) {
            this.showToast("Please enter your rescue email and password", "error");
            return;
        }

        try {
            const resp = await fetch("/api/auth/login", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ email: email, password: password })
            });

            const data = await resp.json();
            if (!resp.ok) {
                const msg = data.error || "Authentication failed";
                if (errBox) {
                    errBox.textContent = `❌ ${msg}`;
                    errBox.style.display = "block";
                }
                throw new Error(msg);
            }

            this.authToken = data.token;
            this.authEmail = data.email || email;
            localStorage.setItem("akash_commander_token", data.token);
            localStorage.setItem("akash_commander_email", this.authEmail);

            const modal = document.getElementById("authModal");
            if (modal) modal.style.display = "none";

            this.updateAuthUI();
            this.showToast(`🛡️ Rescue Commander Authorized: ${this.authEmail}`, "success");

            this.refreshAll();
            if (this.selectedIncidentId) {
                this.selectIncident(this.selectedIncidentId);
            }
        } catch (err) {
            this.showToast(`Authentication Denied: ${err.message}`, "error");
        }
    }

    logoutCommander() {
        this.authToken = null;
        this.authEmail = null;
        localStorage.removeItem("akash_commander_token");
        localStorage.removeItem("akash_commander_email");
        this.updateAuthUI();
        this.showToast("Logged out of Rescue Team Mode. Public read-only view active.", "info");
        this.refreshAll();
        if (this.selectedIncidentId) {
            this.selectIncident(this.selectedIncidentId);
        }
    }

    updateAuthUI() {
        const btnAuth = document.getElementById("btnCommanderAuth");
        const lockScreen = document.getElementById("fleetLockScreen");
        const fleetGrid = document.getElementById("teamsGridContainer");
        const statusBadge = document.getElementById("fleetAuthStatusBadge");

        if (btnAuth) {
            if (this.authToken) {
                btnAuth.innerHTML = `🛡️ ${this.authEmail || 'Commander'} <span style='font-size:0.7rem;color:#fca5a5;'>[Logout]</span>`;
                btnAuth.style.borderColor = "#10b981";
                btnAuth.style.color = "#10b981";
            } else {
                btnAuth.innerHTML = "🛡️ Rescue Team Login";
                btnAuth.style.borderColor = "#38bdf8";
                btnAuth.style.color = "#38bdf8";
            }
        }

        if (lockScreen && fleetGrid && statusBadge) {
            if (this.authToken) {
                lockScreen.style.display = "none";
                fleetGrid.style.display = "grid";
                statusBadge.textContent = `🟢 Authenticated: ${this.authEmail}`;
                statusBadge.style.color = "#10b981";
            } else {
                lockScreen.style.display = "block";
                fleetGrid.style.display = "none";
                statusBadge.textContent = "🔒 Authentication Required";
                statusBadge.style.color = "var(--p2-high)";
            }
        }
    }

    getAuthHeaders() {
        const headers = { "Content-Type": "application/json" };
        if (this.authToken) {
            headers["Authorization"] = `Bearer ${this.authToken}`;
        }
        return headers;
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
        const confCard = document.getElementById("sosConfirmationCard");
        const btnAnother = document.getElementById("btnSubmitAnotherSOS");

        if (btnAnother) {
            btnAnother.addEventListener("click", () => {
                if (confCard) confCard.style.display = "none";
                if (form) {
                    form.style.display = "block";
                    form.reset();
                    const nameInput = document.getElementById("sosPersonName");
                    if (nameInput) nameInput.focus();
                }
            });
        }

        if (!form) return;

        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById("btnSubmitSOS");
            submitBtn.disabled = true;
            submitBtn.textContent = "Processing & Triaging SOS...";

            try {
                // Collect ONLY the 3 required fields from form
                const personName = (document.getElementById("sosPersonName")?.value || "").trim();
                const locationName = (document.getElementById("sosLocationName")?.value || "").trim();
                const description = (document.getElementById("sosDescription")?.value || "").trim();

                if (!description) {
                    throw new Error("Emergency description ('What Happened?') is required.");
                }

                const payload = {
                    name: personName || "Concerned Citizen",
                    location: locationName || "Uttarakhand Disaster Sector",
                    description: description
                };

                const resp = await fetch("/api/emergency/submit", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                const data = await resp.json();
                if (!resp.ok) throw new Error(data.error || "Failed to submit emergency report");

                // Populate confirmation card
                this.setText("confMessageId", data.message_id || "AS-SOS-RECEIVED");
                this.setText("confIncidentCode", data.incident_code || (data.incident ? data.incident.incident_code : "AS-INC-NEW"));
                
                const priorityTier = data.priority_tier || (data.incident ? data.incident.priority_level : "P1");
                const priorityLabel = priorityTier === "P1" ? "Critical Priority (P1) — Immediate Dispatch" : `${priorityTier} Priority`;
                this.setText("confPriority", priorityLabel);

                // Show confirmation card and hide input form
                form.style.display = "none";
                if (confCard) confCard.style.display = "block";

                if (data.is_duplicate_merged) {
                    this.showToast(
                        `Report auto-consolidated into Incident ${data.duplicate_metrics.incident_code} (${data.duplicate_metrics.confidence_pct}% match)!`,
                        "success"
                    );
                } else {
                    this.showToast(`Emergency SOS logged: ${data.message_id} [${priorityTier}]`, "success");
                }

                // Refresh incidents and analytics in background
                this.loadIncidents(true);
                this.loadAnalytics();

            } catch (err) {
                this.showToast(`Submission Error: ${err.message}`, "error");
            } finally {
                submitBtn.disabled = false;
                submitBtn.textContent = "🚨 SEND SOS / REQUEST HELP";
            }
        });
    }

    initDemoReset() {
        const btnReset = document.getElementById("btnResetDemo");
        if (btnReset) {
            btnReset.addEventListener("click", async () => {
                if (!this.authToken) {
                    this.showToast("🔒 Commander Login Required: Please authenticate to reset scenario.", "error");
                    document.getElementById("authModal").style.display = "flex";
                    return;
                }

                if (!confirm("Reset Akash Setu database to fresh Himalayan disaster scenario?")) return;
                btnReset.textContent = "Resetting...";
                try {
                    const resp = await fetch("/api/system/reset-demo", {
                        method: "POST",
                        headers: this.getAuthHeaders()
                    });
                    const data = await resp.json();
                    if (!resp.ok) throw new Error(data.error);
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

            // Priority & Recency Sorting:
            // 1. Active unrescued emergencies first (0); successfully rescued (RESOLVED, CLOSED) move down to bottom (1)
            // 2. Task priority remains as before (P1 > P2 > P3 > P4 > P5)
            // 3. Within same priority, recent requests appear first (created_at DESC, id DESC)
            const prioRank = { 'P1': 1, 'P2': 2, 'P3': 3, 'P4': 4, 'P5': 5 };
            this.incidents.sort((a, b) => {
                const aRes = (a.status === 'RESOLVED' || a.status === 'CLOSED') ? 1 : 0;
                const bRes = (b.status === 'RESOLVED' || b.status === 'CLOSED') ? 1 : 0;
                if (aRes !== bRes) return aRes - bRes;

                const aP = prioRank[a.priority_level] || 9;
                const bP = prioRank[b.priority_level] || 9;
                if (aP !== bP) return aP - bP;

                const aTime = new Date(a.created_at || 0).getTime();
                const bTime = new Date(b.created_at || 0).getTime();
                if (aTime !== bTime) return bTime - aTime;

                return (b.id || 0) - (a.id || 0);
            });

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

    async updateHeaderKPIs() {
        const p1Count = this.incidents.filter(i => (i.priority_level === "P1" || (i.risk_score && i.risk_score >= 80)) && i.status !== "RESOLVED" && i.status !== "CLOSED").length;
        const highPriorityCount = this.incidents.filter(i => (i.priority_level === "P2" || i.priority_level === "P3" || (i.risk_score && i.risk_score >= 40 && i.risk_score < 80)) && i.status !== "RESOLVED" && i.status !== "CLOSED").length;
        const pendingCount = this.incidents.filter(i => i.status !== "RESOLVED" && i.status !== "CLOSED").length;
        const resolvedCount = this.incidents.filter(i => i.status === "RESOLVED" || i.status === "CLOSED").length;

        // Fetch authoritative analytics if available
        try {
            const resp = await fetch("/api/analytics");
            if (resp.ok) {
                const data = await resp.json();
                this.setText("kpiTotalSOS", data.total_sos_reports ?? data.total_messages ?? (this.incidents.length + 5));
                this.setText("kpiTotalIncidents", data.total_incidents ?? this.incidents.length);
                this.setText("headerKpiP1", data.critical_incidents ?? p1Count);
                this.setText("headerKpiActive", data.high_priority_incidents ?? highPriorityCount);
                this.setText("kpiPendingIncidents", data.pending_incidents ?? pendingCount);
                this.setText("kpiResolvedIncidents", data.resolved_incidents ?? resolvedCount);
                return;
            }
        } catch (e) {}

        // Fallback to client-side count
        this.setText("kpiTotalSOS", this.incidents.length);
        this.setText("kpiTotalIncidents", this.incidents.length);
        this.setText("headerKpiP1", p1Count);
        this.setText("headerKpiActive", highPriorityCount);
        this.setText("kpiPendingIncidents", pendingCount);
        this.setText("kpiResolvedIncidents", resolvedCount);
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

        let hasRenderedResolvedSeparator = false;
        container.innerHTML = this.incidents.map(inc => {
            const isSelected = inc.id === this.selectedIncidentId ? "selected" : "";
            const isRescued = inc.status === "RESOLVED" || inc.status === "CLOSED";
            const priorityClass = inc.priority_level.toLowerCase();
            const cardResolvedClass = isRescued ? "resolved-card" : "";

            let separatorHtml = "";
            if (isRescued && !hasRenderedResolvedSeparator) {
                hasRenderedResolvedSeparator = true;
                separatorHtml = `
                    <div style="display:flex;align-items:center;gap:0.75rem;margin:1.25rem 0 0.75rem 0;color:#10b981;font-size:0.78rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;">
                        <span style="flex:1;height:1px;background:#10b981;opacity:0.4;"></span>
                        <span>🔻 Rescued Incidents (Moved Down Below Active Emergencies)</span>
                        <span style="flex:1;height:1px;background:#10b981;opacity:0.4;"></span>
                    </div>
                `;
            }

            // Strict Null Preservation in display
            const trappedText = inc.trapped_count !== null ? `${inc.trapped_count} Trapped` : "Trapped Count Unconfirmed (NULL)";
            const waterText = inc.water_level_meters !== null ? ` • 🌊 ${inc.water_level_meters}m Flood` : "";

            const vulns = inc.vulnerable_groups || [];
            const vulnTags = vulns.slice(0, 3).map(v => `<span class="tag-vuln">${v}</span>`).join("");

            const dupBadge = inc.duplicate_count > 0 ? `<span class="tag-infra">${inc.duplicate_count} DUPLICATES LINKED</span>` : "";

            return separatorHtml + `
                <div class="incident-card ${priorityClass} ${isSelected} ${cardResolvedClass}" onclick="app.selectIncident(${inc.id})" style="${isRescued ? 'opacity:0.7;border-left:4px solid #10b981;background:rgba(16,185,129,0.06);' : ''}">
                    <div class="card-top">
                        <span class="card-code">${inc.incident_code}</span>
                        <div class="card-badges">
                            <span class="priority-pill ${priorityClass}">${inc.priority_level}</span>
                            <span class="status-pill" style="${isRescued ? 'color:#10b981;border-color:#10b981;background:rgba(16,185,129,0.15);font-weight:700;' : ''}">${isRescued ? 'RESCUED / SAFE ✅' : inc.status}</span>
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
                            ${isRescued ? '<span class="tag-infra" style="color:#10b981;border-color:#10b981;font-weight:700;">MOVED DOWN (RESCUED)</span>' : ''}
                        </div>
                        <div style="display:flex;gap:0.4rem;align-items:center;">
                            ${!isRescued ? `
                                <button class="btn-secondary" style="font-size:0.72rem;padding:0.25rem 0.55rem;color:#10b981;border:1px solid #10b981;background:rgba(16,185,129,0.1);font-weight:700;border-radius:4px;cursor:pointer;" onclick="app.markRescued(${inc.id}, event)" title="Mark as successfully rescued and move down">
                                    ✅ Rescued
                                </button>
                            ` : ''}
                            <div class="card-risk-score" style="color:${this.getRiskColor(inc.risk_score)};">
                                ${inc.risk_score}<span style="font-size:0.7rem;color:var(--text-dim);">/100</span>
                            </div>
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

            <!-- ⚡ PROMINENT RESCUE & RESOLUTION BAR (TOP OF DRAWER) -->
            <div style="background:linear-gradient(135deg, rgba(16,185,129,0.15) 0%, rgba(15,23,42,0.95) 100%);border:1px solid #10b981;border-radius:8px;padding:0.85rem;margin-bottom:1rem;box-shadow:0 4px 16px rgba(0,0,0,0.3);">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;">
                    <span style="font-size:0.85rem;font-weight:700;color:#fff;">⚡ Operational Rescue Action:</span>
                    <span class="status-pill" style="font-size:0.75rem;color:${inc.status === 'RESOLVED' ? '#10b981' : '#f59e0b'};border-color:${inc.status === 'RESOLVED' ? '#10b981' : 'rgba(245,158,11,0.4)'};">CURRENT: ${inc.status}</span>
                </div>
                ${inc.status !== 'RESOLVED' && inc.status !== 'CLOSED' ? `
                    <button class="btn-primary" style="width:100%;background:linear-gradient(135deg, #059669 0%, #10b981 100%);border:none;padding:0.75rem;font-size:0.95rem;font-weight:800;display:flex;justify-content:center;align-items:center;gap:0.5rem;box-shadow:0 0 15px rgba(16,185,129,0.35);cursor:pointer;" onclick="app.updateSelectedStatus(${inc.id}, 'RESOLVED')">
                        ✅ Mark Rescue Completed / Resolved (Moves Down)
                    </button>
                    <div style="display:flex;gap:0.5rem;align-items:center;margin-top:0.65rem;">
                        <label style="font-size:0.75rem;color:var(--text-muted);white-space:nowrap;">Change Status:</label>
                        <select class="filter-select" style="flex:1;" onchange="app.updateSelectedStatus(${inc.id}, this.value)">
                            <option value="PENDING_TRIAGE" ${inc.status === 'PENDING_TRIAGE' ? 'selected' : ''}>PENDING TRIAGE</option>
                            <option value="TRIAGED" ${inc.status === 'TRIAGED' ? 'selected' : ''}>TRIAGED</option>
                            <option value="DISPATCHED" ${inc.status === 'DISPATCHED' ? 'selected' : ''}>DISPATCHED</option>
                            <option value="IN_PROGRESS" ${inc.status === 'IN_PROGRESS' ? 'selected' : ''}>IN PROGRESS / ON SITE</option>
                            <option value="RESOLVED">RESOLVED / SAFE (MOVES DOWN)</option>
                        </select>
                    </div>
                ` : `
                    <div style="padding:0.7rem;background:rgba(16,185,129,0.2);border:1px solid #10b981;border-radius:6px;color:#a7f3d0;font-size:0.85rem;text-align:center;font-weight:700;">
                        ✅ Rescued & Resolved: This incident has been successfully resolved and moved down to the bottom of the queue.
                    </div>
                    <div style="margin-top:0.5rem;text-align:center;">
                        <button class="btn-secondary" style="font-size:0.72rem;padding:0.3rem 0.6rem;color:#38bdf8;border-color:rgba(56,189,248,0.4);" onclick="app.updateSelectedStatus(${inc.id}, 'PENDING_TRIAGE')">
                            ↺ Reopen Incident (Move Back Up to Active)
                        </button>
                    </div>
                `}
            </div>

            <!-- 1. Preserved Raw Emergency Text Verbatim -->
            <div class="section-label">📜 Verbatim Raw Message Intake (Preserved Proof)</div>
            ${rawMsgsHtml || '<div style="color:var(--text-dim);font-size:0.8rem;">No raw message recorded.</div>'}

            <!-- Consolidated Report Provenance Badge -->
            <div style="background:rgba(56,189,248,0.1);border:1px solid rgba(56,189,248,0.3);border-radius:6px;padding:0.6rem 0.8rem;margin:0.75rem 0;font-size:0.78rem;color:#bae6fd;">
                🔗 <strong>Incident Consolidation Status:</strong> ${(inc.duplicate_count || 0) + 1} citizen message(s) consolidated into this single incident using formula <code style="color:#38bdf8;">M = 0.35L + 0.20T + 0.25C + 0.20D</code> without double-counting casualties.
            </div>

            <!-- 2. Mathematical Risk-Scoring Audit Trace (6-Factor Model) -->
            <div class="section-label">📐 Mathematical Risk-Scoring Engine (AS-RS-2026.4)</div>
            <div class="math-risk-card">
                <div class="math-title">
                    <span>COMPOSITE RISK SCORE P = ${inc.risk_score} / 100</span>
                    <span style="font-size:0.75rem;color:var(--text-dim);">${math.response_window || 'Operational Triage Priority'}</span>
                </div>
                <div class="math-formula-box">
                    Formula: P = 5*S + 5*D + 3*N + 3*T + 2*V + 2*E (Max 100)
                </div>
                <div class="math-grid" style="grid-template-columns: repeat(3, 1fr);">
                    <div class="math-stat">
                        <div class="math-stat-label">S: Life Severity (×5)</div>
                        <div class="math-stat-val">${math.factors?.S_severity ?? 'N/A'} / 5.0</div>
                    </div>
                    <div class="math-stat">
                        <div class="math-stat-label">D: Imminent Danger (×5)</div>
                        <div class="math-stat-val">${math.factors?.D_danger ?? 'N/A'} / 5.0</div>
                    </div>
                    <div class="math-stat">
                        <div class="math-stat-label">N: Affected People (×3)</div>
                        <div class="math-stat-val">${math.factors?.N_affected !== null && math.factors?.N_affected !== undefined ? math.factors.N_affected + ' / 5.0' : 'UNKNOWN (NULL)'}</div>
                    </div>
                    <div class="math-stat">
                        <div class="math-stat-label">T: Time Sensitivity (×3)</div>
                        <div class="math-stat-val">${math.factors?.T_time ?? 'N/A'} / 5.0</div>
                    </div>
                    <div class="math-stat">
                        <div class="math-stat-label">V: Vulnerability (×2)</div>
                        <div class="math-stat-val">${math.factors?.V_vulnerability ?? 'N/A'} / 5.0</div>
                    </div>
                    <div class="math-stat">
                        <div class="math-stat-label">E: Escape Difficulty (×2)</div>
                        <div class="math-stat-val">${math.factors?.E_escape ?? 'N/A'} / 5.0</div>
                    </div>
                </div>
                ${math.is_provisional ? `
                    <div class="provisional-badge" style="margin-top:0.6rem;">
                        ⚠️ <strong>[PROVISIONAL SCORE APPLIED]</strong><br>
                        ${(math.reasons || math.provisional_reasons || []).join("<br>")}
                    </div>
                ` : ''}
                <div style="font-size:0.7rem;color:var(--text-dim);margin-top:0.4rem;">
                    Notice: Academic Prototype Demonstration Estimates — Normalized for available factors.
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
                ${inc.status !== 'RESOLVED' && inc.status !== 'CLOSED' ? `
                    <button class="btn-primary" style="margin-top:0.65rem;width:100%;background:linear-gradient(135deg, #059669, #10b981);border:none;padding:0.6rem;font-weight:700;display:flex;justify-content:center;align-items:center;gap:0.4rem;" onclick="app.updateSelectedStatus(${inc.id}, 'RESOLVED')">
                        ✅ Mark Rescue Completed / Safe (Moves Down)
                    </button>
                ` : `
                    <div style="margin-top:0.6rem;padding:0.5rem;background:rgba(16,185,129,0.15);border:1px solid #10b981;border-radius:4px;color:#6ee7b7;font-size:0.75rem;text-align:center;">
                        ✅ Successful Rescue Completed — Incident moved to bottom of queue.
                    </div>
                `}
            </div>

            <!-- 5. Operational Audit Trail -->
            <div class="section-label">⏱️ Operational Audit Log</div>
            <div class="timeline-container">
                ${timelineHtml}
            </div>
        `;
    }

    async markRescued(incidentId, event) {
        if (event) event.stopPropagation();
        await this.updateSelectedStatus(incidentId, "RESOLVED");
    }

    async dispatchTeamToSelected(incidentId) {
        if (!this.authToken) {
            this.showToast("🔒 Commander Login Required: Please authenticate to dispatch rescue teams.", "error");
            document.getElementById("authModal").style.display = "flex";
            return;
        }

        const select = document.getElementById("selectDispatchTeam");
        if (!select || !select.value) return;

        const teamId = parseInt(select.value);
        try {
            const resp = await fetch(`/api/incidents/${incidentId}/dispatch`, {
                method: "POST",
                headers: this.getAuthHeaders(),
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
        if (!this.authToken) {
            this.showToast("🔒 Commander Login Required: Please authenticate to change incident operational status.", "error");
            document.getElementById("authModal").style.display = "flex";
            return;
        }

        try {
            const resp = await fetch(`/api/incidents/${incidentId}/status`, {
                method: "POST",
                headers: this.getAuthHeaders(),
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
        if (!this.authToken) {
            this.showToast("🔒 Commander Login Required: Please authenticate to modify fleet status.", "error");
            document.getElementById("authModal").style.display = "flex";
            return;
        }

        try {
            const resp = await fetch(`/api/teams/${teamId}/status`, {
                method: "POST",
                headers: this.getAuthHeaders(),
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

const BACKEND_SERVICE_URL = "https://open-renewal-agent.onrender.com";
let engineCache = null;
let currentActiveFilter = null;

const SIGNAL_METADATA = {
    "consumption_vs_commit": "Consumption vs commitment %",
    "consumption_concentration": "Consumption concentration",
    "integrations_live": "Live integration count",
    "active_users": "Active-user ratio",
    "unique_logins": "Unique logins vs seats",
    "logins": "Login activity",
    "activated_workflows": "Activated workflows (50+/qtr)",
    "workflow_breadth": "Distinct workflows in use",
    "features_used": "Core features adopted",
    "grounding_fail_rate": "Grounding-failure rate",
    "support_tickets": "Open ticket / severe count",
    "escalations": "Escalation rate",
    "outcomes_produced": "Outcomes produced",
    "cost_per_outcome": "Cost per outcome",
    "champion_present": "Engaged stakeholders",
    "exec_touch_recency": "Exec-touch recency"
};

async function recomputeEnginePipeline() {
    const payload = {
        n_accounts: 800,
        n_live: parseInt(document.getElementById('ctrl-live').value),
        winner_share: parseFloat(document.getElementById('ctrl-winner').value) / 100,
        noise_share: 0.12, short_share: 0.55, midterm_share: 0.30, smb: 0.50, mid: 0.35, seed: 42
    };

    try {
        const response = await fetch(`${https://open-renewal-intelligence.onrender.com}/api/engine-pipeline`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        engineCache = await response.json();
        
        initializeDropdowns();
        renderHomeInterface();
        renderPortfolioGrid();
        renderAUCMatrixTable();
        renderLineChart();
        buildSignalLibraryUI();
    } catch (e) {
        console.error("Critical connection failure to server engine instance: ", e);
    }
}

function routeToPage(targetId) {
    document.querySelectorAll('.app-page').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`page-${targetId}`).classList.remove('hidden');
    if (event && event.target) event.target.classList.add('active');
}

function switchSubTab(tabMode) {
    document.querySelectorAll('.subtab-content').forEach(c => c.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`subtab-${tabMode}`).classList.remove('hidden');
    document.getElementById(`btn-tab-${tabMode}`).classList.add('active');
}

function initializeDropdowns() {
    const picker = document.getElementById('account-picker');
    if (!picker) return;
    picker.innerHTML = "";
    const signalSelect = document.getElementById('sel-signal');
    signalSelect.innerHTML = "";

    engineCache.portfolio.forEach(a => {
        picker.innerHTML += `<option value="${a.account_id}">${a.account_id} (${a.segment})</option>`;
    });
    Object.keys(SIGNAL_METADATA).forEach(k => {
        signalSelect.innerHTML += `<option value="${k}">${SIGNAL_METADATA[k]}</option>`;
    });

    if(engineCache.portfolio.length > 0) {
        loadAccountPlanView(engineCache.portfolio[0].account_id);
    }
}

function renderHomeInterface() {
    const data = engineCache.portfolio;
    document.getElementById('m-scored').innerText = data.length;
    document.getElementById('m-risk').innerText = data.filter(a => a.risk_band === "At risk").length;
    document.getElementById('m-soon').innerText = data.filter(a => a.risk_band === "At risk" && a.quarters_to_renewal <= 2).length;
}

function renderPortfolioGrid() {
    const tableBody = document.getElementById('portfolio-table-body');
    tableBody.innerHTML = "";
    let collection = engineCache.portfolio;

    if (currentActiveFilter) {
        collection = collection.filter(a => a.risk_band === currentActiveFilter.band && (a.quarters_to_renewal <= 2) === currentActiveFilter.soon);
    }

    collection.forEach(a => {
        let tone = a.risk_band === "At risk" ? "#C0392B" : a.risk_band === "Needs attention" ? "#C77D0A" : "#1E8E5A";
        tableBody.innerHTML += `<tr>
            <td><b>${a.account_id}</b></td>
            <td><span style="color:${tone}; font-weight:bold;">● ${a.risk_band}</span></td>
            <td>${a.segment}</td>
            <td>${a.quarters_to_renewal} Quarters</td>
            <td>$${a.contract_value.toLocaleString()}</td>
            <td>${a.priority_score}</td>
            <td><button onclick="navigateToAccountPlaybook('${a.account_id}')" style="cursor:pointer; border:1px solid #0E7C86; border-radius:4px; padding:2px 8px; color:#0E7C86; background:#fff;">View Plan</button></td>
        </tr>`;
    });

    renderPlotlyQuadrantChart(collection);
}

function renderPlotlyQuadrantChart(dataSet) {
    const trace = {
        x: dataSet.map(a => a.quarters_to_renewal + (Math.random() * 0.08 - 0.04)),
        y: dataSet.map(a => a.risk_band === "On track" ? 2.5 : a.risk_band === "Needs attention" ? 1.5 : 0.5),
        mode: 'markers',
        marker: { size: dataSet.map(a => Math.max(10, Math.min(32, a.contract_value / 80000))), color: dataSet.map(a => a.risk_band === "At risk" ? "#C0392B" : a.risk_band === "Needs attention" ? "#C77D0A" : "#1E8E5A"), opacity: 0.8 },
        text: dataSet.map(a => `${a.account_id}<br>Value: $${a.contract_value.toLocaleString()}`),
        type: 'scatter'
    };

    Plotly.newPlot('plotly-quadrant-chart', [trace], {
        title: 'Risk vs Time Matrix (Click marker to open account)',
        xaxis: { title: 'Quarters to Renewal (Sooner ←)' },
        yaxis: { tickvals: [0.5, 1.5, 2.5], ticktext: ['At Risk', 'Needs Attention', 'On Track'], range: [0, 3] },
        hovermode: 'closest'
    });

    document.getElementById('plotly-quadrant-chart').on('plotly_click', function(data){
        const index = data.points[0].pointIndex;
        navigateToAccountPlaybook(dataSet[index].account_id);
    });
}

function renderLineChart() {
    const horizon = document.getElementById('sel-horizon').value;
    const signal = document.getElementById('sel-signal').value;
    const qCount = parseInt(horizon);
    if (!signal) return;
    
    let xVals = [], yVals = [];
    for(let i=1; i<=qCount; i++) {
        xVals.push(`Q${i}`);
        yVals.push(engineCache.benchmarks[horizon][i][signal][1]);
    }

    const benchmarkTrace = { x: xVals, y: yVals, type: 'scatter', mode: 'lines+markers', name: 'Winning Benchmark', line: { color: '#1E8E5A', width: 3 } };
    Plotly.newPlot('plotly-line-chart', [benchmarkTrace], { title: `${SIGNAL_METADATA[signal]} Median Optimization Path Trajectory`, xaxis: { title: 'Timeline Interval Quarter' }, yaxis: { title: 'Calculated Scalar Value' } });
}

function renderAUCMatrixTable() {
    const body = document.getElementById('auc-rows-body');
    body.innerHTML = "";
    const horizon = document.getElementById('sel-horizon').value;
    
    const head = document.getElementById('auc-headers');
    head.innerHTML = "<th>Trajectory Signal</th>";
    for(let i=1; i<=parseInt(horizon); i++) { head.innerHTML += `<th>Quarter ${i}</th>`; }

    Object.keys(SIGNAL_METADATA).forEach(sig => {
        if(engineCache.auc_matrix[horizon]["1"][sig] !== undefined) {
            let row = `<tr><td><b>${SIGNAL_METADATA[sig]}</b></td>`;
            for(let i=1; i<=parseInt(horizon); i++) {
                row += `<td>${engineCache.auc_matrix[horizon][i][sig]}</td>`;
            }
            row += "</tr>";
            body.innerHTML += row;
        }
    });
}

function loadAccountPlanView(id) {
    const acct = engineCache.portfolio.find(a => a.account_id === id);
    const container = document.getElementById('account-meta-plate');
    container.innerHTML = `<div class="ac-note"><h3>Dossier Profile: ${acct.account_id}</h3><p>Segment Class: ${acct.segment} | Progressed to Quarter ${acct.current_quarter} of operational cycle lifecycle.</p></div>`;

    const body = document.getElementById('plan-table-body');
    body.innerHTML = "";

    if(acct.drivers.length === 0) {
        body.innerHTML = `<tr><td colspan="5" style="color:#1E8E5A; text-align:center; font-weight:bold;">✔ Account is tracking cleanly within optimal target compliance tolerances.</td></tr>`;
        return;
    }

    acct.drivers.forEach(d => {
        body.innerHTML += `<tr>
            <td><b style="color:${d.status==="At risk"?"#C0392B":"#C77D0A"}">${d.status}</b></td>
            <td>${d.metric}</td>
            <td><mark style="padding:2px 6px; border-radius:4px;">${d.owner}</mark></td>
            <td>${d.metric} Optimizer Step</td>
            <td>${d.detail}</td>
        </tr>`;
    });
}

function buildSignalLibraryUI() {
    const target = document.getElementById('library-listing');
    target.innerHTML = "";
    Object.keys(SIGNAL_METADATA).forEach(k => {
        target.innerHTML += `<p style='border-bottom:1px solid #DDE4EA; padding:8px 0;'><b>● ${SIGNAL_METADATA[k]}</b>: Learned prediction metric evaluating tracking system arrays.</p>`;
    });
}

function navigateToAccountPlaybook(id) {
    document.getElementById('account-picker').value = id;
    loadAccountPlanView(id);
    routeToPage('AccountPlan');
}

function applyCellFilter(band, soon) { currentActiveFilter = { band, soon }; renderPortfolioGrid(); }
function clearCellFilter() { currentActiveFilter = null; renderPortfolioGrid(); }

window.onload = recomputeEnginePipeline;

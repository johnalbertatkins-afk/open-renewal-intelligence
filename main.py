import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Atkins Consulting - Renewal Intelligence API Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TERM_CHOICES = [4, 8, 12]
SEGMENTS = ["SMB", "Mid", "Enterprise"]
SEGMENT_COMMIT = {"SMB": 50000, "Mid": 200000, "Enterprise": 800000}
WINNER_OUTCOMES = {"expansion", "full_renewal"}
LOSER_OUTCOMES  = {"under_90", "churn"}

YELLOW_SEV = 0.25    
RED_SEV    = 1.00    
TARGET_AT_RISK    = 0.08   
TARGET_ATTENTION  = 0.12   
BAND_GAP_FLOOR    = 8.0

QUARTER_SIGNALS = [
    "consumption_vs_commit", "consumption_concentration", "integrations_live",
    "active_users", "unique_logins", "logins", "activated_workflows",
    "workflow_breadth", "features_used", "grounding_fail_rate",
    "support_tickets", "escalations", "outcomes_produced", "cost_per_outcome",
    "champion_present", "exec_touch_recency"
]
ACCOUNT_SIGNALS = ["time_to_deploy", "time_to_value", "eval_score", "exec_sponsor_nps"]

class PipelineSettings(BaseModel):
    n_accounts: int = 800
    n_live: int = 100
    winner_share: float = 0.70
    noise_share: float = 0.12
    short_share: float = 0.55
    midterm_share: float = 0.30
    smb: float = 0.50
    mid: float = 0.35
    seed: int = 42

def make_trajectory(shape, term, rng):
    rows = []
    for q in range(1, term + 1):
        frac = q / term
        if shape == "winner":
            cons = 0.55 + 0.60 * frac + rng.normal(0, 0.05)
            concentration = np.clip(0.38 + rng.normal(0, 0.06), 0, 1)
            features = min(8, int(round(3 + 4 * frac + rng.normal(0, 0.6))))
            champion = 1 if rng.random() > 0.05 else 0
            exec_recency = max(1, rng.normal(20, 8))
            cost_per_outcome = np.clip(1.00 - 0.15 * frac + rng.normal(0, 0.05), 0.4, 2.0)
            tickets = max(0, int(rng.normal(2, 1)))
            escal = 1 if rng.random() < 0.05 else 0
            integrations = max(1, int(round(3 + 4 * frac + rng.normal(0, 1.0))))
            activated = max(0, int(round(1 + 3 * frac + rng.normal(0, 0.7))))
            breadth = max(1, int(round(2 + 4 * frac + rng.normal(0, 0.8))))
            grounding = float(np.clip(0.05 + rng.normal(0, 0.02), 0, 1))
        else:
            start = 0.50
            peak = 0.85
            cons = start + (peak - start) * (frac / 0.45) if frac <= 0.45 else peak + (0.65 - peak) * ((frac - 0.45) / 0.55)
            cons += rng.normal(0, 0.04)
            concentration = np.clip(0.58 + 0.15 * frac + rng.normal(0, 0.07), 0, 1)
            features = min(8, int(round(2 + 2 * frac + rng.normal(0, 0.6))))
            champion = 0 if (frac > 0.5 and rng.random() < 0.5) else (1 if rng.random() > 0.2 else 0)
            exec_recency = max(1, rng.normal(55, 18) + 30 * frac)
            cost_per_outcome = np.clip(1.05 + 0.35 * frac + rng.normal(0, 0.07), 0.4, 3.0)
            tickets = max(0, int(rng.normal(5, 2)))
            escal = 1 if rng.random() < 0.30 else 0
            integrations = max(0, int(round(1 + 1.5 * frac + rng.normal(0, 0.8))))
            activated = max(0, int(round(0.5 + 1.0 * frac + rng.normal(0, 0.5))))
            breadth = max(1, int(round(2 + 1.0 * frac - 1.2 * max(0, frac - 0.5) + rng.normal(0, 0.6))))
            grounding = float(np.clip(0.12 + 0.15 * frac + rng.normal(0, 0.03), 0, 1))

        rows.append({
            "quarter_within_term": q, "consumption_vs_commit": round(max(0.05, cons), 4),
            "consumption_concentration": round(concentration, 4), "integrations_live": integrations,
            "active_users": active_users, "unique_logins": unique_logins, "logins": logins,
            "activated_workflows": activated, "workflow_breadth": breadth, "features_used": features,
            "grounding_fail_rate": round(grounding, 4), "support_tickets": tickets, "escalations": escal,
            "outcomes_produced": round(outcomes, 4), "cost_per_outcome": round(cost_per_outcome, 4),
            "champion_present": champion, "exec_touch_recency": round(exec_recency, 1)
        })
    return rows

def generate_base_dataset(settings, is_live=False, seed_offset=0):
    rng = np.random.default_rng(settings.seed + seed_offset)
    acct_rows, aq_rows = [], []
    count = settings.n_live if is_live else settings.n_accounts
    
    tp_tot = settings.short_share + settings.midterm_share + max(0.0, 1.0 - settings.short_share - settings.midterm_share)
    tp = [settings.short_share/tp_tot, settings.midterm_share/tp_tot, max(0.0, 1.0 - settings.short_share - settings.midterm_share)/tp_tot]
    
    seg_tot = settings.smb + settings.mid + max(0.0, 1.0 - settings.smb - settings.mid)
    sp = [settings.smb/seg_tot, settings.mid/seg_tot, max(0.0, 1.0 - settings.smb - settings.mid)/seg_tot]

    for i in range(count):
        aid = f"LACC{i:04d}" if is_live else f"HACC{i:04d}"
        segment = rng.choice(SEGMENTS, p=sp)
        term = int(rng.choice(TERM_CHOICES, p=tp))
        committed = int(SEGMENT_COMMIT[segment] * np.exp(rng.normal(0, 0.25)))
        shape = "winner" if rng.random() < settings.winner_share else "faller"
        
        traj = make_trajectory(shape, term, rng)
        
        t_deploy = float(max(3, rng.normal(35, 12) if shape=="winner" else rng.normal(70, 25)))
        t_value  = float(t_deploy + (rng.normal(20, 8) if shape=="winner" else rng.normal(55, 20)))
        eval_score = float(np.clip(rng.normal(0.90, 0.07) if shape=="winner" else rng.normal(0.60, 0.12), 0, 1.3))
        exec_sponsor_nps = float(np.clip(rng.normal(45, 15) if shape=="winner" else rng.normal(10, 25), -100, 100))
        
        ratio = traj[-1]["consumption_vs_commit"]
        outcome = "expansion" if ratio >= 1.15 else "full_renewal" if ratio >= 1.00 else "90_99" if ratio >= 0.90 else "under_90" if ratio >= 0.75 else "churn"

        acct_rows.append({
            "account_id": aid, "segment": segment, "term_quarters": term, "committed_credits_quarter": committed,
            "time_to_deploy": round(t_deploy, 1), "time_to_value": round(t_value, 1),
            "eval_score": round(eval_score, 4), "exec_sponsor_nps": round(exec_sponsor_nps, 1),
            "outcome": outcome, "shape_internal": shape
        })
        for r in traj:
            aq_rows.append({"account_id": aid, "term_quarters": term, **r})
            
    return pd.DataFrame(acct_rows), pd.DataFrame(aq_rows)

def calculate_auc(x, y):
    n1, n0 = int(y.sum()), int((y == 0).sum())
    if n1 == 0 or n0 == 0: return 0.5
    ranks = pd.Series(x).rank().to_numpy()
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))

@app.post("/api/engine-pipeline")
def get_pipeline_data(settings: PipelineSettings):
    h_acct, h_aq = generate_base_dataset(settings, is_live=False, seed_offset=0)
    l_acct, l_aq = generate_base_dataset(settings, is_live=True, seed_offset=999)
    
    h_aq["is_winner"] = h_aq["account_id"].map(lambda a: h_acct.set_index("account_id")["outcome"][a] in WINNER_OUTCOMES)
    win_hist = h_aq[h_aq["is_winner"]]
    
    benchmarks = {}
    for term in TERM_CHOICES:
        benchmarks[str(term)] = {}
        for q in range(1, term + 1):
            sub = win_hist[(win_hist["term_quarters"] == term) & (win_hist["quarter_within_term"] == q)]
            benchmarks[str(term)][str(q)] = {}
            for m in QUARTER_SIGNALS:
                if sub.empty:
                    benchmarks[str(term)][str(q)][m] = [0.0, 0.0, 0.0]
                else:
                    benchmarks[str(term)][str(q)][m] = [float(sub[m].quantile(0.25)), float(sub[m].median()), float(sub[m].quantile(0.75))]

    win_accts = h_acct[h_acct["outcome"].isin(WINNER_OUTCOMES)]
    aband = {}
    for m in ACCOUNT_SIGNALS:
        aband[m] = [float(win_accts[m].quantile(0.25)), float(win_accts[m].median()), float(win_accts[m].quantile(0.75))]

    auc_matrix = {}
    for term in TERM_CHOICES:
        auc_matrix[str(term)] = {}
        df = h_aq[h_aq["term_quarters"] == term].copy()
        df["label"] = df["account_id"].map(lambda a: 1 if h_acct.set_index("account_id")["outcome"][a] in WINNER_OUTCOMES else (0 if h_acct.set_index("account_id")["outcome"][a] in LOSER_OUTCOMES else -1))
        df = df[df["label"] >= 0]
        for q in sorted(df["quarter_within_term"].unique()):
            sub = df[df["quarter_within_term"] == q]
            auc_matrix[str(term)][str(q)] = {}
            for m in QUARTER_SIGNALS:
                auc_matrix[str(term)][str(q)][m] = round(calculate_auc(sub[m], sub["label"]), 2)

    rng = np.random.default_rng(settings.seed + 7)
    portfolio_rows = []
    
    for _, a in l_acct.iterrows():
        term = a["term_quarters"]
        current_q = max(1, int(round(term * rng.uniform(0.40, 0.80))))
        q_to_renewal = term - current_q
        cur = l_aq[(l_aq["account_id"] == a["account_id"]) & (l_aq["quarter_within_term"] == current_q)].iloc[0]
        
        drivers = []
        n_tracked = 0
        
        for m in QUARTER_SIGNALS + ACCOUNT_SIGNALS:
            if m in QUARTER_SIGNALS:
                q25, med, q75 = benchmarks[str(term)][str(current_q)][m]
                raw = cur[m]
            else:
                q25, med, q75 = aband[m]
                raw = a[m]
                
            n_tracked += 1
            val = float(raw)
            iqr = max(q75 - q25, 1e-6)
            sev = round(min(max(0.0, (q25 - val) / iqr), 3.0), 2)
            
            if sev > YELLOW_SEV:
                drivers.append({
                    "metric": m, "severity": sev, "status": "At risk" if sev >= RED_SEV else "Needs attention",
                    "owner": "FDE" if "deploy" in m or "fail" in m else "CSM",
                    "detail": f"{val:.2f} vs winning benchmark {med:.2f}"
                })
                
        drivers = sorted(drivers, key=lambda d: -d["severity"])
        total_gap = round(sum(d["severity"] for d in drivers), 2)
        contract_value = int(a["committed_credits_quarter"] * term)
        priority = round(total_gap * (np.log10(contract_value) / 5.0) * (1.0 + (1.0 - q_to_renewal / term)), 2)
        
        portfolio_rows.append({
            "account_id": a["account_id"], "segment": a["segment"], "term_label": f"{term*3}mo",
            "quarters_to_renewal": q_to_renewal, "contract_value": contract_value, "current_quarter": current_q,
            "off_target_count": len(drivers), "top_drivers": ", ".join(d["metric"] for d in drivers[:2]) or "None",
            "total_gap": total_gap, "priority_score": priority, "true_outcome_hidden": a["outcome"],
            "drivers": drivers, "n_tracked": n_tracked
        })

    portfolio_rows = sorted(portfolio_rows, key=lambda w: -w["total_gap"])
    n = len(portfolio_rows)
    n_red = int(round(n * TARGET_AT_RISK))
    n_amber = int(round(n * TARGET_ATTENTION))
    
    for idx, row in enumerate(portfolio_rows):
        if row["total_gap"] < BAND_GAP_FLOOR: row["risk_band"] = "On track"
        elif idx < n_red: row["risk_band"] = "At risk"
        elif idx < (n_red + n_amber): row["risk_band"] = "Needs attention"
        else: row["risk_band"] = "On track"
        
    return {
        "portfolio": portfolio_rows,
        "benchmarks": benchmarks,
        "auc_matrix": auc_matrix
    }

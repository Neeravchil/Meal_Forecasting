import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from utils.loader import load_data
from utils.forecast import gbt_forecast, LUNCH_RMSE, BREAKFAST_RMSE

ACTUAL_MONTHS   = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
FORECAST_MONTHS = ["Apr", "May", "Jun"]
ALL_MONTHS      = ACTUAL_MONTHS + FORECAST_MONTHS

MONTH_DATES = {
    "Aug": "2025-08-01", "Sep": "2025-09-01", "Oct": "2025-10-01",
    "Nov": "2025-11-01", "Dec": "2025-12-01", "Jan": "2026-01-01",
    "Feb": "2026-02-01", "Mar": "2026-03-01",
}
MONTH_NUM  = {"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12,"Jan":1,"Feb":2,"Mar":3}
MONTH_YEAR = {"Aug":2025,"Sep":2025,"Oct":2025,"Nov":2025,
              "Dec":2025,"Jan":2026,"Feb":2026,"Mar":2026}

_LAYOUT = dict(
    paper_bgcolor="white", plot_bgcolor="white",
    font=dict(family="Aptos, Nunito Sans, Segoe UI, Arial", size=12, color="#334D66"),
    margin=dict(l=44, r=44, t=20, b=40),
    showlegend=True,
    legend=dict(orientation="h", y=1.08),
)

@st.cache_data
def _defaults():
    df = load_data()
    return {
        "enrollment":     int(df["ENROLLMENT"].median()),
        "lunch_part":     round(df["LUNCH_PARTICIPATION"].median() * 100, 1),
        "bf_part":        round(df["BREAKFAST_PARTICIPATION"].median() * 100, 1),
        "absence_rate":   round(df["absence_rate"].median() * 100, 1),
        "frl":            round(df["pct_free_reduced_lunch"].median() * 100, 2),
        # kept at medians but not exposed in UI
        "weighted_abs":   round(df["weighted_absence_rate"].median() * 100, 1),
        "pct_full_abs":   round(df["pct_full_absence"].median() * 100, 1),
        "pct_half_abs":   round(df["pct_half_absence"].median() * 100, 1),
        "pct_excused":    round(df["pct_excused"].median() * 100, 1),
        "pct_mhd":        round(df["pct_mental_health_day"].median() * 100, 2),
        "pct_female":     round(df["pct_female"].median() * 100, 1),
        "pct_dc":         round(df["pct_direct_cert"].median() * 100, 2),
        "pct_rl":         round(df["pct_reduced_lunch"].median() * 100, 2),
    }

DEF = _defaults()

# ── Sidebar: display toggle only ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:0.82rem; font-weight:700; color:#E8EDF2; "
                "margin:6px 0 4px 0;'>Forecast display</p>", unsafe_allow_html=True)
    show = st.radio("Show forecast for", ["Lunch", "Breakfast", "Both"],
                    index=2, key="show_forecast_p3")
    st.markdown("<hr style='border:none; border-top:1px solid rgba(200,151,58,0.3); "
                "margin:10px 0;'/>", unsafe_allow_html=True)
    if st.button("↺  Reset to district defaults", use_container_width=True,
                 key="p3_reset"):
        for k in ["p3_name","p3_enroll","p3_abs","p3_lp","p3_lt",
                  "p3_bp","p3_bt","p3_frl"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# HERO
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style='background:linear-gradient(135deg,#003057 0%,#00497a 100%);
            border-radius:12px; padding:32px 40px; margin-bottom:28px;
            border-left:6px solid #C8973A;'>
    <div style='font-size:0.72rem; font-weight:700; letter-spacing:0.14em;
                color:#C8973A; text-transform:uppercase; margin-bottom:10px;'>
        Chicago Public Schools · Custom School Simulator
    </div>
    <div style='font-size:1.9rem; font-weight:800; color:#FFFFFF; line-height:1.25;'>
        Forecast Any School — Real or Hypothetical
    </div>
    <div style='font-size:0.92rem; color:#B8CFDF; margin-top:12px;
                max-width:740px; line-height:1.6;'>
        Enter a school's key characteristics below. The model uses only the inputs
        that matter most — pre-filled with CPS district averages so you can start
        forecasting immediately.
    </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# INPUT SECTION
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-header'>Configure School Profile</div>",
            unsafe_allow_html=True)
st.markdown("<div class='section-sub'>Adjust the inputs below — all other variables "
            "are held at CPS district averages.</div>", unsafe_allow_html=True)

# ── Shared school-level inputs ────────────────────────────────────────────────
si1, si2, si3 = st.columns([2, 1, 1])
with si1:
    school_name = st.text_input("School name (for labelling)", value="Hypothetical School",
                                key="p3_name")
with si2:
    enrollment = st.number_input("School Enrollment",
                                 min_value=10, max_value=5000,
                                 value=DEF["enrollment"], step=10, key="p3_enroll",
                                 help="Total number of students enrolled.")
with si3:
    absence_rate_pct = st.slider(
        "Student Absence Rate (%)", 0.0, 40.0,
        value=DEF["absence_rate"], step=0.1, key="p3_abs",
        help="Percentage of school days where students are absent. "
             "District median ≈ 9.8%"
    )

st.markdown("<br>", unsafe_allow_html=True)

# ── Model-specific input cards ────────────────────────────────────────────────
def _imp_badge(pct: str, color: str) -> str:
    """Render a small importance pill."""
    return (f"<span style='background:{color}18; color:{color}; font-size:0.68rem; "
            f"font-weight:700; border-radius:20px; padding:2px 8px; "
            f"margin-left:6px; vertical-align:middle;'>{pct} impact</span>")

col_l, col_r = st.columns(2)

with col_l:
    st.markdown(f"""
    <div style='background:#F0F5FA; border:1px solid #D1DBE8; border-top:4px solid #003057;
                border-radius:10px; padding:20px 20px 8px 20px; margin-bottom:4px;'>
        <div style='font-size:0.95rem; font-weight:800; color:#003057; margin-bottom:2px;'>
            🍽&nbsp; Lunch Model
        </div>
        <div style='font-size:0.76rem; color:#4A6580; margin-bottom:16px;'>
            Key drivers for lunch participation forecasting
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f"**Prior Month Lunch Participation** {_imp_badge('69.9%', '#003057')}",
        unsafe_allow_html=True,
    )
    lunch_part_pct = st.slider(
        "lunch_part_pct", 0.0, 120.0,
        value=DEF["lunch_part"], step=0.5, key="p3_lp",
        label_visibility="collapsed",
        help="The school's lunch participation rate last month — the strongest "
             "predictor of future rates. District median ≈ 66.7%"
    )
    st.markdown(f"<div style='font-size:0.75rem; color:#64748B; "
                f"margin:-8px 0 14px 0;'>Current value: "
                f"<b>{lunch_part_pct:.1f}%</b></div>", unsafe_allow_html=True)

    st.markdown(
        f"**Recent Participation Trend** {_imp_badge('13.8%', '#003057')}",
        unsafe_allow_html=True,
    )
    lunch_trend_pct = st.slider(
        "lunch_trend_pct", -30.0, 30.0,
        value=0.0, step=0.5, key="p3_lt",
        label_visibility="collapsed",
        help="Month-over-month change in participation. +5% means the school's "
             "lunch participation grew by 5% last month. Negative = declining."
    )
    trend_label = ("▲ Growing" if lunch_trend_pct > 0
                   else "▼ Declining" if lunch_trend_pct < 0 else "→ Flat")
    trend_clr   = "#22C55E" if lunch_trend_pct > 0 else "#EF4444" if lunch_trend_pct < 0 else "#64748B"
    st.markdown(
        f"<div style='font-size:0.75rem; color:{trend_clr}; "
        f"margin:-8px 0 14px 0;'><b>{trend_label}</b> "
        f"({lunch_trend_pct:+.1f}% vs prior month)</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

with col_r:
    st.markdown(f"""
    <div style='background:#FDF8F0; border:1px solid #E8D9B8; border-top:4px solid #C8973A;
                border-radius:10px; padding:20px 20px 8px 20px; margin-bottom:4px;'>
        <div style='font-size:0.95rem; font-weight:800; color:#C8973A; margin-bottom:2px;'>
            🥞&nbsp; Breakfast Model
        </div>
        <div style='font-size:0.76rem; color:#7A6040; margin-bottom:16px;'>
            Key drivers for breakfast participation forecasting
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(
        f"**Prior Month Breakfast Participation** {_imp_badge('12.7%', '#C8973A')}",
        unsafe_allow_html=True,
    )
    bf_part_pct = st.slider(
        "bf_part_pct", 0.0, 120.0,
        value=DEF["bf_part"], step=0.5, key="p3_bp",
        label_visibility="collapsed",
        help="The school's breakfast participation rate last month. "
             "District median ≈ 44.3%"
    )
    st.markdown(f"<div style='font-size:0.75rem; color:#64748B; "
                f"margin:-8px 0 14px 0;'>Current value: "
                f"<b>{bf_part_pct:.1f}%</b></div>", unsafe_allow_html=True)

    st.markdown(
        f"**Recent Breakfast Trend** {_imp_badge('28.2%', '#C8973A')}",
        unsafe_allow_html=True,
    )
    bf_trend_pct = st.slider(
        "bf_trend_pct", -30.0, 30.0,
        value=0.0, step=0.5, key="p3_bt",
        label_visibility="collapsed",
        help="Month-over-month change in breakfast participation. Drives the "
             "3-month rolling average that's the second strongest predictor."
    )
    bf_trend_label = ("▲ Growing" if bf_trend_pct > 0
                      else "▼ Declining" if bf_trend_pct < 0 else "→ Flat")
    bf_trend_clr   = "#22C55E" if bf_trend_pct > 0 else "#EF4444" if bf_trend_pct < 0 else "#64748B"
    st.markdown(
        f"<div style='font-size:0.75rem; color:{bf_trend_clr}; "
        f"margin:-8px 0 14px 0;'><b>{bf_trend_label}</b> "
        f"({bf_trend_pct:+.1f}% vs prior month)</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f"**Free & Reduced Lunch Eligibility** {_imp_badge('6.1%', '#C8973A')}",
        unsafe_allow_html=True,
    )
    frl_pct = st.slider(
        "frl_pct", 0.0, 35.0,
        value=DEF["frl"], step=0.01, key="p3_frl",
        label_visibility="collapsed",
        help="Percentage of students eligible for free or reduced-price meals — "
             "a proxy for household economic hardship. District median ≈ 4.2%"
    )
    st.markdown(f"<div style='font-size:0.75rem; color:#64748B; "
                f"margin:-8px 0 8px 0;'>Current value: "
                f"<b>{frl_pct:.2f}%</b></div>", unsafe_allow_html=True)

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# BUILD SYNTHETIC HISTORICAL DATA
# Months 1–7: "pre-trend" values; Month 8 (Mar): user-set "current" values.
# This gives the model correct lag-1, 3-month rolling avg, and momentum values.
# ══════════════════════════════════════════════════════════════════════════════
lunch_part  = lunch_part_pct  / 100.0
bf_part     = bf_part_pct     / 100.0
absence     = absence_rate_pct / 100.0
frl         = frl_pct          / 100.0

# Derive the "prior period" values that produce the user's trend
denom_l = 1.0 + lunch_trend_pct / 100.0
denom_b = 1.0 + bf_trend_pct    / 100.0
prev_lunch = lunch_part / denom_l if denom_l != 0 else lunch_part
prev_bf    = bf_part    / denom_b if denom_b != 0 else bf_part

# Hidden features (held at district medians)
w_abs   = DEF["weighted_abs"]  / 100.0
full_ab = DEF["pct_full_abs"]  / 100.0
half_ab = DEF["pct_half_abs"]  / 100.0
excused = DEF["pct_excused"]   / 100.0
mhd     = DEF["pct_mhd"]       / 100.0
fem     = DEF["pct_female"]    / 100.0
dc      = DEF["pct_dc"]        / 100.0
rl      = DEF["pct_rl"]        / 100.0

rows = []
for i, m_lbl in enumerate(ACTUAL_MONTHS):
    is_last = (i == len(ACTUAL_MONTHS) - 1)
    lp = lunch_part if is_last else prev_lunch
    bp = bf_part    if is_last else prev_bf
    rows.append({
        "SCHOOL_NAME":               school_name,
        "MONTH_START":               pd.Timestamp(MONTH_DATES[m_lbl], tz="UTC"),
        "MONTH":                     MONTH_NUM[m_lbl],
        "YEAR":                      MONTH_YEAR[m_lbl],
        "ENROLLMENT":                enrollment,
        "LUNCH_PARTICIPATION":       lp,
        "BREAKFAST_PARTICIPATION":   bp,
        "LUNCH_AVERAGE_PER_DAY":     lp * enrollment,
        "BREAKFAST_AVERAGE_PER_DAY": bp * enrollment,
        "absence_rate":              absence,
        "weighted_absence_rate":     w_abs,
        "pct_full_absence":          full_ab,
        "pct_half_absence":          half_ab,
        "pct_excused":               excused,
        "pct_mental_health_day":     mhd,
        "pct_female":                fem,
        "pct_male":                  1.0 - fem,
        "pct_free_reduced_lunch":    frl,
        "pct_direct_cert":           dc,
        "pct_reduced_lunch":         rl,
    })

school_data = pd.DataFrame(rows)

# ══════════════════════════════════════════════════════════════════════════════
# KPI SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
TIER_COLORS = {"Strong":"#003057","Moderate":"#4A90C4","Low":"#C8973A","Critical":"#EF4444"}

def _tier(p):
    return "Critical" if p < 40 else "Low" if p < 55 else "Moderate" if p < 65 else "Strong"

tier     = _tier(lunch_part_pct)
tier_clr = TIER_COLORS[tier]

s1, s2, s3, s4 = st.columns(4)
for col, (val, lbl, sub, clr) in zip([s1, s2, s3, s4], [
    (str(enrollment),               "Enrollment",               "Students",           "#003057"),
    (f"{lunch_part_pct:.1f}%",      "Lunch Participation",      f"Tier: {tier}",      tier_clr),
    (f"{bf_part_pct:.1f}%",         "Breakfast Participation",  "Prior month",        "#C8973A"),
    (f"{absence_rate_pct:.1f}%",    "Absence Rate",             "Student-days absent","#4A90C4"),
]):
    with col:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value' style='color:{clr};'>{val}</div>
            <div class='metric-label'>{lbl}</div>
            <div class='metric-sub'>{sub}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# RUN FORECAST
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"<div class='section-header'>Participation Forecast — {school_name}</div>",
            unsafe_allow_html=True)
st.markdown("<div class='section-sub'>Solid lines = assumed history based on your inputs "
            "· Dashed = Apr–Jun forecast · Shaded = ±RMSE band (pp)</div>",
            unsafe_allow_html=True)

with st.spinner(f"Running forecast for {school_name}…"):
    lunch_fc_vals, bf_fc_vals = gbt_forecast(school_data, n_ahead=3)

lunch_fc_pct = [v * 100 for v in lunch_fc_vals]
bf_fc_pct    = [v * 100 for v in bf_fc_vals]

lunch_upper = [v + LUNCH_RMSE     * 100 for v in lunch_fc_pct]
lunch_lower = [v - LUNCH_RMSE     * 100 for v in lunch_fc_pct]
bf_upper    = [v + BREAKFAST_RMSE * 100 for v in bf_fc_pct]
bf_lower    = [v - BREAKFAST_RMSE * 100 for v in bf_fc_pct]

# Build actual lines (show the trend across history)
hist_lunch = [prev_lunch * 100] * (len(ACTUAL_MONTHS) - 1) + [lunch_part_pct]
hist_bf    = [prev_bf    * 100] * (len(ACTUAL_MONTHS) - 1) + [bf_part_pct]

FC_X = [ACTUAL_MONTHS[-1]] + FORECAST_MONTHS

fig = go.Figure()

if show in ("Lunch", "Both"):
    fig.add_trace(go.Scatter(
        name="Lunch (History)", x=ACTUAL_MONTHS, y=hist_lunch,
        mode="lines+markers",
        line=dict(color="#003057", width=2.5),
        marker=dict(size=6, color="#003057"),
    ))
    fig.add_trace(go.Scatter(
        name="Lunch (Forecast)", x=FC_X, y=[lunch_part_pct] + lunch_fc_pct,
        mode="lines+markers",
        line=dict(color="#003057", width=2, dash="dash"),
        marker=dict(size=7, color="#003057", symbol="circle-open"),
    ))
    fig.add_trace(go.Scatter(
        x=FC_X, y=[lunch_part_pct] + lunch_upper,
        mode="lines", line=dict(width=0), showlegend=False, name="_lu",
    ))
    fig.add_trace(go.Scatter(
        x=FC_X, y=[lunch_part_pct] + lunch_lower,
        mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(0,48,87,0.10)",
        showlegend=False, name="_ll",
    ))

if show in ("Breakfast", "Both"):
    fig.add_trace(go.Scatter(
        name="Breakfast (History)", x=ACTUAL_MONTHS, y=hist_bf,
        mode="lines+markers",
        line=dict(color="#C8973A", width=2.5),
        marker=dict(size=6, color="#C8973A"),
    ))
    fig.add_trace(go.Scatter(
        name="Breakfast (Forecast)", x=FC_X, y=[bf_part_pct] + bf_fc_pct,
        mode="lines+markers",
        line=dict(color="#C8973A", width=2, dash="dash"),
        marker=dict(size=7, color="#C8973A", symbol="circle-open"),
    ))
    fig.add_trace(go.Scatter(
        x=FC_X, y=[bf_part_pct] + bf_upper,
        mode="lines", line=dict(width=0), showlegend=False, name="_bu",
    ))
    fig.add_trace(go.Scatter(
        x=FC_X, y=[bf_part_pct] + bf_lower,
        mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(200,151,58,0.12)",
        showlegend=False, name="_bl",
    ))

fig.add_shape(
    type="line", x0=FORECAST_MONTHS[0], x1=FORECAST_MONTHS[0],
    y0=0, y1=1, xref="x", yref="paper",
    line=dict(color="#64748B", dash="dot", width=1.5),
)
fig.add_annotation(
    x=FORECAST_MONTHS[0], y=0.96, xref="x", yref="paper",
    text="  Forecast →", showarrow=False,
    font=dict(color="#64748B", size=11), xanchor="left",
)
fig.update_layout(
    **_LAYOUT,
    xaxis=dict(title="Month", categoryorder="array", categoryarray=ALL_MONTHS,
               showgrid=True, gridcolor="#F1F5F9"),
    yaxis=dict(title="Participation Rate (%)", range=[0, 105],
               showgrid=True, gridcolor="#F1F5F9"),
    height=460,
)
st.plotly_chart(fig, use_container_width=True)

st.markdown("""
<div style='background:#EBF3FA; border:1px solid #4A90C4; border-radius:6px;
            padding:12px 16px; font-size:0.82rem; color:#003057; margin-bottom:16px;'>
    <b>Model accuracy (test set, Mar 2026 hold-out):</b>&nbsp;
    Lunch MAE = <b>0.74 pp</b> &nbsp;·&nbsp; Lunch RMSE = <b>2.92 pp</b>
    &nbsp;&nbsp;|&nbsp;&nbsp;
    Breakfast MAE = <b>2.00 pp</b> &nbsp;·&nbsp; Breakfast RMSE = <b>2.99 pp</b>
</div>
""", unsafe_allow_html=True)

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MONTHLY DETAIL TABLE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-header'>Monthly Detail</div>", unsafe_allow_html=True)
st.markdown("<div class='section-sub'>Assumed history (Aug–Mar) + "
            "Apr–Jun forecast</div>", unsafe_allow_html=True)

table_rows = [
    {"Month": m, "Lunch %": f"{lp:.1f}%", "Breakfast %": f"{bp:.1f}%", "Source": "Assumed"}
    for m, lp, bp in zip(ACTUAL_MONTHS, hist_lunch, hist_bf)
]
for lbl, lp, bp in zip(["Apr (Forecast)","May (Forecast)","Jun (Forecast)"],
                        lunch_fc_pct, bf_fc_pct):
    table_rows.append({"Month": lbl, "Lunch %": f"{lp:.1f}%",
                        "Breakfast %": f"{bp:.1f}%", "Source": "Forecast"})
st.dataframe(pd.DataFrame(table_rows), hide_index=True)

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MEALS TO BE PREPARED
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-header'>Meals to Be Prepared</div>",
            unsafe_allow_html=True)
st.markdown(
    "<div class='section-sub'>"
    "Daily meal count = Forecasted Participation Rate × Enrollment."
    "</div>",
    unsafe_allow_html=True,
)

fc_lunch_meals = [r / 100 * enrollment for r in lunch_fc_pct]
fc_bf_meals    = [r / 100 * enrollment for r in bf_fc_pct]

kc1, kc2, kc3 = st.columns(3)
for col, month, lm, bm in zip([kc1,kc2,kc3], ["April","May","June"],
                               fc_lunch_meals, fc_bf_meals):
    with col:
        if show == "Lunch":
            st.markdown(f"""
            <div class='metric-card' style='border-top:3px solid #4A90C4; text-align:left;'>
                <div style='font-size:0.70rem;font-weight:700;letter-spacing:0.12em;
                            color:#4A90C4;text-transform:uppercase;margin-bottom:8px;'>
                    {month} &nbsp;·&nbsp; Forecast</div>
                <div style='font-size:1.75rem;font-weight:800;color:#003057;
                            line-height:1.1;margin-bottom:4px;'>{lm:,.0f}</div>
                <div class='metric-label' style='text-transform:none;letter-spacing:0;
                            font-size:0.75rem;'>lunch meals / day</div>
            </div>""", unsafe_allow_html=True)
        elif show == "Breakfast":
            st.markdown(f"""
            <div class='metric-card' style='border-top:3px solid #4A90C4; text-align:left;'>
                <div style='font-size:0.70rem;font-weight:700;letter-spacing:0.12em;
                            color:#4A90C4;text-transform:uppercase;margin-bottom:8px;'>
                    {month} &nbsp;·&nbsp; Forecast</div>
                <div style='font-size:1.75rem;font-weight:800;color:#C8973A;
                            line-height:1.1;margin-bottom:4px;'>{bm:,.0f}</div>
                <div class='metric-label' style='text-transform:none;letter-spacing:0;
                            font-size:0.75rem;'>breakfast meals / day</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class='metric-card' style='border-top:3px solid #4A90C4; text-align:left;'>
                <div style='font-size:0.70rem;font-weight:700;letter-spacing:0.12em;
                            color:#4A90C4;text-transform:uppercase;margin-bottom:8px;'>
                    {month} &nbsp;·&nbsp; Forecast</div>
                <div style='font-size:1.75rem;font-weight:800;color:#003057;
                            line-height:1.1;margin-bottom:4px;'>{lm+bm:,.0f}</div>
                <div class='metric-label' style='text-transform:none;letter-spacing:0;
                            font-size:0.75rem;margin-bottom:12px;'>total meals / day</div>
                <div style='display:flex;gap:20px;padding-top:10px;
                            border-top:1px solid #EEF2F7;'>
                    <div>
                        <div style='font-size:1.05rem;font-weight:700;color:#003057;'>{lm:,.0f}</div>
                        <div class='metric-sub'>Lunch</div>
                    </div>
                    <div style='color:#D1DBE8;align-self:center;font-size:1.2rem;'>|</div>
                    <div>
                        <div style='font-size:1.05rem;font-weight:700;color:#C8973A;'>{bm:,.0f}</div>
                        <div class='metric-sub'>Breakfast</div>
                    </div>
                </div>
            </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Stacked bar chart ─────────────────────────────────────────────────────────
act_lunch_meals = [lp / 100 * enrollment for lp in hist_lunch]
act_bf_meals    = [bp / 100 * enrollment for bp in hist_bf]

fig2 = go.Figure()
if show in ("Breakfast", "Both"):
    fig2.add_trace(go.Bar(name="Breakfast (History)", x=ACTUAL_MONTHS, y=act_bf_meals,
                          marker_color="rgba(200,151,58,0.80)", marker_line=dict(width=0)))
if show in ("Lunch", "Both"):
    fig2.add_trace(go.Bar(name="Lunch (History)", x=ACTUAL_MONTHS, y=act_lunch_meals,
                          marker_color="rgba(0,48,87,0.85)", marker_line=dict(width=0)))
if show in ("Breakfast", "Both"):
    fig2.add_trace(go.Bar(name="Breakfast (Forecast)", x=FORECAST_MONTHS, y=fc_bf_meals,
                          marker_color="rgba(200,151,58,0.38)",
                          marker_line=dict(color="#C8973A", width=1.5),
                          marker_pattern_shape="/", marker_pattern_fgcolor="#C8973A"))
if show in ("Lunch", "Both"):
    fig2.add_trace(go.Bar(name="Lunch (Forecast)", x=FORECAST_MONTHS, y=fc_lunch_meals,
                          marker_color="rgba(0,48,87,0.28)",
                          marker_line=dict(color="#003057", width=1.5),
                          marker_pattern_shape="/", marker_pattern_fgcolor="#003057"))

fig2.add_shape(type="line", x0=FORECAST_MONTHS[0], x1=FORECAST_MONTHS[0],
               y0=0, y1=1, xref="x", yref="paper",
               line=dict(color="#64748B", dash="dot", width=1.5))
fig2.add_annotation(x=FORECAST_MONTHS[0], y=0.96, xref="x", yref="paper",
                    text="  Forecast →", showarrow=False,
                    font=dict(color="#64748B", size=11), xanchor="left")
_ytitle2 = {"Lunch":"Avg Daily Lunch Meals","Breakfast":"Avg Daily Breakfast Meals",
            "Both":"Avg Daily Meals"}.get(show,"Avg Daily Meals")
fig2.update_layout(**_LAYOUT, barmode="stack", height=400, bargap=0.25,
                   xaxis=dict(title="Month", categoryorder="array",
                              categoryarray=ALL_MONTHS, showgrid=False),
                   yaxis=dict(title=_ytitle2, showgrid=True,
                              gridcolor="#F1F5F9", tickformat=","))
st.plotly_chart(fig2, use_container_width=True)

# ── Meals table ────────────────────────────────────────────────────────────────
meals_rows = []
for m_lbl, lm, bm in zip(ACTUAL_MONTHS, act_lunch_meals, act_bf_meals):
    r = {"Month": m_lbl, "Enrollment": f"{enrollment:,}", "Source": "Assumed"}
    if show in ("Lunch",     "Both"): r["Lunch Meals / Day"]     = f"{lm:,.0f}"
    if show in ("Breakfast", "Both"): r["Breakfast Meals / Day"] = f"{bm:,.0f}"
    if show == "Both":                r["Total Meals / Day"]      = f"{lm+bm:,.0f}"
    meals_rows.append(r)
for lbl, lm, bm in zip(["Apr (Forecast)","May (Forecast)","Jun (Forecast)"],
                         fc_lunch_meals, fc_bf_meals):
    r = {"Month": lbl, "Enrollment": f"{enrollment:,}", "Source": "Forecast"}
    if show in ("Lunch",     "Both"): r["Lunch Meals / Day"]     = f"{lm:,.0f}"
    if show in ("Breakfast", "Both"): r["Breakfast Meals / Day"] = f"{bm:,.0f}"
    if show == "Both":                r["Total Meals / Day"]      = f"{lm+bm:,.0f}"
    meals_rows.append(r)
st.dataframe(pd.DataFrame(meals_rows), hide_index=True)

st.markdown("""
<div class='info-box' style='margin-top:10px;'>
    <b>How this works:</b>
    Your inputs define the school's profile. The model uses the same GBT algorithm
    as the School Participation Report. All inputs not shown here are held at
    CPS district averages. Add a 3–5 % buffer before placing food orders.
</div>
""", unsafe_allow_html=True)

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from utils.loader import load_data, school_averages
from utils.forecast import aggregate_gbt_forecast, LUNCH_RMSE, BREAKFAST_RMSE

# ── Hard-coded district monthly averages ──────────────────────────────────────
MONTHS        = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
FORECAST_MONTHS = ["Apr", "May", "Jun"]
ALL_MONTHS    = MONTHS + FORECAST_MONTHS
LUNCH_PCT     = [62.4, 64.6, 63.9, 63.6, 61.3, 62.5, 62.8, 62.1]
BREAKFAST_PCT = [40.6, 43.9, 43.4, 43.5, 40.4, 39.9, 41.4, 40.8]
ABSENCE_PCT   = [ 7.9, 10.4, 12.2, 12.9, 15.4, 15.2, 13.3, 15.1]

TIER_COLORS = {
    "Strong":   "#003057",
    "Moderate": "#4A90C4",
    "Low":      "#C8973A",
    "Critical": "#EF4444",
}

_LAYOUT = dict(
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=dict(family="Aptos, Nunito Sans, Segoe UI, Arial", size=12, color="#334D66"),
    margin=dict(l=44, r=44, t=20, b=40),
    showlegend=True,
    legend=dict(orientation="h", y=1.08),
)

# ── Load data ────────────────────────────────────────────────────────────────
df = load_data()
school_avg = school_averages(df)

# ── Sidebar filters (scatter only) ───────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:0.82rem; font-weight:700; color:#E8EDF2; "
                "margin:6px 0 4px 0; letter-spacing:0.03em;'>School filter</p>",
                unsafe_allow_html=True)
    tier_filter = st.multiselect(
        "Show tiers",
        options=["Strong", "Moderate", "Low", "Critical"],
        default=["Strong", "Moderate", "Low", "Critical"],
    )
    enroll_min = st.slider("Min enrollment", min_value=0, max_value=5000, value=0, step=50)

# ── KPI values ────────────────────────────────────────────────────────────────
total_schools  = len(school_avg)
strong_count   = int((school_avg["tier"] == "Strong").sum())
critical_count = int((school_avg["tier"] == "Critical").sum())

# ══════════════════════════════════════════════════════════════════════════════
# HERO BANNER  (matches CPS Chronic Absenteeism style exactly)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style='background:linear-gradient(135deg,#003057 0%,#00497a 100%);
            border-radius:12px; padding:40px 48px; margin-bottom:28px;
            border-left:6px solid #C8973A; width:100%;'>
    <div style='font-size:2.2rem; font-weight:800; color:#FFFFFF; line-height:1.2; margin-bottom:16px;'>
        Forecasting Meal Participation Before Budgets Are Set
    </div>
    <div style='font-size:0.97rem; color:#B8CFDF; line-height:1.7;'>
        District 299 serves meals to <b style='color:#FFFFFF;'>hundreds of thousands of students</b>
        every school day. This tool uses machine-learning models trained on school-level records to
        predict participation rates for the months ahead — so nutrition staff and school leaders can
        plan accurately instead of reacting to shortfalls.
    </div>
</div>
""", unsafe_allow_html=True)

# ── KPI strip ─────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
kpis = [
    ("62.1%",         "Avg Lunch Participation",        "Mar 2026 district average"),
    ("40.8%",         "Avg Breakfast Participation",    "Mar 2026 district average"),
    (f"{strong_count}",   "Schools — Strong (>65%)",    f"{strong_count / total_schools * 100:.0f}% of all schools"),
    (f"{critical_count}", "Schools — Critical (<40%)",  f"{critical_count / total_schools * 100:.0f}% of all schools"),
]
for col, (val, lbl, sub) in zip([c1, c2, c3, c4], kpis):
    with col:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value'>{val}</div>
            <div class='metric-label'>{lbl}</div>
            <div class='metric-sub'>{sub}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# WHY IT MATTERS  /  HOW IT WORKS
# ══════════════════════════════════════════════════════════════════════════════
col_l, col_r = st.columns([1.05, 1], gap="large")

with col_l:
    st.markdown("""
    <div style='font-size:1.25rem; font-weight:800; color:#003057; margin-bottom:4px;
                border-left:5px solid #C8973A; padding-left:14px;'>
        Why Meal Participation Rates Matter
    </div>
    <div style='font-size:0.82rem; color:#4A6580; margin-bottom:18px; padding-left:19px;'>
        What the data signals and why accurate forecasting is essential
    </div>
    """, unsafe_allow_html=True)

    reasons = [
        ("#4A90C4", "📊", "A direct nutrition equity signal",
         "Free and reduced-price meals are the primary food source for the majority of enrolled students. Declining participation is an early warning that students are going without."),
        ("#003057", "📉", "Declining breakfast rates predict winter absenteeism",
         "Schools that see breakfast participation fall in October reliably experience higher absence rates in January and February — typically six to eight weeks later."),
        ("#C8973A", "🏫", "Operational and staffing efficiency",
         "Accurate monthly forecasts allow kitchen teams to right-size food preparation and staffing schedules, reducing waste without compromising service levels."),
        ("#22C55E", "🎯", "Early enough to act",
         "By forecasting April through June in March, leadership has a full quarter to target outreach, adjust menus, and coordinate with school counselors before the trend solidifies."),
    ]
    for color, icon, title, body in reasons:
        st.markdown(f"""
        <div style='background:#FFFFFF; border:1px solid #E2E8F0; border-left:5px solid {color};
                    border-radius:0 10px 10px 0; padding:16px 18px; margin-bottom:12px;
                    box-shadow:0 1px 4px rgba(0,48,87,0.06);'>
            <div style='font-size:0.9rem; font-weight:700; color:#003057; margin-bottom:6px;'>
                {icon}&nbsp; {title}
            </div>
            <div style='font-size:0.82rem; color:#334D66; line-height:1.6;'>{body}</div>
        </div>
        """, unsafe_allow_html=True)

with col_r:
    st.markdown("""
    <div style='font-size:1.25rem; font-weight:800; color:#003057; margin-bottom:4px;
                border-left:5px solid #C8973A; padding-left:14px;'>
        From School Records to a Forecast — How It Works
    </div>
    <div style='font-size:0.82rem; color:#4A6580; margin-bottom:18px; padding-left:19px;'>
        Five steps from raw data to a school-level monthly prediction
    </div>
    """, unsafe_allow_html=True)

    stages = [
        ("#4A90C4",  "1", "Collect monthly school records",
         "Lunch and breakfast counts, enrollment, and daily attendance data across all 556 schools for the full school year."),
        ("#8B5CF6",  "2", "Engineer lag and trend features",
         "The prior month's participation and a three-month rolling average are computed per school — the signals the model relies on most."),
        ("#C8973A",  "3", "Train a Gradient Boosted Tree ensemble",
         "One hundred decision trees are trained in PySpark MLlib — one model for lunch, one for breakfast — on school-level records from the current year."),
        ("#EF4444",  "4", "Score future months without Spark",
         "Model trees are stored as Parquet files and scored in pure Python. No Java runtime is needed; predictions run in milliseconds on any machine."),
        ("#22C55E",  "5", "Forecast at district, network, or school level",
         "The same model runs at any scope — district-wide, a single network, or one school — so every level of leadership sees a forecast relevant to their span of control."),
    ]
    for color, num, title, desc in stages:
        st.markdown(f"""
        <div style='display:flex; align-items:flex-start; margin-bottom:14px; gap:14px;
                    background:#FFFFFF; border:1px solid #E2E8F0; border-radius:10px;
                    padding:14px 16px; box-shadow:0 1px 4px rgba(0,48,87,0.06);'>
            <div style='min-width:36px; height:36px; background:{color}; border-radius:50%;
                        display:flex; align-items:center; justify-content:center;
                        font-weight:800; font-size:1rem; color:white; flex-shrink:0;'>{num}</div>
            <div>
                <div style='font-weight:700; font-size:0.92rem; color:#003057; margin-bottom:4px;'>{title}</div>
                <div style='font-size:0.8rem; color:#4A6580; line-height:1.5;'>{desc}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# DISTRICT 3-MONTH GBT FORECAST
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-header'>District-Wide 3-Month Forecast</div>",
            unsafe_allow_html=True)
st.markdown(
    "<div class='section-sub'>Apr – Jun 2026 forecast computed by averaging all school features "
    "and running the forecast model · Solid = actual · Dashed = forecast · Shaded = ±RMSE band</div>",
    unsafe_allow_html=True,
)

with st.spinner("Running district-level forecast…"):
    d_lunch_fc, d_bf_fc = aggregate_gbt_forecast(df)

d_lunch_fc_pct = [v * 100 for v in d_lunch_fc]
d_bf_fc_pct    = [v * 100 for v in d_bf_fc]

d_lunch_upper = [v + LUNCH_RMSE     * 100 for v in d_lunch_fc_pct]
d_lunch_lower = [v - LUNCH_RMSE     * 100 for v in d_lunch_fc_pct]
d_bf_upper    = [v + BREAKFAST_RMSE * 100 for v in d_bf_fc_pct]
d_bf_lower    = [v - BREAKFAST_RMSE * 100 for v in d_bf_fc_pct]

# Connecting points: include Mar in the forecast line so it joins the history
CONN_LUNCH = [LUNCH_PCT[-1]] + d_lunch_fc_pct      # Mar + Apr May Jun
CONN_BF    = [BREAKFAST_PCT[-1]] + d_bf_fc_pct
CONN_X     = ["Mar"] + FORECAST_MONTHS             # Mar Apr May Jun

fig_fc = go.Figure()

# ── Historical bars (Aug-Mar) ─────────────────────────────────────────────
fig_fc.add_trace(go.Bar(
    name="Lunch (Actual)",
    x=MONTHS, y=LUNCH_PCT,
    marker_color="#003057",
    yaxis="y",
))
fig_fc.add_trace(go.Bar(
    name="Breakfast (Actual)",
    x=MONTHS, y=BREAKFAST_PCT,
    marker_color="#C8973A",
    yaxis="y",
))

# ── Forecast lines (Mar → Jun, connected) ────────────────────────────────
fig_fc.add_trace(go.Scatter(
    name="Lunch (Forecasted)",
    x=CONN_X, y=CONN_LUNCH,
    mode="lines+markers",
    line=dict(color="#003057", width=2.5, dash="dash"),
    marker=dict(size=8, color="#003057", symbol="circle-open"),
))
fig_fc.add_trace(go.Scatter(
    name="Breakfast (Forecasted)",
    x=CONN_X, y=CONN_BF,
    mode="lines+markers",
    line=dict(color="#C8973A", width=2.5, dash="dash"),
    marker=dict(size=8, color="#C8973A", symbol="circle-open"),
))

# ── Confidence bands (Apr-Jun only) ──────────────────────────────────────
fig_fc.add_trace(go.Scatter(
    x=FORECAST_MONTHS, y=d_lunch_upper,
    mode="lines", line=dict(width=0), showlegend=False, name="_lu",
))
fig_fc.add_trace(go.Scatter(
    x=FORECAST_MONTHS, y=d_lunch_lower,
    mode="lines", line=dict(width=0),
    fill="tonexty", fillcolor="rgba(0,48,87,0.10)",
    showlegend=False, name="_ll",
))
fig_fc.add_trace(go.Scatter(
    x=FORECAST_MONTHS, y=d_bf_upper,
    mode="lines", line=dict(width=0), showlegend=False, name="_bu",
))
fig_fc.add_trace(go.Scatter(
    x=FORECAST_MONTHS, y=d_bf_lower,
    mode="lines", line=dict(width=0),
    fill="tonexty", fillcolor="rgba(200,151,58,0.12)",
    showlegend=False, name="_bl",
))

# ── Forecast boundary line at Apr ────────────────────────────────────────
fig_fc.add_shape(
    type="line", x0="Apr", x1="Apr", y0=0, y1=1,
    xref="x", yref="paper",
    line=dict(color="#64748B", dash="dot", width=1.5),
)
fig_fc.add_annotation(
    x="Apr", y=0.96, xref="x", yref="paper",
    text="  Forecast →",
    showarrow=False, font=dict(color="#64748B", size=11), xanchor="left",
)

# ── Forecast value labels ─────────────────────────────────────────────────
for month, lv, bv in zip(FORECAST_MONTHS, d_lunch_fc_pct, d_bf_fc_pct):
    fig_fc.add_annotation(
        x=month, y=lv + 2.5,
        text=f"{lv:.1f}%",
        showarrow=False,
        font=dict(size=10, color="#003057", weight=700),
    )
    fig_fc.add_annotation(
        x=month, y=bv - 3.0,
        text=f"{bv:.1f}%",
        showarrow=False,
        font=dict(size=10, color="#C8973A", weight=700),
    )

fig_fc.update_layout(
    **_LAYOUT,
    barmode="group",
    xaxis=dict(
        title="Month",
        categoryorder="array",
        categoryarray=ALL_MONTHS,
        showgrid=True,
        gridcolor="#F1F5F9",
    ),
    yaxis=dict(
        title="Participation rate (%)",
        range=[0, 80],
        showgrid=True,
        gridcolor="#F1F5F9",
    ),
    height=460,
)
st.plotly_chart(fig_fc)

# ── 3-month forecast summary cards ───────────────────────────────────────
fc1, fc2, fc3, fc4, fc5, fc6 = st.columns(6)
fc_pairs = list(zip(
    ["Apr Lunch", "May Lunch", "Jun Lunch",
     "Apr Breakfast", "May Breakfast", "Jun Breakfast"],
    d_lunch_fc_pct + d_bf_fc_pct,
    ["#003057"] * 3 + ["#C8973A"] * 3,
    [fc1, fc2, fc3, fc4, fc5, fc6],
))
for lbl, val, color, col in fc_pairs:
    with col:
        st.markdown(f"""
        <div style='background:#FFFFFF; border:1px solid #D1DBE8;
                    border-top:3px solid {color};
                    border-radius:8px; padding:14px 12px; text-align:center;
                    box-shadow:0 1px 4px rgba(0,48,87,0.06);'>
            <div style='font-size:1.5rem; font-weight:800; color:{color};'>{val:.1f}%</div>
            <div style='font-size:0.7rem; font-weight:700; text-transform:uppercase;
                        letter-spacing:0.05em; color:#64748B; margin-top:4px;'>{lbl}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# WHAT DRIVES PARTICIPATION — feature importance
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-header'>What Drives the Forecast?</div>", unsafe_allow_html=True)
st.markdown("<div class='section-sub'>Feature importance — the factors each model found most predictive, in order</div>",
            unsafe_allow_html=True)

fi_left, fi_right = st.columns(2, gap="large")

with fi_left:
    lunch_feats = ["lunch_part_lag_1", "lunch_mom_pct", "lunch_part_roll3",
                   "MONTH", "absence_rate", "ENROLLMENT"]
    lunch_impts = [69.9, 13.8, 9.3, 3.1, 0.9, 0.6]
    lunch_colors = ["#003057" if v == max(lunch_impts) else "#4A90C4"
                    for v in lunch_impts]

    fig_fi_l = go.Figure(go.Bar(
        x=lunch_impts[::-1],
        y=lunch_feats[::-1],
        orientation="h",
        marker_color=lunch_colors[::-1],
        text=[f"{v:.1f}%" for v in lunch_impts[::-1]],
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig_fi_l.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Aptos, Nunito Sans, Segoe UI, Arial", size=12, color="#334D66"),
        margin=dict(l=10, r=60, t=10, b=10),
        showlegend=False,
        title=dict(text="🍽️  Lunch model — top drivers",
                   font=dict(size=13, color="#003057")),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9",
                   showticklabels=False, range=[0, 85]),
        yaxis=dict(showgrid=False, tickfont=dict(size=10.5)),
        height=280,
    )
    st.plotly_chart(fig_fi_l)

    # Explainer
    st.markdown("""
    <div class='insight-card'>
        <div class='title'>📌 Prior-month participation dominates (69.9%)</div>
        <div class='body'>A school's lunch rate last month is by far the strongest signal.
        A three-month rolling trend adds further context.
        Month-over-month momentum captures acceleration or deceleration.</div>
    </div>
    """, unsafe_allow_html=True)

with fi_right:
    bf_feats  = ["ENROLLMENT", "breakfast_roll3", "breakfast_lag_1",
                 "MONTH", "pct_free_reduced_lunch", "absence_rate"]
    bf_impts  = [28.9, 28.2, 12.7, 8.4, 6.1, 4.2]
    bf_colors = ["#C8973A" if v == max(bf_impts) else "#D4AE72"
                 for v in bf_impts]

    fig_fi_b = go.Figure(go.Bar(
        x=bf_impts[::-1],
        y=bf_feats[::-1],
        orientation="h",
        marker_color=bf_colors[::-1],
        text=[f"{v:.1f}%" for v in bf_impts[::-1]],
        textposition="outside",
        textfont=dict(size=10),
    ))
    fig_fi_b.update_layout(
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Aptos, Nunito Sans, Segoe UI, Arial", size=12, color="#334D66"),
        margin=dict(l=10, r=60, t=10, b=10),
        showlegend=False,
        title=dict(text="🥐  Breakfast model — top drivers",
                   font=dict(size=13, color="#003057")),
        xaxis=dict(showgrid=True, gridcolor="#F1F5F9",
                   showticklabels=False, range=[0, 40]),
        yaxis=dict(showgrid=False, tickfont=dict(size=10.5)),
        height=280,
    )
    st.plotly_chart(fig_fi_b)

    st.markdown("""
    <div class='insight-card'>
        <div class='title'>📌 School size and rolling trend share top billing</div>
        <div class='body'>Unlike lunch, breakfast participation is co-driven by enrollment scale
        and a three-month rolling average. Free-and-reduced lunch eligibility —
        a household hardship proxy — is also a meaningful signal.</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MODEL ACCURACY
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-header'>How Accurate Are the Models?</div>",
            unsafe_allow_html=True)
st.markdown("<div class='section-sub'>Tested on a hold-out set from Mar 2026 — school-level participation rates</div>",
            unsafe_allow_html=True)

acc1, acc2, acc3, acc4 = st.columns(4)
accuracy_kpis = [
    ("#4A90C4",  "2.92%", "Lunch RMSE",
     "Root mean squared error on the test set."),
    ("#003057",  "0.74%", "Lunch MAE",
     "Mean absolute error — typical prediction is within 0.74% of actual."),
    ("#C8973A",  "2.99%", "Breakfast RMSE",
     "Root mean squared error on the test set."),
    ("#8B5CF6",  "2.00%", "Breakfast MAE",
     "Mean absolute error — typical prediction is within 2% of actual."),
]
for col, (color, val, lbl, body) in zip([acc1, acc2, acc3, acc4], accuracy_kpis):
    with col:
        st.markdown(f"""
        <div style='background:#FFFFFF; border:1px solid #D1DBE8; border-top:4px solid {color};
                    border-radius:12px; padding:20px 18px; height:100%;
                    box-shadow:0 1px 4px rgba(0,48,87,0.06);'>
            <div style='font-size:2rem; font-weight:800; color:{color};'>{val}</div>
            <div style='font-size:0.78rem; font-weight:700; color:#1E293B;
                        text-transform:uppercase; letter-spacing:0.04em;
                        margin-top:6px;'>{lbl}</div>
            <div style='font-size:0.76rem; color:#64748B; margin-top:6px;
                        line-height:1.5;'>{body}</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# CHART 2 — School-level scatter
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-header'>School-Level Participation Distribution</div>",
            unsafe_allow_html=True)
st.markdown("<div class='section-sub'>Each bubble is one school — sized by enrollment, coloured by tier</div>",
            unsafe_allow_html=True)

scatter_df = school_avg[
    (school_avg["tier"].isin(tier_filter)) &
    (school_avg["ENROLLMENT"] >= enroll_min)
].copy()

fig2 = px.scatter(
    scatter_df,
    x="lunch_pct",
    y="breakfast_pct",
    size="ENROLLMENT",
    color="tier",
    color_discrete_map=TIER_COLORS,
    size_max=30,
    hover_data={
        "SCHOOL_NAME": True,
        "ENROLLMENT": True,
        "absence_pct": True,
        "lunch_pct": False,
        "breakfast_pct": False,
        "tier": False,
    },
    labels={
        "lunch_pct": "Lunch participation (%)",
        "breakfast_pct": "Breakfast participation (%)",
        "absence_pct": "Absence rate (%)",
        "ENROLLMENT": "Enrollment",
        "SCHOOL_NAME": "School",
    },
    custom_data=["SCHOOL_NAME"],
)

fig2.add_vline(
    x=62.4,
    line_dash="dot", line_color="#64748B", line_width=1.5,
    annotation_text="Dist. avg lunch 62.4%",
    annotation_position="top right",
    annotation_font_color="#64748B",
    annotation_font_size=11,
)
fig2.add_hline(
    y=40.6,
    line_dash="dot", line_color="#64748B", line_width=1.5,
    annotation_text="Dist. avg breakfast 40.6%",
    annotation_position="top right",
    annotation_font_color="#64748B",
    annotation_font_size=11,
)

fig2.update_layout(
    **_LAYOUT,
    xaxis=dict(title="Lunch participation (%)", showgrid=True, gridcolor="#F1F5F9"),
    yaxis=dict(title="Breakfast participation (%)", showgrid=True, gridcolor="#F1F5F9"),
    height=480,
)

st.plotly_chart(fig2)

if scatter_df.empty:
    st.warning("No schools match the current filters.")

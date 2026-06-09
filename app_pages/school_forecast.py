import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from utils.loader import load_data
from utils.forecast import gbt_forecast, aggregate_gbt_forecast, LUNCH_RMSE, BREAKFAST_RMSE

ACTUAL_MONTHS   = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
FORECAST_MONTHS = ["Apr", "May", "Jun"]
ALL_MONTHS      = ACTUAL_MONTHS + FORECAST_MONTHS

MONTH_LABEL = {8:"Aug", 9:"Sep", 10:"Oct", 11:"Nov", 12:"Dec",
               1:"Jan", 2:"Feb", 3:"Mar"}
MONTH_ORDER  = {m: i for i, m in enumerate(ACTUAL_MONTHS)}

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

ALL_NETWORKS_LABEL = "All Networks (District-Wide)"

NETWORK_DESCRIPTIONS = {
    "Charter":    "Independently operated, publicly funded schools with autonomy over curriculum and staffing.",
    "ISP":        "In-School Probation — schools receiving additional oversight and support due to underperformance.",
    "Contract":   "Schools managed by private operators under contract with CPS for specific student populations or programs.",
    "Options":    "Alternative schools serving students who need non-traditional settings — continuation, night school, or re-engagement programs.",
    **{f"Network {i}": "A geographic and instructional cluster of traditional CPS schools — one of 17 administrative networks spanning the city."
       for i in range(1, 18)},
}

# ── Load data ─────────────────────────────────────────────────────────────────
df = load_data()
def _network_sort_key(n):
    # Numeric networks ("Network 1" … "Network 17") sort before named ones
    parts = n.split()
    if len(parts) == 2 and parts[0] == "Network" and parts[1].isdigit():
        return (0, int(parts[1]), "")
    return (1, 0, n)

sorted_networks = sorted(df["NETWORK"].dropna().unique().tolist(), key=_network_sort_key)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("<p style='font-size:0.82rem; font-weight:700; color:#E8EDF2; "
                "margin:6px 0 4px 0;'>Forecast display</p>", unsafe_allow_html=True)
    show_forecast = st.radio(
        "Show forecast for",
        options=["Lunch", "Breakfast", "Both"],
        index=2,
        key="show_forecast_radio",
    )

# ══════════════════════════════════════════════════════════════════════════════
# HERO
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style='background:linear-gradient(135deg,#003057 0%,#00497a 100%);
            border-radius:12px; padding:32px 40px; margin-bottom:28px;
            border-left:6px solid #C8973A;'>
    <div style='font-size:0.72rem; font-weight:700; letter-spacing:0.14em;
                color:#C8973A; text-transform:uppercase; margin-bottom:10px;'>
        Chicago Public Schools · Meal Participation Forecasting
    </div>
    <div style='font-size:1.9rem; font-weight:800; color:#FFFFFF; line-height:1.25;'>
        Forecast at any level — District, Network, or School
    </div>
    <div style='font-size:0.92rem; color:#B8CFDF; margin-top:12px; max-width:700px; line-height:1.6;'>
        Drill from the full district down to a single school.
        At every level the model produces a 3-month Apr–Jun forecast.
        Select "All" at any step to see the aggregate for that level.
    </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — NETWORK SELECTION
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-header'>Step 1 — Choose a Network</div>",
            unsafe_allow_html=True)
st.markdown("<div class='section-sub'>Select a network to drill in, or keep "
            "\"All Networks\" for a district-wide forecast.</div>",
            unsafe_allow_html=True)

network_options = [ALL_NETWORKS_LABEL] + sorted_networks
selected_network = st.selectbox(
    "Network",
    options=network_options,
    index=0,
    label_visibility="collapsed",
    key="network_sel",
)

if selected_network != ALL_NETWORKS_LABEL:
    net_desc = NETWORK_DESCRIPTIONS.get(selected_network, "")
    if net_desc:
        st.markdown(
            f"<div class='info-box' style='margin-top:6px;'>ℹ️ <b>{selected_network}:</b> {net_desc}</div>",
            unsafe_allow_html=True,
        )

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — SCHOOL SELECTION (only when a specific network is chosen)
# ══════════════════════════════════════════════════════════════════════════════
if selected_network != ALL_NETWORKS_LABEL:
    net_df = df[df["NETWORK"] == selected_network].copy()
    schools_in_net = sorted(net_df["SCHOOL_NAME"].dropna().unique().tolist())
    ALL_SCHOOLS_LABEL = f"All Schools — {selected_network}"
    school_options = [ALL_SCHOOLS_LABEL] + schools_in_net

    st.markdown("<div class='section-header' style='margin-top:12px;'>"
                "Step 2 — Choose a School</div>", unsafe_allow_html=True)
    st.markdown("<div class='section-sub'>Select a specific school or keep "
                f"\"All Schools\" for a {selected_network} network forecast.</div>",
                unsafe_allow_html=True)

    selected_school = st.selectbox(
        "School",
        options=school_options,
        index=0,
        label_visibility="collapsed",
        key="school_sel",
    )
else:
    net_df = df.copy()
    selected_school = None
    ALL_SCHOOLS_LABEL = None

# ── Determine scope and view level ───────────────────────────────────────────
if selected_network == ALL_NETWORKS_LABEL:
    scope_df    = df.copy()
    scope_label = "District-Wide"
    view_level  = "district"
elif selected_school is None or selected_school == ALL_SCHOOLS_LABEL:
    scope_df    = net_df.copy()
    scope_label = f"{selected_network} Network"
    view_level  = "network"
else:
    scope_df    = net_df[net_df["SCHOOL_NAME"] == selected_school].copy()
    scope_label = selected_school
    view_level  = "school"

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# KPI STRIP
# ══════════════════════════════════════════════════════════════════════════════
avg_lunch = scope_df["LUNCH_PARTICIPATION"].mean() * 100
avg_bf    = scope_df["BREAKFAST_PARTICIPATION"].mean() * 100
n_schools = scope_df["SCHOOL_NAME"].nunique()

def _tier(p):
    return "Critical" if p < 40 else "Low" if p < 55 else "Moderate" if p < 65 else "Strong"

school_avgs = (
    scope_df.groupby("SCHOOL_NAME")["LUNCH_PARTICIPATION"].mean() * 100
)
n_critical = int((school_avgs < 40).sum())
n_strong   = int((school_avgs >= 65).sum())

if view_level == "school":
    tier = _tier(avg_lunch)
    tier_color = TIER_COLORS.get(tier, "#64748B")
    kpis = [
        (f"{avg_lunch:.1f}%",  "Avg Lunch Participation",     "Year-to-date average",        "#003057"),
        (f"{avg_bf:.1f}%",     "Avg Breakfast Participation", "Year-to-date average",        "#003057"),
        (tier,                 "Participation Tier",          "Based on lunch average",      tier_color),
        (str(scope_df["MONTH"].nunique()), "Months of Data",  "Available school-year months","#4A90C4"),
    ]
elif view_level == "network":
    kpis = [
        (f"{avg_lunch:.1f}%",  "Avg Lunch — Network",      f"{selected_network}",           "#003057"),
        (f"{avg_bf:.1f}%",     "Avg Breakfast — Network",  f"{selected_network}",           "#003057"),
        (str(n_schools),       "Schools in Network",       f"{n_critical} critical (<40%)", "#4A90C4"),
        (str(n_critical),      "Critical Schools",         "Lunch participation <40%",      "#EF4444"),
    ]
else:
    kpis = [
        (f"{avg_lunch:.1f}%",  "Avg Lunch — District",  "Across all 556 schools",           "#003057"),
        (f"{avg_bf:.1f}%",     "Avg Breakfast — District","Across all 556 schools",         "#003057"),
        (str(n_strong),        "Strong Schools (≥65%)",  f"{n_strong/n_schools*100:.0f}% of district","#4A90C4"),
        (str(n_critical),      "Critical Schools (<40%)",f"{n_critical/n_schools*100:.0f}% of district","#EF4444"),
    ]

c1, c2, c3, c4 = st.columns(4)
for col, (val, lbl, sub, col_color) in zip([c1, c2, c3, c4], kpis):
    with col:
        st.markdown(f"""
        <div class='metric-card'>
            <div class='metric-value' style='color:{col_color};'>{val}</div>
            <div class='metric-label'>{lbl}</div>
            <div class='metric-sub'>{sub}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# COMPUTE FORECAST
# ══════════════════════════════════════════════════════════════════════════════
part_shift = 0.0
abs_shift  = 0.0

# ── Historical actuals: monthly averages for this scope ───────────────────────
monthly = (
    scope_df.sort_values("MONTH_START")
    .groupby("MONTH_START")
    .agg(MONTH=("MONTH","first"),
         LUNCH=("LUNCH_PARTICIPATION","mean"),
         BREAKFAST=("BREAKFAST_PARTICIPATION","mean"))
    .reset_index()
)
monthly["lbl"] = monthly["MONTH"].map(MONTH_LABEL)
monthly = monthly.dropna(subset=["lbl"])
monthly["order"] = monthly["lbl"].map(MONTH_ORDER)
monthly = monthly.sort_values("order").reset_index(drop=True)

actual_x              = monthly["lbl"].tolist()
lunch_actuals_pct     = (monthly["LUNCH"]     * 100).tolist()
breakfast_actuals_pct = (monthly["BREAKFAST"] * 100).tolist()

# ── GBT forecast ──────────────────────────────────────────────────────────────
with st.spinner(f"Running forecast for {scope_label}…"):
    if view_level == "school":
        school_data = scope_df.sort_values("MONTH_START").reset_index(drop=True)
        lunch_fc_vals, bf_fc_vals = gbt_forecast(
            school_data, n_ahead=3,
            part_shift_pp=part_shift,
            absence_shift_pp=abs_shift,
        )
    else:
        lunch_fc_vals, bf_fc_vals = aggregate_gbt_forecast(scope_df)

lunch_fc_pct = [v * 100 for v in lunch_fc_vals]
bf_fc_pct    = [v * 100 for v in bf_fc_vals]

lunch_upper = [v + LUNCH_RMSE     * 100 for v in lunch_fc_pct]
lunch_lower = [v - LUNCH_RMSE     * 100 for v in lunch_fc_pct]
bf_upper    = [v + BREAKFAST_RMSE * 100 for v in bf_fc_pct]
bf_lower    = [v - BREAKFAST_RMSE * 100 for v in bf_fc_pct]

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FORECAST CHART
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"<div class='section-header'>Participation History & 3-Month Forecast"
            f" — {scope_label}</div>", unsafe_allow_html=True)
st.markdown("<div class='section-sub'>Solid lines = actual data · Dashed = forecast "
            "· Shaded = ±RMSE band (pp)</div>", unsafe_allow_html=True)

show = st.session_state.get("show_forecast_radio", "Both")

fig = go.Figure()

# Connect forecast from last actual month to avoid the gap
mar_lunch = lunch_actuals_pct[-1] if lunch_actuals_pct else 0.0
mar_bf    = breakfast_actuals_pct[-1] if breakfast_actuals_pct else 0.0
FC_X      = [actual_x[-1]] + FORECAST_MONTHS  # last actual month + Apr May Jun

if show in ("Lunch", "Both"):
    fig.add_trace(go.Scatter(
        name="Lunch (Actual)",
        x=actual_x, y=lunch_actuals_pct,
        mode="lines+markers",
        line=dict(color="#003057", width=2.5),
        marker=dict(size=7, color="#003057"),
    ))
    fig.add_trace(go.Scatter(
        name="Lunch (Forecasted)",
        x=FC_X, y=[mar_lunch] + lunch_fc_pct,
        mode="lines+markers",
        line=dict(color="#003057", width=2, dash="dash"),
        marker=dict(size=7, color="#003057", symbol="circle-open"),
    ))
    fig.add_trace(go.Scatter(
        x=FC_X, y=[mar_lunch] + lunch_upper,
        mode="lines", line=dict(width=0), showlegend=False, name="_lu",
    ))
    fig.add_trace(go.Scatter(
        x=FC_X, y=[mar_lunch] + lunch_lower,
        mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(0,48,87,0.10)",
        showlegend=False, name="_ll",
    ))

if show in ("Breakfast", "Both"):
    fig.add_trace(go.Scatter(
        name="Breakfast (Actual)",
        x=actual_x, y=breakfast_actuals_pct,
        mode="lines+markers",
        line=dict(color="#C8973A", width=2.5),
        marker=dict(size=7, color="#C8973A"),
    ))
    fig.add_trace(go.Scatter(
        name="Breakfast (Forecasted)",
        x=FC_X, y=[mar_bf] + bf_fc_pct,
        mode="lines+markers",
        line=dict(color="#C8973A", width=2, dash="dash"),
        marker=dict(size=7, color="#C8973A", symbol="circle-open"),
    ))
    fig.add_trace(go.Scatter(
        x=FC_X, y=[mar_bf] + bf_upper,
        mode="lines", line=dict(width=0), showlegend=False, name="_bu",
    ))
    fig.add_trace(go.Scatter(
        x=FC_X, y=[mar_bf] + bf_lower,
        mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(200,151,58,0.12)",
        showlegend=False, name="_bl",
    ))

# Forecast boundary — use add_shape (categorical axis, add_vline won't work)
last_actual_month = actual_x[-1] if actual_x else "Mar"
fig.add_shape(
    type="line",
    x0=FORECAST_MONTHS[0], x1=FORECAST_MONTHS[0],
    y0=0, y1=1, xref="x", yref="paper",
    line=dict(color="#64748B", dash="dot", width=1.5),
)
fig.add_annotation(
    x=FORECAST_MONTHS[0], y=0.96, xref="x", yref="paper",
    text="  Forecast →",
    showarrow=False, font=dict(color="#64748B", size=11), xanchor="left",
)

fig.update_layout(
    **_LAYOUT,
    xaxis=dict(
        title="Month",
        categoryorder="array",
        categoryarray=ALL_MONTHS,
        showgrid=True,
        gridcolor="#F1F5F9",
    ),
    yaxis=dict(
        title="Participation rate (%)",
        range=[0, 105],
        showgrid=True,
        gridcolor="#F1F5F9",
    ),
    height=460,
)
st.plotly_chart(fig, use_container_width=True)

# ── Accuracy callout ──────────────────────────────────────────────────────────
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
st.markdown("<div class='section-sub'>Observed averages (Aug–Mar) plus forecast rows (Apr–Jun)</div>",
            unsafe_allow_html=True)

table_rows = [
    {
        "Month":       row["lbl"],
        "Lunch %":     f"{row['LUNCH']*100:.1f}%",
        "Breakfast %": f"{row['BREAKFAST']*100:.1f}%",
        "Source":      "Actual",
    }
    for _, row in monthly.iterrows()
]
for lbl, lp, bp in zip(["Apr (Forecast)", "May (Forecast)", "Jun (Forecast)"],
                        lunch_fc_pct, bf_fc_pct):
    table_rows.append({
        "Month":       lbl,
        "Lunch %":     f"{lp:.1f}%",
        "Breakfast %": f"{bp:.1f}%",
        "Source":      "Forecast",
    })

st.dataframe(pd.DataFrame(table_rows), hide_index=True)

st.markdown("<hr class='thin'/>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# MEALS TO BE PREPARED
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-header'>Meals to Be Prepared</div>",
            unsafe_allow_html=True)
st.markdown(
    "<div class='section-sub'>"
    "Daily meal count = Participation Rate × Enrollment. "
    "Historical bars use actual reported meal averages; "
    "forecast bars apply the model's predicted rate to the most-recent enrollment."
    "</div>",
    unsafe_allow_html=True,
)

# ── Enrollment for forecast months ───────────────────────────────────────────
latest_month_start  = scope_df["MONTH_START"].max()
forecast_enrollment = scope_df[scope_df["MONTH_START"] == latest_month_start]["ENROLLMENT"].sum()

# ── Historical monthly meal totals ────────────────────────────────────────────
monthly_meals = (
    scope_df.sort_values("MONTH_START")
    .groupby("MONTH_START")
    .agg(
        MONTH=("MONTH",                   "first"),
        LUNCH_MEALS=("LUNCH_AVERAGE_PER_DAY",     "sum"),
        BF_MEALS=("BREAKFAST_AVERAGE_PER_DAY",    "sum"),
        ENROLLMENT_TOTAL=("ENROLLMENT",           "sum"),
    )
    .reset_index()
)
monthly_meals["lbl"]   = monthly_meals["MONTH"].map(MONTH_LABEL)
monthly_meals          = monthly_meals.dropna(subset=["lbl"])
monthly_meals["order"] = monthly_meals["lbl"].map(MONTH_ORDER)
monthly_meals          = monthly_meals.sort_values("order").reset_index(drop=True)

# ── Forecast meal counts ──────────────────────────────────────────────────────
fc_lunch_meals = [r / 100 * forecast_enrollment for r in lunch_fc_pct]
fc_bf_meals    = [r / 100 * forecast_enrollment for r in bf_fc_pct]

# ── KPI cards — one per forecast month ───────────────────────────────────────
kc1, kc2, kc3 = st.columns(3)
for col, month, lm, bm in zip(
    [kc1, kc2, kc3],
    ["April", "May", "June"],
    fc_lunch_meals, fc_bf_meals,
):
    total = lm + bm
    with col:
        st.markdown(f"""
        <div class='metric-card' style='border-top:3px solid #4A90C4; text-align:left;'>
            <div style='font-size:0.70rem; font-weight:700; letter-spacing:0.12em;
                        color:#4A90C4; text-transform:uppercase; margin-bottom:8px;'>
                {month} &nbsp;·&nbsp; Forecast
            </div>
            <div style='font-size:1.75rem; font-weight:800; color:#003057;
                        line-height:1.1; margin-bottom:4px;'>
                {total:,.0f}
            </div>
            <div class='metric-label' style='text-transform:none; letter-spacing:0;
                        font-size:0.75rem; margin-bottom:12px;'>
                total meals / day
            </div>
            <div style='display:flex; gap:20px; padding-top:10px;
                        border-top:1px solid #EEF2F7;'>
                <div>
                    <div style='font-size:1.05rem; font-weight:700;
                                color:#003057;'>{lm:,.0f}</div>
                    <div class='metric-sub'>🍽 Lunch</div>
                </div>
                <div style='color:#D1DBE8; align-self:center;'>|</div>
                <div>
                    <div style='font-size:1.05rem; font-weight:700;
                                color:#C8973A;'>{bm:,.0f}</div>
                    <div class='metric-sub'>🥞 Breakfast</div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Stacked bar chart: actual + forecast ──────────────────────────────────────
actual_x_m = monthly_meals["lbl"].tolist()
act_lunch  = monthly_meals["LUNCH_MEALS"].tolist()
act_bf     = monthly_meals["BF_MEALS"].tolist()

fig2 = go.Figure()

fig2.add_trace(go.Bar(
    name="Breakfast (Actual)",
    x=actual_x_m,
    y=act_bf,
    marker_color="rgba(200,151,58,0.80)",
    marker_line=dict(width=0),
))
fig2.add_trace(go.Bar(
    name="Lunch (Actual)",
    x=actual_x_m,
    y=act_lunch,
    marker_color="rgba(0,48,87,0.85)",
    marker_line=dict(width=0),
))
fig2.add_trace(go.Bar(
    name="Breakfast (Forecast)",
    x=FORECAST_MONTHS,
    y=fc_bf_meals,
    marker_color="rgba(200,151,58,0.38)",
    marker_line=dict(color="#C8973A", width=1.5),
    marker_pattern_shape="/",
    marker_pattern_fgcolor="#C8973A",
))
fig2.add_trace(go.Bar(
    name="Lunch (Forecast)",
    x=FORECAST_MONTHS,
    y=fc_lunch_meals,
    marker_color="rgba(0,48,87,0.28)",
    marker_line=dict(color="#003057", width=1.5),
    marker_pattern_shape="/",
    marker_pattern_fgcolor="#003057",
))

fig2.add_shape(
    type="line",
    x0=FORECAST_MONTHS[0], x1=FORECAST_MONTHS[0],
    y0=0, y1=1, xref="x", yref="paper",
    line=dict(color="#64748B", dash="dot", width=1.5),
)
fig2.add_annotation(
    x=FORECAST_MONTHS[0], y=0.96, xref="x", yref="paper",
    text="  Forecast →",
    showarrow=False, font=dict(color="#64748B", size=11), xanchor="left",
)

fig2.update_layout(
    **_LAYOUT,
    barmode="stack",
    xaxis=dict(
        title="Month",
        categoryorder="array",
        categoryarray=ALL_MONTHS,
        showgrid=False,
        gridcolor="#F1F5F9",
    ),
    yaxis=dict(
        title="Avg Daily Meals",
        showgrid=True,
        gridcolor="#F1F5F9",
        tickformat=",",
    ),
    height=420,
    bargap=0.25,
)
st.plotly_chart(fig2, use_container_width=True)

# ── Meals detail table ────────────────────────────────────────────────────────
st.markdown("<div class='section-sub' style='margin-bottom:8px;'>Monthly breakdown — "
            "actual reported daily averages + forecasted counts</div>",
            unsafe_allow_html=True)

meals_rows = [
    {
        "Month":                 row["lbl"],
        "Lunch Meals / Day":     f"{row['LUNCH_MEALS']:,.0f}",
        "Breakfast Meals / Day": f"{row['BF_MEALS']:,.0f}",
        "Total Meals / Day":     f"{row['LUNCH_MEALS'] + row['BF_MEALS']:,.0f}",
        "Enrollment":            f"{row['ENROLLMENT_TOTAL']:,}",
        "Source":                "Actual",
    }
    for _, row in monthly_meals.iterrows()
]
for lbl, lm, bm in zip(
    ["Apr (Forecast)", "May (Forecast)", "Jun (Forecast)"],
    fc_lunch_meals, fc_bf_meals,
):
    meals_rows.append({
        "Month":                 lbl,
        "Lunch Meals / Day":     f"{lm:,.0f}",
        "Breakfast Meals / Day": f"{bm:,.0f}",
        "Total Meals / Day":     f"{lm + bm:,.0f}",
        "Enrollment":            f"{forecast_enrollment:,}",
        "Source":                "Forecast",
    })

st.dataframe(pd.DataFrame(meals_rows), hide_index=True)

st.markdown("""
<div class='info-box' style='margin-top:10px;'>
    <b>Formula:</b>
    &nbsp;Historical months use <em>actual reported average meals per day</em> from the data.
    &nbsp;Forecast months: <em>Meals = Forecasted Participation Rate × Most-Recent Enrollment</em>.
    &nbsp;Add a buffer (typically 3–5 %) to account for day-to-day variance before placing food orders.
</div>
""", unsafe_allow_html=True)

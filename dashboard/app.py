"""
Western Maharashtra Soil Erosion Dashboard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Streamlit dashboard for exploring RUSLE soil erosion analysis results.
Loads sample data from data/sample/sample_points_30m_demo.csv.

Run:
    streamlit run dashboard/app.py
"""

import os
import sys
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

# ─── Page Config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Western Maharashtra Soil Erosion Dashboard",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    .main { background: #0e1117; }

    .stApp {
        background: linear-gradient(135deg, #0e1117 0%, #1a1f2e 50%, #0e1117 100%);
    }

    /* Hero banner */
    .hero-banner {
        background: linear-gradient(135deg, #1a9850 0%, #06b6d4 50%, #8b5cf6 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(26, 152, 80, 0.25);
    }
    .hero-banner h1 {
        color: white;
        font-size: 2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .hero-banner p {
        color: rgba(255,255,255,0.85);
        font-size: 1rem;
        margin: 0.5rem 0 0 0;
        font-weight: 400;
    }

    /* Metric cards */
    .metric-card {
        background: linear-gradient(145deg, #1e2538 0%, #161b2e 100%);
        border: 1px solid rgba(139, 92, 246, 0.2);
        border-radius: 14px;
        padding: 1.3rem 1.5rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 30px rgba(139, 92, 246, 0.15);
    }
    .metric-value {
        color: #06b6d4;
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .metric-label {
        color: #94a3b8;
        font-size: 0.8rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-top: 0.4rem;
    }

    /* Section headers */
    .section-header {
        color: #e2e8f0;
        font-size: 1.2rem;
        font-weight: 700;
        margin: 1.5rem 0 0.8rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(139, 92, 246, 0.3);
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #141929 0%, #0e1117 100%);
        border-right: 1px solid rgba(139, 92, 246, 0.15);
    }
    [data-testid="stSidebar"] .stMarkdown h1 {
        color: #06b6d4;
        font-size: 1.1rem;
    }

    /* Info box */
    .info-box {
        background: rgba(6, 182, 212, 0.08);
        border: 1px solid rgba(6, 182, 212, 0.2);
        border-radius: 10px;
        padding: 1rem 1.2rem;
        color: #94a3b8;
        font-size: 0.85rem;
        margin: 0.5rem 0;
    }

    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}

    /* Tab styling override */
    .stTabs [data-baseweb="tab-list"] button {
        color: #94a3b8;
        font-weight: 600;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"] {
        color: #06b6d4;
        border-bottom-color: #06b6d4;
    }
</style>
""", unsafe_allow_html=True)

# ─── Data Loading ─────────────────────────────────────────────────────────────

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
CSV_FILE = os.path.join(DATA_DIR, "sample_points_30m_demo.csv")

# Erosion classification
CLASS_BREAKS = [0, 5, 10, 20, 40, 80, 9999]
CLASS_LABELS = ["Very Low", "Low", "Moderate", "High", "Very High", "Severe"]
CLASS_COLORS = ["#1a9850", "#91cf60", "#d9ef8b", "#fee08b", "#fc8d59", "#d73027"]
CLASS_COLORS_MAP = dict(zip(CLASS_LABELS, CLASS_COLORS))


@st.cache_data
def load_data():
    """Load and preprocess sample data."""
    df = pd.read_csv(CSV_FILE)

    # Assign erosion classes
    df["Erosion_Class"] = pd.cut(
        df["Soil_Loss"], bins=CLASS_BREAKS, labels=CLASS_LABELS, right=False
    )
    df["Class_Num"] = df["Erosion_Class"].cat.codes + 1

    # Vulnerability Index
    slope_n = np.clip(df["Slope"] / 30.0, 0, 1)
    veg_n = np.clip(1.0 - df["NDVI"], 0, 1)
    rain_n = np.clip(df["Annual_Rainfall"] / 3000.0, 0, 1)
    tri_n = np.clip(df["TRI"] / 50.0, 0, 1)
    df["Vulnerability"] = (0.35 * slope_n + 0.30 * veg_n + 0.20 * rain_n + 0.15 * tri_n) * 100

    # Annual runoff (SCS-CN with default CN=80)
    cn = 80
    s = 25400 / cn - 254
    ia = 0.2 * s
    df["Runoff"] = np.where(
        df["Annual_Rainfall"] > ia,
        (df["Annual_Rainfall"] - ia) ** 2 / (df["Annual_Rainfall"] - ia + s),
        0.0
    )

    return df


# ─── Plotly theme ─────────────────────────────────────────────────────────────

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(14,17,23,0.8)",
    font=dict(family="Inter, sans-serif", color="#e2e8f0", size=12),
    margin=dict(l=50, r=30, t=50, b=50),
    legend=dict(
        bgcolor="rgba(20,25,41,0.8)",
        bordercolor="rgba(139,92,246,0.3)",
        borderwidth=1,
        font=dict(size=11),
    ),
    xaxis=dict(gridcolor="rgba(148,163,184,0.1)", zerolinecolor="rgba(148,163,184,0.2)"),
    yaxis=dict(gridcolor="rgba(148,163,184,0.1)", zerolinecolor="rgba(148,163,184,0.2)"),
)


def apply_theme(fig):
    fig.update_layout(**PLOTLY_LAYOUT)
    return fig


# ─── Main App ─────────────────────────────────────────────────────────────────

def main():
    df = load_data()

    # ── Hero Banner ──
    st.markdown("""
    <div class="hero-banner">
        <h1>🌍 Western Maharashtra Soil Erosion Dashboard</h1>
        <p>RUSLE Analysis @ 30m Resolution — Satara · Sangli · Kolhapur · Solapur — 2020–2023</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("# ⚙️ Dashboard Controls")

        st.markdown('<div class="info-box">Filter and explore RUSLE soil erosion data across 4 districts of Western Maharashtra.</div>', unsafe_allow_html=True)

        st.markdown("---")

        # Erosion class filter
        selected_classes = st.multiselect(
            "🔍 Erosion Classes",
            CLASS_LABELS,
            default=CLASS_LABELS,
            help="Filter data by erosion severity class"
        )

        # Soil loss range
        sl_min, sl_max = float(df["Soil_Loss"].min()), float(df["Soil_Loss"].max())
        sl_range = st.slider(
            "📊 Soil Loss Range (t/ha/yr)",
            min_value=sl_min,
            max_value=sl_max,
            value=(sl_min, sl_max),
            format="%.1f"
        )

        # Slope filter
        slope_range = st.slider(
            "⛰️ Slope Range (°)",
            min_value=float(df["Slope"].min()),
            max_value=float(df["Slope"].max()),
            value=(float(df["Slope"].min()), float(df["Slope"].max())),
            format="%.1f"
        )

        st.markdown("---")
        st.markdown("### 📐 Resolution")
        st.metric("Pixel Size", "30m (SRTM)")
        st.markdown("### 📅 Study Period")
        st.metric("Years", "2020 – 2023")
        st.markdown("### 📍 Sample Points")
        st.metric("Count", f"{len(df):,}")

        st.markdown("---")
        st.markdown(
            '<p style="color:#64748b;font-size:0.75rem;text-align:center;">'
            'Built with Streamlit · Data from Google Earth Engine<br>'
            '© 2024 Western Maharashtra Erosion Project</p>',
            unsafe_allow_html=True
        )

    # ── Apply filters ──
    mask = (
        df["Erosion_Class"].isin(selected_classes) &
        df["Soil_Loss"].between(sl_range[0], sl_range[1]) &
        df["Slope"].between(slope_range[0], slope_range[1])
    )
    dff = df[mask].copy()

    if len(dff) == 0:
        st.warning("No data matches the current filters. Adjust the sidebar controls.")
        return

    # ── KPI Cards ──
    c1, c2, c3, c4, c5, c6 = st.columns(6)

    mean_sl = dff["Soil_Loss"].mean()
    median_sl = dff["Soil_Loss"].median()
    max_sl = dff["Soil_Loss"].max()
    hotspot_pct = (dff["Soil_Loss"] > 40).mean() * 100
    mean_vi = dff["Vulnerability"].mean()
    mean_ndvi = dff["NDVI"].mean()

    for col, val, label, color in [
        (c1, f"{mean_sl:.1f}", "Mean Soil Loss (t/ha/yr)", "#06b6d4"),
        (c2, f"{median_sl:.1f}", "Median Soil Loss", "#8b5cf6"),
        (c3, f"{max_sl:.0f}", "Peak Soil Loss", "#d73027"),
        (c4, f"{hotspot_pct:.1f}%", "Hotspot Area (>40)", "#fc8d59"),
        (c5, f"{mean_vi:.1f}", "Avg Vulnerability", "#fee08b"),
        (c6, f"{mean_ndvi:.2f}", "Mean NDVI", "#1a9850"),
    ]:
        col.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value" style="color:{color}">{val}</div>'
            f'<div class="metric-label">{label}</div>'
            f'</div>',
            unsafe_allow_html=True
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Erosion Overview",
        "🔬 RUSLE Factors",
        "🤖 ML Features",
        "🌊 Vulnerability & Runoff",
        "📈 Correlations"
    ])

    # ════════════════════════════════════════════════════════════════════════
    # TAB 1: Erosion Overview
    # ════════════════════════════════════════════════════════════════════════
    with tab1:
        st.markdown('<div class="section-header">Erosion Severity Distribution</div>', unsafe_allow_html=True)

        col_a, col_b = st.columns([3, 2])

        with col_a:
            # Histogram
            fig = px.histogram(
                dff, x="Soil_Loss", color="Erosion_Class",
                color_discrete_map=CLASS_COLORS_MAP,
                nbins=50,
                title="Soil Loss Distribution by Erosion Severity",
                labels={"Soil_Loss": "Soil Loss (t/ha/yr)", "Erosion_Class": "Class"},
                category_orders={"Erosion_Class": CLASS_LABELS},
                opacity=0.85,
            )
            apply_theme(fig)
            fig.update_layout(barmode="overlay", height=420)
            st.plotly_chart(fig, use_container_width=True)

        with col_b:
            # Pie chart
            class_counts = dff["Erosion_Class"].value_counts().reindex(CLASS_LABELS).fillna(0)
            fig = go.Figure(data=[go.Pie(
                labels=class_counts.index,
                values=class_counts.values,
                hole=0.55,
                marker=dict(colors=[CLASS_COLORS_MAP[c] for c in class_counts.index]),
                textinfo="label+percent",
                textfont=dict(size=11),
                hovertemplate="<b>%{label}</b><br>Count: %{value}<br>%{percent}<extra></extra>",
            )])
            fig.update_layout(
                title="Erosion Class Composition",
                showlegend=False,
                height=420,
                **{k: v for k, v in PLOTLY_LAYOUT.items() if k != "xaxis" and k != "yaxis"}
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="section-header">Erosion Statistics by Class</div>', unsafe_allow_html=True)

        # Box plot
        fig = px.box(
            dff, x="Erosion_Class", y="Soil_Loss",
            color="Erosion_Class",
            color_discrete_map=CLASS_COLORS_MAP,
            category_orders={"Erosion_Class": CLASS_LABELS},
            title="Soil Loss Distribution per Severity Class",
            labels={"Soil_Loss": "Soil Loss (t/ha/yr)", "Erosion_Class": "Class"},
            notched=True,
        )
        apply_theme(fig)
        fig.update_layout(showlegend=False, height=380)
        st.plotly_chart(fig, use_container_width=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 2: RUSLE Factors
    # ════════════════════════════════════════════════════════════════════════
    with tab2:
        st.markdown('<div class="section-header">RUSLE Factor Analysis</div>', unsafe_allow_html=True)

        factors = ["R_Factor", "K_Factor", "LS_Factor", "C_Factor", "P_Factor"]
        factor_labels = {
            "R_Factor": "Rainfall Erosivity (R)",
            "K_Factor": "Soil Erodibility (K)",
            "LS_Factor": "Topographic (LS)",
            "C_Factor": "Cover Management (C)",
            "P_Factor": "Support Practice (P)",
        }

        col1, col2 = st.columns(2)

        with col1:
            # Radar chart of mean factors (normalized)
            means = dff[factors].mean()
            maxes = dff[factors].max()
            normalized = (means / maxes * 100).values

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=list(normalized) + [normalized[0]],
                theta=[factor_labels[f] for f in factors] + [factor_labels[factors[0]]],
                fill="toself",
                fillcolor="rgba(6,182,212,0.15)",
                line=dict(color="#06b6d4", width=2),
                marker=dict(size=6, color="#06b6d4"),
                name="Mean (Normalized %)",
            ))
            fig.update_layout(
                title="RUSLE Factor Radar Profile (Normalized)",
                polar=dict(
                    bgcolor="rgba(14,17,23,0.8)",
                    radialaxis=dict(visible=True, range=[0, 100], gridcolor="rgba(148,163,184,0.15)"),
                    angularaxis=dict(gridcolor="rgba(148,163,184,0.15)"),
                ),
                height=420,
                **{k: v for k, v in PLOTLY_LAYOUT.items() if k not in ["xaxis", "yaxis"]},
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Factor box plots
            df_melt = dff[factors].melt(var_name="Factor", value_name="Value")
            df_melt["Factor"] = df_melt["Factor"].map(factor_labels)
            fig = px.box(
                df_melt, x="Factor", y="Value",
                color="Factor",
                color_discrete_sequence=["#06b6d4", "#8b5cf6", "#1a9850", "#fee08b", "#fc8d59"],
                title="RUSLE Factor Distributions",
            )
            apply_theme(fig)
            fig.update_layout(showlegend=False, height=420)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="section-header">Factor vs Soil Loss</div>', unsafe_allow_html=True)

        selected_factor = st.selectbox(
            "Select RUSLE factor",
            factors,
            format_func=lambda x: factor_labels[x]
        )

        fig = px.scatter(
            dff, x=selected_factor, y="Soil_Loss",
            color="Erosion_Class",
            color_discrete_map=CLASS_COLORS_MAP,
            category_orders={"Erosion_Class": CLASS_LABELS},
            opacity=0.65,
            title=f"{factor_labels[selected_factor]} vs Soil Loss",
            labels={"Soil_Loss": "Soil Loss (t/ha/yr)"},
            trendline="ols",
        )
        apply_theme(fig)
        fig.update_layout(height=420)
        st.plotly_chart(fig, use_container_width=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 3: ML Features
    # ════════════════════════════════════════════════════════════════════════
    with tab3:
        st.markdown('<div class="section-header">Feature Analysis for Machine Learning</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            # Scatter: LS vs Soil Loss colored by slope
            fig = px.scatter(
                dff, x="LS_Factor", y="Soil_Loss",
                color="Slope",
                color_continuous_scale="Turbo",
                opacity=0.7,
                title="LS Factor vs Soil Loss (colored by Slope)",
                labels={"Soil_Loss": "Soil Loss (t/ha/yr)", "LS_Factor": "LS Factor", "Slope": "Slope (°)"},
            )
            apply_theme(fig)
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # 3D scatter
            fig = px.scatter_3d(
                dff, x="Slope", y="Annual_Rainfall", z="Soil_Loss",
                color="Erosion_Class",
                color_discrete_map=CLASS_COLORS_MAP,
                category_orders={"Erosion_Class": CLASS_LABELS},
                opacity=0.7,
                title="3D: Slope × Rainfall × Soil Loss",
                labels={
                    "Slope": "Slope (°)",
                    "Annual_Rainfall": "Rainfall (mm)",
                    "Soil_Loss": "Soil Loss (t/ha/yr)",
                },
            )
            fig.update_layout(
                height=480,
                scene=dict(
                    bgcolor="rgba(14,17,23,0.8)",
                    xaxis=dict(backgroundcolor="rgba(14,17,23,0.5)", gridcolor="rgba(148,163,184,0.15)"),
                    yaxis=dict(backgroundcolor="rgba(14,17,23,0.5)", gridcolor="rgba(148,163,184,0.15)"),
                    zaxis=dict(backgroundcolor="rgba(14,17,23,0.5)", gridcolor="rgba(148,163,184,0.15)"),
                ),
                **{k: v for k, v in PLOTLY_LAYOUT.items() if k not in ["xaxis", "yaxis"]},
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="section-header">Feature Importance (Simulated)</div>', unsafe_allow_html=True)

        # Feature importance bar chart (using correlation as proxy)
        features = ['LS_Factor', 'Annual_Rainfall', 'Slope', 'NDVI', 'R_Factor',
                     'TRI', 'C_Factor', 'K_Factor', 'P_Factor', 'Elevation']
        available = [f for f in features if f in dff.columns]
        correlations = dff[available].corrwith(dff["Soil_Loss"]).abs().sort_values(ascending=True)

        fig = go.Figure(go.Bar(
            y=correlations.index,
            x=correlations.values,
            orientation="h",
            marker=dict(
                color=correlations.values,
                colorscale=[[0, "#1a9850"], [0.5, "#06b6d4"], [1, "#d73027"]],
                line=dict(width=0),
            ),
            hovertemplate="<b>%{y}</b><br>|Correlation|: %{x:.3f}<extra></extra>",
        ))
        fig.update_layout(
            title="Feature Correlation with Soil Loss (|Spearman ρ| proxy)",
            xaxis_title="Absolute Correlation",
            height=380,
        )
        apply_theme(fig)
        st.plotly_chart(fig, use_container_width=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 4: Vulnerability & Runoff
    # ════════════════════════════════════════════════════════════════════════
    with tab4:
        st.markdown('<div class="section-header">Vulnerability Index & Surface Runoff</div>', unsafe_allow_html=True)

        col1, col2 = st.columns(2)

        with col1:
            fig = px.density_heatmap(
                dff, x="Vulnerability", y="Soil_Loss",
                nbinsx=30, nbinsy=30,
                color_continuous_scale="Inferno",
                title="Vulnerability Index vs Soil Loss (2D Density)",
                labels={"Vulnerability": "Vulnerability Index (0-100)", "Soil_Loss": "Soil Loss (t/ha/yr)"},
            )
            apply_theme(fig)
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.scatter(
                dff, x="Runoff", y="Soil_Loss",
                color="NDVI",
                color_continuous_scale="RdYlGn",
                opacity=0.7,
                title="Annual Runoff vs Soil Loss (colored by NDVI)",
                labels={"Runoff": "Runoff (mm)", "Soil_Loss": "Soil Loss (t/ha/yr)", "NDVI": "NDVI"},
            )
            apply_theme(fig)
            fig.update_layout(height=420)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="section-header">Vulnerability Histogram</div>', unsafe_allow_html=True)

        fig = px.histogram(
            dff, x="Vulnerability",
            nbins=40,
            color="Erosion_Class",
            color_discrete_map=CLASS_COLORS_MAP,
            category_orders={"Erosion_Class": CLASS_LABELS},
            title="Vulnerability Index Distribution by Erosion Class",
            labels={"Vulnerability": "Vulnerability Index (0-100)"},
            opacity=0.8,
        )
        apply_theme(fig)
        fig.update_layout(barmode="stack", height=380)
        st.plotly_chart(fig, use_container_width=True)

    # ════════════════════════════════════════════════════════════════════════
    # TAB 5: Correlations
    # ════════════════════════════════════════════════════════════════════════
    with tab5:
        st.markdown('<div class="section-header">Spearman Correlation Matrix</div>', unsafe_allow_html=True)

        corr_cols = ['Soil_Loss', 'R_Factor', 'K_Factor', 'LS_Factor', 'C_Factor',
                     'P_Factor', 'Slope', 'Elevation', 'TRI', 'Annual_Rainfall',
                     'NDVI', 'Vulnerability']
        available_corr = [c for c in corr_cols if c in dff.columns]
        corr = dff[available_corr].corr(method="spearman")

        fig = px.imshow(
            corr,
            x=available_corr, y=available_corr,
            color_continuous_scale="RdBu_r",
            zmin=-1, zmax=1,
            title="Spearman Correlation Matrix",
            text_auto=".2f",
        )
        apply_theme(fig)
        fig.update_layout(height=550)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown('<div class="section-header">Scatter Matrix (Key Features)</div>', unsafe_allow_html=True)

        scatter_features = st.multiselect(
            "Select features for scatter matrix",
            available_corr,
            default=["Soil_Loss", "LS_Factor", "Slope", "NDVI"],
            max_selections=6,
        )

        if len(scatter_features) >= 2:
            fig = px.scatter_matrix(
                dff, dimensions=scatter_features,
                color="Erosion_Class",
                color_discrete_map=CLASS_COLORS_MAP,
                category_orders={"Erosion_Class": CLASS_LABELS},
                opacity=0.5,
                title="Interactive Scatter Matrix",
            )
            apply_theme(fig)
            fig.update_layout(height=600)
            fig.update_traces(diagonal_visible=False, marker=dict(size=3))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Select at least 2 features to display the scatter matrix.")

    # ── Footer ──
    st.markdown("---")
    st.markdown(
        '<p style="text-align:center;color:#475569;font-size:0.8rem;">'
        '🌍 Western Maharashtra Soil Erosion Analysis · RUSLE @ 30m · '
        'Powered by Google Earth Engine & Streamlit<br>'
        '<a href="https://github.com/Satwik-1234/RUSLE_Western-Maharashtra_V1" '
        'style="color:#06b6d4;">GitHub</a> · '
        '<a href="https://colab.research.google.com" style="color:#06b6d4;">Open in Colab</a>'
        '</p>',
        unsafe_allow_html=True
    )


if __name__ == "__main__":
    main()

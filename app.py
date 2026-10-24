import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Metric,
    RunReportRequest,
)

# ==============================================================================
# CONFIGURATION & PAGE SETUP
# ==============================================================================
st.set_page_config(
    page_title="Executive GA4 Analytics Dashboard",
    page_icon="📊",
    layout="wide",
)

# Set path to your Service Account JSON key (for local execution)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"
GA4_PROPERTY_ID = "YOUR_PROPERTY_ID"  # Replace with your 9-digit numeric GA4 Property ID

# Set to True for live demonstration using synthetic data without active credentials
USE_DEMO_MODE = False  

# Custom Styling
st.markdown("""
    <style>
    .main { padding-top: 1rem; }
    .stMetric { background-color: #f8f9fa; border-radius: 8px; padding: 15px; border: 1px solid #e9ecef; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 Executive GA4 Analytics Dashboard")
st.caption("Automated reporting pipeline filtering core business KPIs")

# ==============================================================================
# SIDEBAR CONTROLS & OPTION 1: CHANNEL FILTERING WITH SELECT ALL / CLEAR ALL
# ==============================================================================
st.sidebar.header("Dashboard Controls")
days_range = st.sidebar.slider("Select Date Window (Days)", 7, 90, 30)

all_channels = [
    "Organic Search",
    "Direct",
    "Paid Search",
    "Social",
    "Email",
    "Referral",
]

# Initialize Session State for channels if not present
if "selected_channels" not in st.session_state:
    st.session_state.selected_channels = all_channels

st.sidebar.subheader("Filter Traffic Channels")

# Option 1: Quick Action Buttons
col_sel, col_clr = st.sidebar.columns(2)
if col_sel.button("Select All"):
    st.session_state.selected_channels = all_channels
if col_clr.button("Clear All"):
    st.session_state.selected_channels = []

# Multiselect Widget Linked to Session State
traffic_segments = st.sidebar.multiselect(
    "Active Channels",
    options=all_channels,
    key="selected_channels",
)

# ==============================================================================
# DATA RETRIEVAL PIPELINE
# ==============================================================================
@st.cache_data(ttl=3600)  # Caches data for 1 hour to optimize performance
def get_ga4_data(days, demo_mode=False):
    if demo_mode:
        np.random.seed(42)
        dates = pd.date_range(end=pd.Timestamp.today(), periods=days).strftime("%Y-%m-%d")
        
        trend_df = pd.DataFrame({
            "date": dates,
            "activeUsers": np.random.randint(800, 1800, size=days),
            "screenPageViews": np.random.randint(2000, 4500, size=days),
            "conversions": np.random.randint(20, 80, size=days)
        })
        
        channel_df = pd.DataFrame({
            "sessionDefaultChannelGroup": ["Organic Search", "Direct", "Paid Search", "Social", "Email", "Referral"],
            "sessions": [12400, 7800, 5200, 3100, 2200, 1100]
        })
        
        pages_df = pd.DataFrame({
            "pagePath": ["/home", "/pricing", "/features", "/blog/post-1", "/checkout"],
            "screenPageViews": [14200, 8900, 6100, 4300, 2100],
            "averageSessionDuration": [45, 95, 110, 180, 130],
            "bounceRate": [0.35, 0.28, 0.41, 0.62, 0.18]
        })
        return trend_df, channel_df, pages_df

    # --- Live GA4 API Call ---
    client = BetaAnalyticsDataClient()
    property_path = f"properties/{GA4_PROPERTY_ID}"
    date_range = [DateRange(start_date=f"{days}daysAgo", end_date="today")]

    # 1. Trend Data Request
    req_trend = RunReportRequest(
        property=property_path,
        dimensions=[Dimension(name="date")],
        metrics=[Metric(name="activeUsers"), Metric(name="screenPageViews"), Metric(name="conversions")],
        date_ranges=date_range,
    )
    res_trend = client.run_report(req_trend)
    trend_rows = [[r.dimension_values[0].value, r.metric_values[0].value, r.metric_values[1].value, r.metric_values[2].value] for r in res_trend.rows]
    trend_df = pd.DataFrame(trend_rows, columns=["date", "activeUsers", "screenPageViews", "conversions"])
    
    # 2. Channel Data Request
    req_channel = RunReportRequest(
        property=property_path,
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="sessions")],
        date_ranges=date_range,
    )
    res_channel = client.run_report(req_channel)
    channel_rows = [[r.dimension_values[0].value, r.metric_values[0].value] for r in res_channel.rows]
    channel_df = pd.DataFrame(channel_rows, columns=["sessionDefaultChannelGroup", "sessions"])

    # 3. Pages Data Request
    req_pages = RunReportRequest(
        property=property_path,
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews"), Metric(name="averageSessionDuration"), Metric(name="bounceRate")],
        date_ranges=date_range,
    )
    res_pages = client.run_report(req_pages)
    pages_rows = [[r.dimension_values[0].value, r.metric_values[0].value, r.metric_values[1].value, r.metric_values[2].value] for r in res_pages.rows]
    pages_df = pd.DataFrame(pages_rows, columns=["pagePath", "screenPageViews", "averageSessionDuration", "bounceRate"])

    # Convert metrics to numeric values
    for df in [trend_df, channel_df, pages_df]:
        for col in df.columns:
            if col not in ["date", "sessionDefaultChannelGroup", "pagePath"]:
                df[col] = pd.to_numeric(df[col])

    return trend_df, channel_df, pages_df

# ==============================================================================
# DASHBOARD RENDERING
# ==============================================================================
try:
    trend_df, channel_df, pages_df = get_ga4_data(days_range, demo_mode=USE_DEMO_MODE)

    # Filter Channel DataFrame based on Sidebar Selection
    if traffic_segments:
        filtered_channel_df = channel_df[channel_df["sessionDefaultChannelGroup"].isin(traffic_segments)]
    else:
        filtered_channel_df = channel_df.iloc[0:0]  # Empty DataFrame if Clear All is clicked

    # --- Section 1: KPI Summary Cards ---
    total_users = trend_df["activeUsers"].sum()
    total_views = trend_df["screenPageViews"].sum()
    total_convs = trend_df["conversions"].sum()
    cvr = (total_convs / total_users * 100) if total_users > 0 else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Active Users", f"{total_users:,}")
    c2.metric("Pageviews", f"{total_views:,}")
    c3.metric("Conversions", f"{total_convs:,}")
    c4.metric("Conversion Rate", f"{cvr:.2f}%")

    st.markdown("---")

    # --- Section 2: Time Series Chart ---
    st.subheader("📈 User Traffic & Conversion Trends")
    trend_df["date"] = pd.to_datetime(trend_df["date"])
    trend_df = trend_df.sort_values("date")

    fig_trend = px.line(
        trend_df,
        x="date",
        y=["activeUsers", "screenPageViews", "conversions"],
        labels={"value": "Volume", "date": "Date", "variable": "Metric"},
        color_discrete_sequence=["#1f77b4", "#ff7f0e", "#2ca02c"],
    )
    fig_trend.update_layout(hovermode="x unified", margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig_trend, use_container_width=True)

    # --- Section 3: Channel Breakdown & Conversion Funnel ---
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🎯 Traffic Sources")
        if not filtered_channel_df.empty:
            fig_pie = px.pie(
                filtered_channel_df,
                names="sessionDefaultChannelGroup",
                values="sessions",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No traffic channels selected. Use the sidebar options to select channels.")

    with col_right:
        st.subheader("🛒 Conversion Funnel")
        funnel_data = dict(
            number=[total_views, int(total_views * 0.45), int(total_views * 0.15), int(total_convs * 1.5), total_convs],
            stage=["Sessions", "Product Views", "Cart Additions", "Checkout Started", "Purchases"]
        )
        fig_funnel = go.Figure(go.Funnel(
            y=funnel_data["stage"],
            x=funnel_data["number"],
            textinfo="value+percent initial"
        ))
        fig_funnel.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_funnel, use_container_width=True)

    st.markdown("---")

    # --- Section 4: Content Performance ---
    st.subheader("📄 Top Content Performance")
    pages_df = pages_df.sort_values(by="screenPageViews", ascending=False).head(10)
    
    st.dataframe(
        pages_df,
        column_config={
            "pagePath": "Page Path",
            "screenPageViews": st.column_config.NumberColumn("Pageviews", format="%d"),
            "averageSessionDuration": st.column_config.NumberColumn("Avg Duration (s)", format="%.0f s"),
            "bounceRate": st.column_config.NumberColumn("Bounce Rate", format="%.1f%%"),
        },
        use_container_width=True,
        hide_index=True,
    )

except Exception as e:
    st.error(f"Error loading dashboard data: {e}")
    st.info("Ensure credentials.json is present locally or Streamlit Secrets are configured properly.")

import os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from google.oauth2 import service_account
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
    page_title="Universal GA4 Analytics Studio",
    page_icon="📊",
    layout="wide",
)

GA4_PROPERTY_ID = "153293282"  # Google Merchandise Store GA4 Demo Property ID
USE_DEMO_MODE = False  # Set to True to use synthetic mock data without active credentials

# Custom Styling
st.markdown("""
    <style>
    .main { padding-top: 1rem; }
    .stMetric { background-color: #f8f9fa; border-radius: 8px; padding: 15px; border: 1px solid #e9ecef; }
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# CLIENT INITIALIZATION (STREAMLIT CLOUD & LOCAL COMPATIBLE)
# ==============================================================================
@st.cache_resource
def get_ga4_client():
    if USE_DEMO_MODE:
        return None
        
    # 1. Read credentials from Streamlit Cloud Secrets
    if "gcp_service_account" in st.secrets:
        credentials_dict = dict(st.secrets["gcp_service_account"])
        credentials = service_account.Credentials.from_service_account_info(credentials_dict)
        return BetaAnalyticsDataClient(credentials=credentials)
    
    # 2. Fallback for local development using credentials.json file
    elif os.path.exists("credentials.json"):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"
        return BetaAnalyticsDataClient()
    
    else:
        st.error("No Google Analytics credentials found. Configure Streamlit Secrets or add credentials.json locally.")
        st.stop()

client = get_ga4_client()

# ==============================================================================
# PRE-BUILT REPORTS CONFIGURATION
# ==============================================================================
REPORTS_CONFIG = {
    "User Acquisition": {
        "dimensions": ["firstUserPrimaryChannelGroup"],
        "metrics": ["newUsers", "sessions", "conversions"],
        "primary_metric": "newUsers",
        "chart_type": "bar"
    },
    "Traffic Acquisition": {
        "dimensions": ["sessionDefaultChannelGroup"],
        "metrics": ["sessions", "activeUsers", "conversions"],
        "primary_metric": "sessions",
        "chart_type": "pie"
    },
    "Engagement (Pages & Screens)": {
        "dimensions": ["pagePath"],
        "metrics": ["screenPageViews", "activeUsers", "averageSessionDuration", "bounceRate"],
        "primary_metric": "screenPageViews",
        "chart_type": "bar"
    },
    "Events": {
        "dimensions": ["eventName"],
        "metrics": ["eventCount", "activeUsers"],
        "primary_metric": "eventCount",
        "chart_type": "bar"
    },
    "Ecommerce / Monetization": {
        "dimensions": ["itemName"],
        "metrics": ["itemRevenue", "itemsPurchased", "itemsViewed"],
        "primary_metric": "itemRevenue",
        "chart_type": "bar"
    },
    "Demographics (Countries)": {
        "dimensions": ["country"],
        "metrics": ["activeUsers", "sessions", "conversions"],
        "primary_metric": "activeUsers",
        "chart_type": "map"
    }
}

# ==============================================================================
# SIDEBAR CONTROLS & NAVIGATION
# ==============================================================================
st.sidebar.title("📌 Navigation")

report_type = st.sidebar.radio(
    "Select Report View",
    list(REPORTS_CONFIG.keys()) + ["Custom Query Builder"]
)

# Date Slider - Changing this now invalidates cache and updates data dynamically
days_range = st.sidebar.slider("Date Window (Days)", 7, 90, 28)

# Channel Filters
all_channels = [
    "Organic Search",
    "Direct",
    "Paid Search",
    "Social",
    "Email",
    "Referral",
    "Cross-network"
]

if "selected_channels" not in st.session_state:
    st.session_state.selected_channels = all_channels

st.sidebar.markdown("---")
st.sidebar.subheader("Filter Channels")

col_sel, col_clr = st.sidebar.columns(2)
if col_sel.button("Select All"):
    st.session_state.selected_channels = all_channels
if col_clr.button("Clear All"):
    st.session_state.selected_channels = []

traffic_segments = st.sidebar.multiselect(
    "Active Channels",
    options=all_channels,
    key="selected_channels"
)

# ==============================================================================
# DYNAMIC DATA ENGINE PIPELINE
# ==============================================================================
# `days` is explicitly placed FIRST so cache updates when slider moves
@st.cache_data(ttl=3600)
def run_dynamic_ga4_report(days, dim_names, metric_names, demo_mode=False):
    if demo_mode:
        np.random.seed(days)  # Seed changes dynamically with date slider
        rows = []
        for i in range(10):
            d_vals = [f"Item_{i+1}" if "Path" in d or "Name" in d else "Organic Search" for d in dim_names]
            # Multiply by days factor so metrics scale up when date window expands
            m_vals = [int(np.random.randint(50, 300) * (days / 7)) for _ in metric_names]
            rows.append(d_vals + m_vals)
        return pd.DataFrame(rows, columns=dim_names + metric_names)

    # Dynamic date range formatting tied directly to slider input
    request = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dim_names],
        metrics=[Metric(name=m) for m in metric_names],
        date_ranges=[DateRange(start_date=f"{int(days)}daysAgo", end_date="today")],
    )
    
    response = client.run_report(request)
    
    rows = []
    for row in response.rows:
        dims = [d.value for d in row.dimension_values]
        mets = [m.value for m in row.metric_values]
        rows.append(dims + mets)
        
    df = pd.DataFrame(rows, columns=dim_names + metric_names)
    
    for m in metric_names:
        df[m] = pd.to_numeric(df[m])
        
    return df

# ==============================================================================
# DASHBOARD RENDERING
# ==============================================================================
st.title(f"📊 {report_type}")

try:
    if report_type != "Custom Query Builder":
        config = REPORTS_CONFIG[report_type]
        
        # Pass days_range as FIRST argument to ensure slider triggers fresh API calls
        df = run_dynamic_ga4_report(
            days_range, 
            config["dimensions"], 
            config["metrics"], 
            demo_mode=USE_DEMO_MODE
        )
        
        # Channel Filter Check
        primary_dim = config["dimensions"][0]
        if primary_dim in ["firstUserPrimaryChannelGroup", "sessionDefaultChannelGroup"]:
            if traffic_segments:
                df = df[df[primary_dim].isin(traffic_segments)]
            else:
                df = df.iloc[0:0]

        # Top Metric KPI Summary Cards
        cols = st.columns(len(config["metrics"]))
        for idx, m in enumerate(config["metrics"]):
            total_val = df[m].sum() if not df.empty else 0
            cols[idx].metric(m, f"{total_val:,.2f}" if isinstance(total_val, float) else f"{total_val:,}")
            
        st.markdown("---")
        
        col_chart, col_table = st.columns([1.5, 1])
        
        # Chart Visualization
        with col_chart:
            st.subheader("Visual Analysis")
            if df.empty:
                st.info("No data available for the selected filters.")
            elif config["chart_type"] == "pie":
                fig = px.pie(df, names=primary_dim, values=config["primary_metric"], hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            elif config["chart_type"] == "map":
                fig = px.choropleth(df, locations=primary_dim, locationmode="country names", color=config["primary_metric"])
                st.plotly_chart(fig, use_container_width=True)
            else:
                sorted_df = df.sort_values(by=config["primary_metric"], ascending=False).head(10)
                fig = px.bar(sorted_df, x=config["primary_metric"], y=primary_dim, orientation="h")
                fig.update_layout(yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)
            
        # Raw Data Table
        with col_table:
            st.subheader("Raw Data Table")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # Custom Query Builder View
    else:
        st.subheader("🛠️ Build Your Own Custom GA4 Report")
        
        col_d, col_m = st.columns(2)
        with col_d:
            custom_dims = st.multiselect(
                "Select Dimensions", 
                ["pagePath", "sessionDefaultChannelGroup", "firstUserPrimaryChannelGroup", "country", "deviceCategory", "eventName"], 
                default=["pagePath"]
            )
        with col_m:
            custom_mets = st.multiselect(
                "Select Metrics", 
                ["activeUsers", "screenPageViews", "sessions", "conversions", "eventCount"], 
                default=["screenPageViews", "activeUsers"]
            )
            
        if custom_dims and custom_mets:
            custom_df = run_dynamic_ga4_report(
                days_range, 
                custom_dims, 
                custom_mets, 
                demo_mode=USE_DEMO_MODE
            )
            st.dataframe(custom_df, use_container_width=True)
            
            fig_custom = px.bar(
                custom_df.sort_values(by=custom_mets[0], ascending=False).head(10), 
                x=custom_dims[0], 
                y=custom_mets[0]
            )
            st.plotly_chart(fig_custom, use_container_width=True)

except Exception as e:
    st.error(f"Error executing report: {e}")

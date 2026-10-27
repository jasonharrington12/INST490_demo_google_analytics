import os
import pandas as pd
import numpy as np
import plotly.express as px
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
    page_title="GA4 Analytics Studio",
    page_icon="📊",
    layout="wide",
)

GA4_PROPERTY_ID = "153293282"  # Replace with your 9-digit numeric GA4 Property ID
USE_DEMO_MODE = False  # Set to True to force synthetic mock data without API credentials

# Custom CSS Styling
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
        # Fall back gracefully to demo mode if no credentials exist
        return None

client = get_ga4_client()

# ==============================================================================
# GA4 UI NAVIGATION & API SCHEMA MAPPING
# ==============================================================================
GA4_NAVIGATION = {
    "Reports snapshot": {
        "dimensions": ["date"],
        "metrics": ["activeUsers", "screenPageViews", "conversions"],
        "primary_metric": "activeUsers",
        "chart_type": "line"
    },
    "Acquisition": {
        "User acquisition": {
            "dimensions": ["firstUserPrimaryChannelGroup"],
            "metrics": ["newUsers", "sessions", "conversions"],
            "primary_metric": "newUsers",
            "chart_type": "bar"
        },
        "Traffic acquisition": {
            "dimensions": ["sessionDefaultChannelGroup"],
            "metrics": ["sessions", "activeUsers", "conversions"],
            "primary_metric": "sessions",
            "chart_type": "pie"
        }
    },
    "Engagement": {
        "Pages and screens": {
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
        }
    },
    "Monetization": {
        "Ecommerce purchases": {
            "dimensions": ["itemName"],
            "metrics": ["itemRevenue", "itemsPurchased", "itemsViewed"],
            "primary_metric": "itemRevenue",
            "chart_type": "bar"
        }
    },
    "Demographics": {
        "Demographic details": {
            "dimensions": ["country"],
            "metrics": ["activeUsers", "sessions", "conversions"],
            "primary_metric": "activeUsers",
            "chart_type": "map"
        }
    },
    "Tech": {
        "Tech details": {
            "dimensions": ["deviceCategory"],
            "metrics": ["activeUsers", "sessions"],
            "primary_metric": "activeUsers",
            "chart_type": "pie"
        }
    }
}

# ==============================================================================
# SIDEBAR NAVIGATION CONTROLS
# ==============================================================================
st.sidebar.title("📌 Analytics Navigation")

# Primary Category Selectbox
category = st.sidebar.selectbox("Category", list(GA4_NAVIGATION.keys()) + ["Custom Query Builder"])

# Handle Nested Sub-Tabs
if category == "Reports snapshot":
    selected_report_config = GA4_NAVIGATION["Reports snapshot"]
    report_title = "Reports snapshot"
elif category == "Custom Query Builder":
    selected_report_config = None
    report_title = "Custom Query Builder"
else:
    sub_tab = st.sidebar.radio("Report Tab", list(GA4_NAVIGATION[category].keys()))
    selected_report_config = GA4_NAVIGATION[category][sub_tab]
    report_title = sub_tab

# Dynamic Date Slider
days_range = st.sidebar.slider("Date Window (Days)", 7, 90, 28)

# Optional Channel Filters
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
@st.cache_data(ttl=3600)
def run_dynamic_ga4_report(days, dim_names, metric_names, demo_mode=False):
    # Fall back to synthetic data if client is None or demo_mode is True
    if demo_mode or client is None:
        np.random.seed(int(days))
        rows = []
        sample_countries = [
            "United States", "India", "United Kingdom", "Canada", 
            "Germany", "France", "Japan", "Australia", "Brazil", "Mexico"
        ]
        
        for i in range(10):
            d_vals = []
            for d in dim_names:
                if "country" in d:
                    d_vals.append(sample_countries[i % len(sample_countries)])
                elif "Path" in d or "Name" in d:
                    d_vals.append(f"/page-{i+1}")
                elif "date" in d:
                    d_vals.append(pd.Timestamp.today().strftime("%Y-%m-%d"))
                else:
                    d_vals.append("Organic Search")
                    
            m_vals = [int(np.random.randint(50, 300) * (days / 7)) for _ in metric_names]
            rows.append(d_vals + m_vals)
            
        return pd.DataFrame(rows, columns=dim_names + metric_names)

    # Real GA4 Data API Call
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
# DASHBOARD RENDERING ENGINE
# ==============================================================================
st.title(f"📊 {report_title}")

try:
    if category != "Custom Query Builder":
        df = run_dynamic_ga4_report(
            days_range, 
            selected_report_config["dimensions"], 
            selected_report_config["metrics"], 
            demo_mode=USE_DEMO_MODE
        )
        
        # Apply Channel Filter if the primary dimension is channel-based
        primary_dim = selected_report_config["dimensions"][0]
        if primary_dim in ["firstUserPrimaryChannelGroup", "sessionDefaultChannelGroup"]:
            if traffic_segments:
                df = df[df[primary_dim].isin(traffic_segments)]
            else:
                df = df.iloc[0:0]

        # Metric KPI Summary Cards
        cols = st.columns(len(selected_report_config["metrics"]))
        for idx, m in enumerate(selected_report_config["metrics"]):
            total_val = df[m].sum() if not df.empty else 0
            cols[idx].metric(m, f"{total_val:,.2f}" if isinstance(total_val, float) else f"{total_val:,}")
            
        st.markdown("---")
        
        col_chart, col_table = st.columns([1.5, 1])
        
        # Dynamic Visualizations
        with col_chart:
            st.subheader("Visual Analysis")
            if df.empty:
                st.info("No data available for the selected filters.")
            elif selected_report_config["chart_type"] == "line":
                fig = px.line(df, x=primary_dim, y=selected_report_config["primary_metric"])
                st.plotly_chart(fig, use_container_width=True)
            elif selected_report_config["chart_type"] == "pie":
                fig = px.pie(df, names=primary_dim, values=selected_report_config["primary_metric"], hole=0.4)
                st.plotly_chart(fig, use_container_width=True)
            elif selected_report_config["chart_type"] == "map":
                fig = px.choropleth(df, locations=primary_dim, locationmode="country names", color=selected_report_config["primary_metric"])
                st.plotly_chart(fig, use_container_width=True)
            else:
                sorted_df = df.sort_values(by=selected_report_config["primary_metric"], ascending=False).head(10)
                fig = px.bar(sorted_df, x=selected_report_config["primary_metric"], y=primary_dim, orientation="h")
                fig.update_layout(yaxis=dict(autorange="reversed"))
                st.plotly_chart(fig, use_container_width=True)
            
        # Raw Data Table
        with col_table:
            st.subheader("Raw Data Table")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # Custom Query Builder View
    else:
        st.subheader("🛠️ Custom Query Builder")
        
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

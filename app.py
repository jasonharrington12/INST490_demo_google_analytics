import os
import pandas as pd
import plotly.express as px
import streamlit as st
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest

# ==============================================================================
# CONFIGURATION
# ==============================================================================
st.set_page_config(page_title="Universal GA4 Analytics Studio", page_icon="📊", layout="wide")
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"
GA4_PROPERTY_ID = "153293282"  # Update with your property ID

client = BetaAnalyticsDataClient()

# ==============================================================================
# REPORT DEFINITIONS (Add any GA4 report here)
# ==============================================================================
REPORTS_CONFIG = {
    "Acquisition (User Channels)": {
        "dimensions": ["firstUserPrimaryChannelGroup"],
        "metrics": ["newUsers", "sessions", "conversions"],
        "primary_metric": "newUsers",
        "chart_type": "bar"
    },
    "Traffic Acquisition (Session Channels)": {
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
    "Monetization / Ecommerce": {
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
# SIDEBAR NAVIGATION
# ==============================================================================
st.sidebar.title("📌 GA4 Reports Navigation")

# 1. Choose Report Type
report_type = st.sidebar.radio("Select Pre-built Report", list(REPORTS_CONFIG.keys()) + ["Custom Query Builder"])

# 2. Date Range Picker
days_range = st.sidebar.slider("Date Window (Days)", 7, 90, 28)

# ==============================================================================
# UNIVERSAL REPORT ENGINE FUNCTION
# ==============================================================================
def run_dynamic_ga4_report(dim_names, metric_names, days):
    request = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[Dimension(name=d) for d in dim_names],
        metrics=[Metric(name=m) for m in metric_names],
        date_ranges=[DateRange(start_date=f"{days}daysAgo", end_date="today")],
    )
    response = client.run_report(request)
    
    rows = []
    for row in response.rows:
        dims = [d.value for d in row.dimension_values]
        mets = [m.value for m in row.metric_values]
        rows.append(dims + mets)
        
    df = pd.DataFrame(rows, columns=dim_names + metric_names)
    
    # Convert metric columns to numeric
    for m in metric_names:
        df[m] = pd.to_numeric(df[m])
        
    return df

# ==============================================================================
# REPORT RENDERING
# ==============================================================================
st.title(f"📊 {report_type}")

try:
    if report_type != "Custom Query Builder":
        config = REPORTS_CONFIG[report_type]
        df = run_dynamic_ga4_report(config["dimensions"], config["metrics"], days_range)
        
        # Metric Summary Cards
        cols = st.columns(len(config["metrics"]))
        for idx, m in enumerate(config["metrics"]):
            total_val = df[m].sum()
            cols[idx].metric(m, f"{total_val:,.2f}" if isinstance(total_val, float) else f"{total_val:,}")
            
        st.markdown("---")
        
        col_chart, col_table = st.columns([1.5, 1])
        
        # Dynamic Visualization
        with col_chart:
            st.subheader("Visual Analysis")
            if config["chart_type"] == "pie":
                fig = px.pie(df, names=config["dimensions"][0], values=config["primary_metric"], hole=0.4)
            elif config["chart_type"] == "map":
                fig = px.choropleth(df, locations=config["dimensions"][0], locationmode="country names", color=config["primary_metric"])
            else:
                sorted_df = df.sort_values(by=config["primary_metric"], ascending=False).head(10)
                fig = px.bar(sorted_df, x=config["primary_metric"], y=config["dimensions"][0], orientation="h")
                fig.update_layout(yaxis=dict(autorange="reversed"))
                
            st.plotly_chart(fig, use_container_width=True)
            
        # Data Table
        with col_table:
            st.subheader("Raw Data Table")
            st.dataframe(df, use_container_width=True, hide_index=True)

    # Custom Query Builder (Allow users to select ANY dimension or metric)
    else:
        st.subheader("🛠️ Build Your Own Custom GA4 Query")
        
        col_d, col_m = st.columns(2)
        with col_d:
            custom_dims = st.multiselect("Dimensions", ["pagePath", "sessionDefaultChannelGroup", "country", "deviceCategory", "eventName"], default=["pagePath"])
        with col_m:
            custom_mets = st.multiselect("Metrics", ["activeUsers", "screenPageViews", "sessions", "conversions", "eventCount"], default=["screenPageViews", "activeUsers"])
            
        if custom_dims and custom_mets:
            custom_df = run_dynamic_ga4_report(custom_dims, custom_mets, days_range)
            st.dataframe(custom_df, use_container_width=True)
            
            # Auto-generate chart on first selected dimension and metric
            fig_custom = px.bar(custom_df.sort_values(by=custom_mets[0], ascending=False).head(10), x=custom_dims[0], y=custom_mets[0])
            st.plotly_chart(fig_custom, use_container_width=True)

except Exception as e:
    st.error(f"Error executing report: {e}")

except Exception as e:
    st.error(f"Error loading dashboard data: {e}")
    st.info("Ensure credentials.json is present locally or Streamlit Secrets are configured properly.")

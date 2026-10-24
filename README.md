# Executive GA4 Analytics Dashboard

A customized, real-time web analytics dashboard built with Python, Streamlit, and the Google Analytics Data API (v1beta). Designed to distil complex GA4 property data into actionable business insights.

## Features
- **Rolling Date Ranges:** Dynamic rolling window calculation (7 to 90 days).
- **Interactive Channel Filtering:** Single-click "Select All" and "Clear All" toggles for traffic sources.
- **Conversion Funnel Visualizations:** Multi-stage funnel analysis using Plotly.
- **API Cache Pipeline:** 1-hour automatic data caching to stay within Google Analytics quota limits.

## Local Setup Instructions

1. Clone or extract this repository.

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Add GA4 Credentials:
   - Save your Google Cloud Service Account JSON key in the root directory as `credentials.json`.
   - Update `GA4_PROPERTY_ID` in `app.py` with your numeric GA4 property ID.

4. Run the app:
   ```bash
   streamlit run app.py
   ```

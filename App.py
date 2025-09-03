import streamlit as st
import pandas as pd
import numpy as np
import ast

# File upload
uploaded_file = st.file_uploader(r"C:\Users\qasim\Downloads\user_exports_02_09_2025.xlsx", type=["xlsx"])
if uploaded_file:
    # Data loading and cleaning
    campaign = pd.read_excel(uploaded_file)
    campaign.columns = campaign.columns.astype(str).str.lower()

    # UTM parsing function
    def parse_utm(x):
        if pd.isna(x):
            return None
        if isinstance(x, dict):
            return x
        if isinstance(x, str):
            try:
                return ast.literal_eval(x)
            except Exception:
                return None
        return None

    campaign["utm_hit"] = campaign["utm_hit"].apply(parse_utm)
    utm_df = pd.json_normalize(campaign["utm_hit"]).add_prefix("utm_hit_")
    campaign_con = pd.concat([campaign.drop(columns=["utm_hit"]), utm_df], axis=1)

    # Clean columns
    campaign_con.columns = campaign_con.columns.str.lower().str.replace(".", "_")
    for col in ["utm_hit_utmcampaign", "utm_hit_utmsource"]:
        if col in campaign_con:
            campaign_con[col] = campaign_con[col].astype(str).str.strip().fillna("UNKNOWN")

    # Build filter options
    sources = ["All"] + sorted(campaign_con["utm_hit_utmsource"].replace(np.nan, "UNKNOWN").unique())
    campaigns = ["All"] + sorted(campaign_con["utm_hit_utmcampaign"].replace(np.nan, "UNKNOWN").unique())

    # Streamlit filters
    selected_source = st.selectbox("Select UTM Source", sources)
    selected_campaign = st.selectbox("Select UTM Campaign", campaigns)
    deposit_min, deposit_max = st.slider(
        "Deposit Total Range",
        float(campaign_con["deposits_total_in_usd"].min()),
        float(campaign_con["deposits_total_in_usd"].max()),
        (float(campaign_con["deposits_total_in_usd"].min()), float(campaign_con["deposits_total_in_usd"].max())),
    )

    # Apply filters
    df_filtered = campaign_con[
        (campaign_con["deposits_total_in_usd"] >= deposit_min)
        & (campaign_con["deposits_total_in_usd"] <= deposit_max)
    ]
    if selected_source != "All":
        df_filtered = df_filtered[df_filtered["utm_hit_utmsource"] == selected_source]
    if selected_campaign != "All":
        df_filtered = df_filtered[df_filtered["utm_hit_utmcampaign"] == selected_campaign]

    # Aggregation
    grouped = df_filtered.groupby(
        ["utm_hit_utmsource", "utm_hit_utmcampaign"], as_index=False
    ).agg(
        total_leads=("utm_hit_utmcampaign", "count"),
        total_deposits=("deposits_total_in_usd", "sum"),
    )

    st.write("Filtered Results", grouped)
    st.write("Detailed Data", df_filtered)

    # Option to download filtered results
    as_excel = st.download_button(
        label="Download Filtered Data as CSV",
        data=df_filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_campaign_data.csv",
        mime="text/csv"
    )

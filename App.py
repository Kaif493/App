import streamlit as st
import pandas as pd
import numpy as np
import ast
import io

uploaded_file = st.file_uploader("Upload campaign Excel file", type=["xlsx"])

if uploaded_file:
    campaign = pd.read_excel(uploaded_file)
    campaign.columns = campaign.columns.astype(str).str.lower()

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

    campaign_con.columns = campaign_con.columns.str.lower().str.replace(".", "_")
    for col in ["utm_hit_utmcampaign", "utm_hit_utmsource"]:
        if col in campaign_con:
            campaign_con[col] = campaign_con[col].astype(str).str.strip().replace("nan", "UNKNOWN")

    # -------------------------
    # UTM filters
    # -------------------------
    sources = ["All"] + sorted(campaign_con["utm_hit_utmsource"].replace(np.nan, "UNKNOWN").unique())
    campaigns = ["All"] + sorted(campaign_con["utm_hit_utmcampaign"].replace(np.nan, "UNKNOWN").unique())

    selected_source = st.selectbox("Select UTM Source", sources)
    selected_campaign = st.selectbox("Select UTM Campaign", campaigns)

    # -------------------------
    # Deposit range filter
    # -------------------------
    deposit_min, deposit_max = st.slider(
        "Deposit Total Range",
        float(campaign_con["deposits_total_in_usd"].min()),
        float(campaign_con["deposits_total_in_usd"].max()),
        (float(campaign_con["deposits_total_in_usd"].min()), float(campaign_con["deposits_total_in_usd"].max())),
    )

    # -------------------------
    # Date filter (multi-select)
    # -------------------------
    if "date" in campaign_con.columns:
        campaign_con["date"] = pd.to_datetime(campaign_con["joined"], errors="coerce").dt.date
        available_dates = sorted(campaign_con["date"].dropna().unique())
        selected_dates = st.multiselect(
            "Select Dates",
            options=available_dates,
            default=available_dates  # select all by default
        )
    else:
        selected_dates = []

    # -------------------------
    # Apply Filters
    # -------------------------
    df_filtered = campaign_con[
        (campaign_con["deposits_total_in_usd"] >= deposit_min)
        & (campaign_con["deposits_total_in_usd"] <= deposit_max)
    ]
    if selected_source != "All":
        df_filtered = df_filtered[df_filtered["utm_hit_utmsource"] == selected_source]
    if selected_campaign != "All":
        df_filtered = df_filtered[df_filtered["utm_hit_utmcampaign"] == selected_campaign]
    if selected_dates:
        df_filtered = df_filtered[df_filtered["date"].isin(selected_dates)]

    # -------------------------
    # Grouped Summary (with Date)
    # -------------------------
    grouped = df_filtered.groupby(
        ["date", "utm_hit_utmsource", "utm_hit_utmcampaign"], as_index=False
    ).agg(
        total_leads=("utm_hit_utmcampaign", "count"),
        total_deposits=("deposits_total_in_usd", "sum"),
    )

    # Grand Total
    grand_total = pd.DataFrame({
        "date": ["TOTAL"],
        "utm_hit_utmsource": ["TOTAL"],
        "utm_hit_utmcampaign": ["TOTAL"],
        "total_leads": [grouped["total_leads"].sum()],
        "total_deposits": [grouped["total_deposits"].sum()]
    })

    utm_with_total = pd.concat([grouped, grand_total], ignore_index=True)

    # -------------------------
    # Display
    # -------------------------
    st.write("Filtered Summary:", utm_with_total)
    st.write("Filtered Detailed Data:", df_filtered)

    # -------------------------
    # Save Excel
    # -------------------------
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_filtered.to_excel(writer, sheet_name="filtered_campaign_data", index=False)
        utm_with_total.to_excel(writer, sheet_name="summary_data", index=False)
    output.seek(0)

    st.download_button(
        label="Download Report as Excel",
        data=output.getvalue(),
        file_name="streamlit_report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )




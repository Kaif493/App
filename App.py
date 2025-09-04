import streamlit as st
import pandas as pd
import numpy as np
import ast
import io

uploaded_file = st.file_uploader("Upload campaign Excel file", type=["xlsx"])

if uploaded_file:
    campaign = pd.read_excel(uploaded_file)
    campaign.columns = campaign.columns.astype(str).str.lower()

    # -------------------------
    # Parse UTM JSON column
    # -------------------------
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
            campaign_con[col] = (
                campaign_con[col]
                .astype(str)
                .str.strip()
                .replace("nan", "UNKNOWN")
            )

    # -------------------------
    # Ensure Date Column from "joined"
    # -------------------------
    if "joined" in campaign_con.columns:
        campaign_con["date"] = pd.to_datetime(
            campaign_con["joined"], errors="coerce"
        ).dt.date
    else:
        campaign_con["date"] = pd.NaT

    # -------------------------
    # UTM filters (multi-select with Select All)
    # -------------------------
    sources = sorted(
        campaign_con["utm_hit_utmsource"].replace(np.nan, "UNKNOWN").unique()
    )
    campaigns = sorted(
        campaign_con["utm_hit_utmcampaign"].replace(np.nan, "UNKNOWN").unique()
    )

    # UTM Source Filter
    select_all_sources = st.checkbox("Select All Sources", value=True)
    if select_all_sources:
        selected_sources = st.multiselect(
            "Select UTM Source(s)", options=sources, default=sources
        )
    else:
        selected_sources = st.multiselect(
            "Select UTM Source(s)", options=sources, default=[]
        )

    # UTM Campaign Filter
    select_all_campaigns = st.checkbox("Select All Campaigns", value=True)
    if select_all_campaigns:
        selected_campaigns = st.multiselect(
            "Select UTM Campaign(s)", options=campaigns, default=campaigns
        )
    else:
        selected_campaigns = st.multiselect(
            "Select UTM Campaign(s)", options=campaigns, default=[]
        )

    # -------------------------
    # Deposit range filter
    # -------------------------
    deposit_min, deposit_max = st.slider(
        "Deposit Total Range",
        float(campaign_con["deposits_total_in_usd"].min()),
        float(campaign_con["deposits_total_in_usd"].max()),
        (
            float(campaign_con["deposits_total_in_usd"].min()),
            float(campaign_con["deposits_total_in_usd"].max()),
        ),
    )

    # -------------------------
    # Date filter (multi-select with Select All)
    # -------------------------
    available_dates = sorted(campaign_con["date"].dropna().unique())
    select_all_dates = st.checkbox("Select All Dates", value=True)
    if select_all_dates:
        selected_dates = st.multiselect(
            "Select Dates", options=available_dates, default=available_dates
        )
    else:
        selected_dates = st.multiselect(
            "Select Dates", options=available_dates, default=[]
        )

    # -------------------------
    # Apply Filters
    # -------------------------
    df_filtered = campaign_con[
        (campaign_con["deposits_total_in_usd"] >= deposit_min)
        & (campaign_con["deposits_total_in_usd"] <= deposit_max)
    ]
    if selected_sources:
        df_filtered = df_filtered[df_filtered["utm_hit_utmsource"].isin(selected_sources)]
    if selected_campaigns:
        df_filtered = df_filtered[df_filtered["utm_hit_utmcampaign"].isin(selected_campaigns)]
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

    # Grand Total row
    grand_total = pd.DataFrame({
        "date": ["TOTAL"],
        "utm_hit_utmsource": ["TOTAL"],
        "utm_hit_utmcampaign": ["TOTAL"],
        "total_leads": [grouped["total_leads"].sum()],
        "total_deposits": [grouped["total_deposits"].sum()],
    })

    utm_with_total = pd.concat([grouped, grand_total], ignore_index=True)

    # -------------------------
    # Styling: Bold TOTAL row
    # -------------------------
    def highlight_total(row):
        return ["font-weight: bold; background-color: #2c2c2c; color: white;"
                if row["date"] == "TOTAL" else "" for _ in row]

    styled_summary = utm_with_total.style.apply(highlight_total, axis=1)

    # -------------------------
    # Display
    # -------------------------
    st.write("### Filtered Summary")
    st.dataframe(styled_summary, use_container_width=True)

    st.write("### Filtered Detailed Data")
    st.dataframe(df_filtered, use_container_width=True)

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
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

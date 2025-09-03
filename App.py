import streamlit as st
import pandas as pd
import numpy as np
import ast
import io
import plotly.express as px

# ----------------- Page Setup -----------------
st.set_page_config(
    page_title="Campaign Analysis Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Campaign Analysis Dashboard")
st.markdown("Upload your campaign Excel file, filter by UTM Source/Campaign, and download cleaned reports easily 🚀")

# ----------------- File Upload -----------------
uploaded_file = st.file_uploader("📂 Upload campaign Excel file", type=["xlsx"])

if uploaded_file:
    campaign = pd.read_excel(uploaded_file)
    campaign.columns = campaign.columns.astype(str).str.lower()

    # ----------------- Parsing Function -----------------
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

    # ----------------- Data Transformation -----------------
    campaign["utm_hit"] = campaign["utm_hit"].apply(parse_utm)
    utm_df = pd.json_normalize(campaign["utm_hit"]).add_prefix("utm_hit_")
    campaign_con = pd.concat([campaign.drop(columns=["utm_hit"]), utm_df], axis=1)

    # Clean columns
    campaign_con.columns = campaign_con.columns.str.lower().str.replace(".", "_")
    for col in ["utm_hit_utmcampaign", "utm_hit_utmsource"]:
        if col in campaign_con:
            campaign_con[col] = campaign_con[col].astype(str).str.strip().replace("nan", "UNKNOWN")

    sources = ["All"] + sorted(campaign_con["utm_hit_utmsource"].replace(np.nan, "UNKNOWN").unique())
    campaigns = ["All"] + sorted(campaign_con["utm_hit_utmcampaign"].replace(np.nan, "UNKNOWN").unique())

    # ----------------- Filters -----------------
    col1, col2 = st.columns(2)
    with col1:
        selected_source = st.selectbox("Select UTM Source", sources)
    with col2:
        selected_campaign = st.selectbox("Select UTM Campaign", campaigns)

    deposit_min, deposit_max = st.slider(
        "💰 Deposit Total Range",
        float(campaign_con["deposits_total_in_usd"].min()),
        float(campaign_con["deposits_total_in_usd"].max()),
        (float(campaign_con["deposits_total_in_usd"].min()), float(campaign_con["deposits_total_in_usd"].max())),
    )

    # ----------------- Filtering Data -----------------
    df_filtered = campaign_con[
        (campaign_con["deposits_total_in_usd"] >= deposit_min)
        & (campaign_con["deposits_total_in_usd"] <= deposit_max)
    ]
    if selected_source != "All":
        df_filtered = df_filtered[df_filtered["utm_hit_utmsource"] == selected_source]
    if selected_campaign != "All":
        df_filtered = df_filtered[df_filtered["utm_hit_utmcampaign"] == selected_campaign]

    # ----------------- Grouped Summary -----------------
    grouped = df_filtered.groupby(
        ["utm_hit_utmsource", "utm_hit_utmcampaign"], as_index=False
    ).agg(
        total_leads=("utm_hit_utmcampaign", "count"),
        total_deposits=("deposits_total_in_usd", "sum"),
    )

    # Grand Total Row
    grand_total = pd.DataFrame({
        "utm_hit_utmsource": ["TOTAL"],
        "utm_hit_utmcampaign": ["TOTAL"],
        "total_leads": [grouped["total_leads"].sum()],
        "total_deposits": [grouped["total_deposits"].sum()]
    })

    utm_with_total = pd.concat([grouped, grand_total], ignore_index=True)

    # ----------------- Tabs for Output -----------------
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Summary", "📋 Detailed Data", "📈 Charts", "⬇️ Download"])

    with tab1:
        st.subheader("📊 Filtered Summary")
        st.dataframe(utm_with_total, use_container_width=True)

    with tab2:
        st.subheader("📋 Filtered Detailed Data")
        st.dataframe(df_filtered, use_container_width=True)

    with tab3:
        st.subheader("📈 Deposits by Campaign & Source")
        if not grouped.empty:
            fig = px.bar(
                grouped,
                x="utm_hit_utmcampaign",
                y="total_deposits",
                color="utm_hit_utmsource",
                title="Deposits by Campaign & Source"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("⚠️ No data available for the selected filters.")

    with tab4:
        # Write Excel to BytesIO buffer
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df_filtered.to_excel(writer, sheet_name="filtered_campaign_data", index=False)
            utm_with_total.to_excel(writer, sheet_name="summary_data", index=False)
        output.seek(0)

        st.download_button(
            label="⬇️ Download Report as Excel",
            data=output.getvalue(),
            file_name="streamlit_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ----------------- Styling -----------------
st.markdown("""
<style>
    .stApp {
        background-color: #f8f9fa;
    }
    h1 {
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)


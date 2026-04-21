import streamlit as st
import pandas as pd
import numpy as np
import re

st.title("Send Time Optimizer")

# -----------------------------
# 1. FILE UPLOAD
# -----------------------------
file = st.file_uploader("Upload CSV")

if file is not None:

    # -----------------------------
    # 2. LOAD DATA
    # -----------------------------
    df = pd.read_csv(file)

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # -----------------------------
    # 3. FIX NUMERIC COLUMNS
    # -----------------------------
    numeric_cols = [
        'sent', 'delivered', 'total_opens', 'unique_opens',
        'unique_clicks', 'total_clicks', 'opt_outs'
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df['base'] = np.where(df['delivered'] > 0, df['delivered'], df['sent'])

    # -----------------------------
    # 4. REMOVE TEST / PROOF DATA
    # -----------------------------
    def is_test(row):
        text = f"{row.get('name','')} {row.get('campaign','')}".lower()

        if any(p in text for p in ["test", "proof"]) and row['sent'] <= 4:
            return True
        return False

    df = df[~df.apply(is_test, axis=1)]

    # -----------------------------
    # 5. SIDEBAR FILTERS (ADD HERE)
    # -----------------------------
    st.sidebar.header("Filters")

    # Day filter
    if 'day_of_week' in df.columns:
        day = st.sidebar.selectbox(
            "Day of Week",
            ["All"] + sorted(df['day_of_week'].dropna().unique())
        )

        if day != "All":
            df = df[df['day_of_week'].str.lower() == day.lower()]

    # Segment filter
    segment = st.sidebar.text_input("Segment (EN, TR, OTA, TÜRSAB...)")

    if segment:
        df = df[
            df['name'].str.contains(segment, case=False, na=False) |
            df['campaign'].str.contains(segment, case=False, na=False)
        ]

    # -----------------------------
    # 6. WEIGHTS (ADD HERE)
    # -----------------------------
    st.sidebar.header("Weights")

    w_open = st.sidebar.slider("Open Rate", 0.0, 1.0, 0.4)
    w_ctr = st.sidebar.slider("CTR", 0.0, 1.0, 0.4)
    w_opt = st.sidebar.slider("Opt-out Penalty", 0.0, 1.0, 0.2)

    # -----------------------------
    # 7. GROUP & METRICS
    # -----------------------------
    if 'hour_interval' not in df.columns:
        st.error("Missing 'hour_interval' column")
        st.stop()

    agg = df.groupby('hour_interval').agg({
        'base': 'sum',
        'unique_opens': 'sum',
        'unique_clicks': 'sum',
        'opt_outs': 'sum'
    }).reset_index()

    agg['open_rate'] = agg['unique_opens'] / agg['base']
    agg['ctr'] = agg['unique_clicks'] / agg['base']
    agg['opt_out_rate'] = agg['opt_outs'] / agg['base']

    agg = agg.fillna(0)

    # -----------------------------
    # 8. SCORE
    # -----------------------------
    agg['score'] = (
        agg['open_rate'] * w_open +
        agg['ctr'] * w_ctr -
        agg['opt_out_rate'] * w_opt
    ) * np.log1p(agg['base'])

    agg = agg.sort_values("score", ascending=False)

    # -----------------------------
    # 9. OUTPUT
    # -----------------------------
    st.subheader("Best Send Times")

    st.dataframe(agg)

    st.bar_chart(agg.set_index("hour_interval")["score"])

    # -----------------------------
    # 10. INSIGHT (WHY THIS WORKS)
    # -----------------------------
    top = agg.iloc[0]
    st.success(f"Best time is: {top['hour_interval']} (Score: {top['score']:.2f})")

    st.subheader("Why this hour?")

    st.write(f"""
    - Open Rate: {top['open_rate']:.2%}
    - CTR: {top['ctr']:.2%}
    - Opt-out Rate: {top['opt_out_rate']:.2%}
    - Based on {int(top['base'])} sends
    """)

    # -----------------------------
    # 11. HEATMAP (ADD LAST)
    # -----------------------------
    if 'day_of_week' in df.columns:

        pivot = df.groupby(['day_of_week', 'hour_interval']).agg({
            'base': 'sum',
            'unique_clicks': 'sum'
        }).reset_index()

        pivot['ctr'] = pivot['unique_clicks'] / pivot['base']

        heatmap = pivot.pivot_table(
            index='day_of_week',
            columns='hour_interval',
            values='ctr'
        )

        st.subheader("Heatmap (CTR)")
        st.dataframe(heatmap)

else:
    st.info("⬆️ Upload a CSV file to start")

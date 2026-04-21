import streamlit as st
import pandas as pd
import numpy as np

st.title("📊 Send Time Optimizer")

# -----------------------------
# 1. FILE UPLOAD (SAFE)
# -----------------------------
file = st.file_uploader("Upload CSV")

if file is not None:

    df = pd.read_csv(file)

    # -----------------------------
    # 2. CLEAN COLUMN NAMES
    # -----------------------------
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

    # -----------------------------
    # 3. FORCE NUMERIC TYPES (IMPORTANT FIX)
    # -----------------------------
    numeric_cols = [
        'sent', 'delivered', 'total_opens', 'unique_opens',
        'unique_clicks', 'total_clicks', 'opt_outs'
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # -----------------------------
    # 4. BASE CALCULATION
    # -----------------------------
    df['base'] = np.where(df['delivered'] > 0, df['delivered'], df['sent'])
    df['base'] = pd.to_numeric(df['base'], errors='coerce').fillna(0)

    # -----------------------------
    # 5. SIMPLE TEST FILTER
    # -----------------------------
    if 'name' in df.columns:
        df = df[~df['name'].str.lower().str.contains("test", na=False)]

    # -----------------------------
    # 6. GROUP BY HOUR
    # -----------------------------
    group_col = 'hour_interval' if 'hour_interval' in df.columns else None

    if group_col is None:
        st.error("Missing 'hour_interval' column in file")
        st.stop()

    agg = df.groupby(group_col).agg({
        'base': 'sum',
        'unique_opens': 'sum',
        'unique_clicks': 'sum',
        'opt_outs': 'sum'
    }).reset_index()

    # -----------------------------
    # 7. METRICS
    # -----------------------------
    agg['open_rate'] = agg['unique_opens'] / agg['base']
    agg['ctr'] = agg['unique_clicks'] / agg['base']
    agg['opt_out_rate'] = agg['opt_outs'] / agg['base']

    agg = agg.fillna(0)

    # -----------------------------
    # 8. SCORE (SIMPLE VERSION)
    # -----------------------------
    agg['score'] = (
        agg['open_rate'] * 0.4 +
        agg['ctr'] * 0.4 -
        agg['opt_out_rate'] * 0.2
    ) * np.log1p(agg['base'])

    agg = agg.sort_values("score", ascending=False)

    # -----------------------------
    # 9. OUTPUT
    # -----------------------------
    st.subheader("🏆 Best Send Times")

    st.dataframe(agg)

    st.bar_chart(agg.set_index(group_col)['score'])

    # -----------------------------
    # 10. TOP RECOMMENDATION
    # -----------------------------
    top = agg.iloc[0]

    st.success(
        f"Best hour: {top[group_col]} | Score: {top['score']:.2f}"
    )

else:
    st.info("⬆️ Upload a CSV file to start analysis")
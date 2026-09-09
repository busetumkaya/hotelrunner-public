'''import streamlit as st
import pandas as pd
import numpy as np
import re
import plotly.express as px

# -----------------------------
# SEGMENT RULES
# -----------------------------
SEGMENT_RULES = {
    "EN": [
        r"\(en\)",
        r"\ben\b",
        r"en users",
        r"en leads",
        r"- en",
        r"-en"
    ],

    "TR": [
        r"\(tr\)",
        r"\btr\b",
        r"tr users",
        r"- tr",
        r"-tr"
    ],
    
        "OTAs": [
        r"\bconnect\b",
        r"- \bconnect\b",
        r"-\bconnect\b",
        r"TÜRSAB",
        r"- TÜRSAB",
        r"-TÜRSAB",
        r"Ratefor",
        r"- Ratefor",
        r"-Ratefor"
    ],

        "Leads": [
        r"leads",
        r"- leads",
        r"-leads",
        r"\(leads\)"
    ],

        "Users": [
        r"users",
        r"- users",
        r"-users",
        r"\(users\)"
    ]
}

def match_segment(text, patterns):
    text = str(text).lower()

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )

st.title("Send Time Optimizer")

# -----------------------------
# FILE UPLOAD
# -----------------------------
file = st.file_uploader("Upload CSV")

if file is None:
    st.info("⬆️ Upload a CSV file to start analysis")
    st.stop()

# -----------------------------
# LOAD
# -----------------------------
df = pd.read_csv(file)
df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")

# -----------------------------
# CLEAN NUMERIC
# -----------------------------
numeric_cols = [
    'sent', 'delivered', 'total_opens', 'unique_opens',
    'unique_clicks', 'total_clicks', 'opt_outs'
]

for col in numeric_cols:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

df['base'] = np.where(df['delivered'] > 0, df['delivered'], df['sent'])
df = df[df['base'] > 0]

# -----------------------------
# CLEAN RATE COLUMNS
# -----------------------------
rate_cols = [
    'open_rate',
    'unique_ctr',
    'opt_out_rate'
]

for col in rate_cols:

    if col in df.columns:

        df[col] = (
            df[col]
            .astype(str)
            .str.replace('%', '', regex=False)
            .str.replace(',', '.', regex=False)
            .str.strip()
        )

        df[col] = pd.to_numeric(
            df[col],
            errors='coerce'
        )

        df[col] = df[col].fillna(0) / 100

# -----------------------------
# TEST FILTER
# -----------------------------
def is_test(row):
    text = f"{row.get('name','')} {row.get('campaign','')}".lower()
    return any(p in text for p in ["test", "proof"]) and row['sent'] <= 4

df = df[~df.apply(is_test, axis=1)]

# -----------------------------
# FILTERS
# -----------------------------
st.sidebar.header("Filters")

# -----------------------------
# DAY FILTER
# -----------------------------
DAY_ORDER = [
    "Mon",
    "Tue",
    "Wed",
    "Thu",
    "Fri",
    "Sat",
    "Sun"
]

if 'day_of_week' in df.columns:

    df['day_of_week'] = (
        df['day_of_week']
        .astype(str)
        .str.strip()
        .str.title()
    )

    existing_days = list(
        df['day_of_week']
        .dropna()
        .astype(str)
        .unique()
    )

    available_days = [
        d for d in DAY_ORDER
        if d in existing_days
    ]

    selected_days = st.sidebar.multiselect(
        "Day of Week",
        options=available_days,
        default=[]
    )

    if len(selected_days) > 0:

        df = df[
            df['day_of_week'].isin(selected_days)
        ]

selected_segments = st.sidebar.multiselect(
    "Segments",
    ["EN", "TR", "OTAs", "Hoteliers", "Leads", "Users"]
)

if selected_segments:

    combined_mask = pd.Series(False, index=df.index)

    for segment in selected_segments:

        # normal regex-rule segments
        if segment in SEGMENT_RULES:

            patterns = SEGMENT_RULES[segment]

            mask = (
                df['name'].apply(lambda x: match_segment(x, patterns)) |
                df['campaign'].apply(lambda x: match_segment(x, patterns))
            )

        # HOTELIERS special logic
        elif segment == "Hoteliers":

            ota_pattern = r"connect|türsab|ratefor"

            mask = ~(
                df['name'].str.contains(
                    ota_pattern,
                    case=False,
                    na=False,
                    regex=True
                ) |
                df['campaign'].str.contains(
                    ota_pattern,
                    case=False,
                    na=False,
                    regex=True
                )
            )

        combined_mask = combined_mask | mask

    df = df[combined_mask]

# -----------------------------
# WEIGHTS
# -----------------------------
st.sidebar.header("Weights")

w_open = st.sidebar.slider("Open Rate", 0.0, 1.0, 0.4)
w_ctr = st.sidebar.slider("CTR", 0.0, 1.0, 0.4)
w_opt = st.sidebar.slider("Opt-out Penalty", 0.0, 1.0, 0.2)

# -----------------------------
# ANALYSIS
# -----------------------------
if 'hour_interval' not in df.columns:
    st.error("Missing 'hour_interval' column")
    st.stop()

def weighted_avg(values, weights):

    if weights.sum() == 0:
        return 0

    return np.average(values, weights=weights)

agg = df.groupby('hour_interval').apply(
    lambda x: pd.Series({

        'base': x['base'].sum(),

        'open_rate': weighted_avg(
            x['open_rate'],
            x['base']
        ),

        'ctr': weighted_avg(
            x['unique_ctr'],
            x['base']
        ),

        'opt_out_rate': weighted_avg(
            x['opt_out_rate'],
            x['base']
        )
    })
).reset_index()

agg = agg.fillna(0)

agg['score'] = (
    agg['open_rate'] * w_open +
    agg['ctr'] * w_ctr -
    agg['opt_out_rate'] * w_opt
) * np.log1p(agg['base'])

agg = agg.sort_values("score", ascending=False)

# -----------------------------
# BUSINESS HOURS FILTER
# -----------------------------
def extract_hour(interval):

    try:
        return int(str(interval).split(":")[0])
    except:
        return None

agg['hour_num'] = agg['hour_interval'].apply(extract_hour)

business_hours = agg[
    (agg['hour_num'] >= 9) &
    (agg['hour_num'] < 18)
].copy()

overall_best = agg.iloc[0]

if not business_hours.empty:
    business_best = business_hours.iloc[0]
else:
    business_best = overall_best

avg_ctr = agg['ctr'].mean()
avg_open = agg['open_rate'].mean()
avg_opt_out = agg['opt_out_rate'].mean()

overall_best = agg.iloc[0]

if overall_best['hour_num'] < 9 or overall_best['hour_num'] >= 18:

    st.warning(
        "Top-performing hour falls outside business hours."
    )

    st.subheader("Recommended Business Hours")

    top_business = business_hours.head(3)

    for _, row in top_business.iterrows():

        st.write(
            f"• {row['hour_interval']} "
            f"(Score: {row['score']:.2f})"
        )

col1, col2 = st.columns(2)

with col1:
    st.metric(
        "🏆 Overall Best",
        overall_best['hour_interval']
    )

with col2:
    st.metric(
        "💼 Business Hours Best",
        business_best['hour_interval']
    )

col3, col4 = st.columns(2)

with col3:
    st.metric(
        "📈 CTR",
        f"{business_best['ctr']:.2%}"
    )

with col4:
    st.metric(
        "📬 Open Rate",
        f"{business_best['open_rate']:.2%}"
    )

st.subheader("📊 Executive Summary")

st.info(f"""
The strongest performing send window is **{overall_best['hour_interval']}**.

This interval outperforms other hours due to:
- stronger click-through performance
- healthy open rates
- lower unsubscribe behavior
- statistically meaningful send volume

Recommendation:
Prioritize this time window for future campaigns,
especially for the selected segment and day filters.
""")

# -----------------------------
# OUTPUT
# -----------------------------
st.subheader("Best Send Times")
st.dataframe(agg)
st.bar_chart(agg.set_index("hour_interval")["score"])

top = agg.iloc[0]
st.success(f"Best time is: {top['hour_interval']} (Score: {top['score']:.2f})")

st.subheader("Why this hour performs well")

reasons = []

if top['ctr'] > avg_ctr:
    reasons.append(
        f"CTR ({top['ctr']:.2%}) is above average ({avg_ctr:.2%})"
    )

if top['open_rate'] > avg_open:
    reasons.append(
        f"Open rate ({top['open_rate']:.2%}) is above average ({avg_open:.2%})"
    )

if top['opt_out_rate'] < avg_opt_out:
    reasons.append(
        f"Opt-out rate ({top['opt_out_rate']:.2%}) is lower than average ({avg_opt_out:.2%})"
    )

if top['base'] > agg['base'].median():
    reasons.append(
        f"Performance is supported by high send volume ({int(top['base'])} sends)"
    )

for reason in reasons:
    st.write(f"• {reason}")

# -----------------------------
# HEATMAP
# -----------------------------
if 'day_of_week' in df.columns:

    pivot = df.groupby(['day_of_week', 'hour_interval']).agg({
        'base': 'sum',
        'unique_clicks': 'sum'
    }).reset_index()

    pivot = pivot[pivot['base'] > 0]
    pivot['ctr'] = pivot['unique_clicks'] / pivot['base']

    heatmap = pivot.pivot_table(
        index='day_of_week',
        columns='hour_interval',
        values='ctr',
        aggfunc='mean'
    ).fillna(0)

    st.subheader("Heatmap (CTR)")

    fig = px.imshow(
        heatmap,
        text_auto=".2%",
        color_continuous_scale="Blues",
        aspect="auto"
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("No day_of_week column found")'''

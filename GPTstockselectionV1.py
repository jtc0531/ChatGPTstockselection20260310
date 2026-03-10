import streamlit as st
import pandas as pd
import numpy as np
import datetime
from FinMind.data import DataLoader

st.set_page_config(page_title="台股飆股雷達 V2", layout="wide")

st.title("🚀 台股飆股雷達 V2")

# ------------------------
# 側邊欄
# ------------------------

st.sidebar.header("策略設定")

capital = st.sidebar.number_input(
    "總投資資金",
    value=1000000
)

volume_multiplier = st.sidebar.slider(
    "爆量倍數",
    1.2,
    3.0,
    1.5
)

revenue_threshold = st.sidebar.slider(
    "營收YoY門檻 %",
    10,
    50,
    20
)

# ------------------------
# FinMind
# ------------------------

dl = DataLoader()

# ------------------------
# 股價資料
# ------------------------

@st.cache_data
def get_price_data():

    today = datetime.date.today()
    start = today - datetime.timedelta(days=400)

    df = dl.dataset(
        dataset="TaiwanStockPrice",
        start_date=start.strftime("%Y-%m-%d")
    )

    return df


# ------------------------
# 營收資料
# ------------------------

@st.cache_data
def get_revenue_data():

    today = datetime.date.today()
    start = today - datetime.timedelta(days=800)

    df = dl.dataset(
        dataset="TaiwanStockMonthRevenue",
        start_date=start.strftime("%Y-%m-%d")
    )

    return df


# ------------------------
# 營收YoY
# ------------------------

def compute_revenue_yoy(df):

    df = df.sort_values(["stock_id", "date"])

    df["revenue"] = pd.to_numeric(df["revenue"])

    df["rev_last_year"] = df.groupby("stock_id")["revenue"].shift(12)

    df["yoy"] = (df["revenue"] - df["rev_last_year"]) / df["rev_last_year"]

    latest = df.groupby("stock_id").tail(1)

    return latest[["stock_id", "yoy"]]


# ------------------------
# 技術分析
# ------------------------

def compute_technical(df):

    df = df.sort_values(["stock_id", "date"])

    result = []

    for stock, g in df.groupby("stock_id"):

        if len(g) < 200:
            continue

        price = g["close"].iloc[-1]

        high120 = g["close"].tail(120).max()

        vol = g["Trading_Volume"].iloc[-1]
        vol20 = g["Trading_Volume"].tail(20).mean()

        ma200 = g["close"].rolling(200).mean().iloc[-1]

        score = 0
        reason = []

        if price > high120:
            score += 40
            reason.append("突破120日新高")

        if vol > vol20 * volume_multiplier:
            score += 30
            reason.append("成交量爆發")

        if price > ma200:
            score += 10
            reason.append("長期多頭")

        result.append({
            "stock_id": stock,
            "price": price,
            "tech_score": score,
            "tech_reason": " | ".join(reason),
            "volume": vol
        })

    return pd.DataFrame(result)


# ------------------------
# 主程式
# ------------------------

if st.button("🚀 開始掃描"):

    with st.spinner("抓取股價資料..."):
        price_df = get_price_data()

    with st.spinner("抓取營收資料..."):
        revenue_df = get_revenue_data()

    with st.spinner("計算技術分析..."):
        tech_df = compute_technical(price_df)

    with st.spinner("計算營收YoY..."):
        rev_df = compute_revenue_yoy(revenue_df)

    df = pd.merge(
        tech_df,
        rev_df,
        on="stock_id",
        how="left"
    )

    df["rev_score"] = np.where(
        df["yoy"] > revenue_threshold / 100,
        40,
        0
    )

    df["rev_reason"] = df["yoy"].apply(
        lambda x: f"營收YoY {round(x*100,1)}%" if pd.notna(x) else ""
    )

    df["total_score"] = df["tech_score"] + df["rev_score"]

    df = df[df["total_score"] >= 50]

    df = df.sort_values(
        "total_score",
        ascending=False
    )

    df["建議資金"] = capital * 0.03

    df["停損價"] = df["price"] * 0.9

    display = df[[
        "stock_id",
        "price",
        "total_score",
        "tech_reason",
        "rev_reason",
        "建議資金",
        "停損價"
    ]]

    display = display.rename(columns={
        "stock_id": "股票",
        "price": "股價",
        "total_score": "策略評分",
        "tech_reason": "技術訊號",
        "rev_reason": "基本面"
    })

    st.success(f"找到 {len(display)} 檔潛力股")

    st.dataframe(
        display.head(30),
        use_container_width=True
    )

    csv = display.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "下載CSV",
        csv,
        "taiwan_stock_radar.csv",
        "text/csv"
    )

st.markdown("---")

st.caption("策略核心：營收動能 + 成交量爆發 + 技術突破")
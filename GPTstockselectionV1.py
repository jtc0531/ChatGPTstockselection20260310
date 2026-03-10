import streamlit as st
import pandas as pd
import numpy as np
import datetime
from FinMind.data import DataLoader

st.set_page_config(page_title="台股飆股雷達 V3", layout="wide")
st.title("🚀 台股飆股雷達 V3 (專業版)")

# ------------------------
# 側邊欄設定
# ------------------------
st.sidebar.header("策略參數")
capital = st.sidebar.number_input("總投資資金", value=1000000)
volume_multiplier = st.sidebar.slider("爆量倍數", 1.2, 3.0, 1.5)
revenue_threshold = st.sidebar.slider("營收YoY門檻 %", 10, 50, 20)
min_trade_value = st.sidebar.number_input("最低成交金額 (TWD)", value=30000000)
scan_limit = st.sidebar.slider("每批掃描檔數", 200, 1000, 500)

# ------------------------
# FinMind 初始化
# ------------------------
dl = DataLoader()

# ------------------------
# 抓股價資料 (分批抓，避免卡住)
# ------------------------
@st.cache_data(ttl=3600)
def get_price_data(batch_size=500):
    today = datetime.date.today()
    start = today - datetime.timedelta(days=250)  # 最近 250 天足夠技術分析

    # 抓全部台股清單
    stock_list = dl.fetch("TaiwanStockPrice", parameters={"start_date": start.strftime("%Y-%m-%d")})
    
    # 過濾低成交量
    stock_list = stock_list[stock_list["Trading_Volume"] > 1000]

    # 分批抓取，避免一次大量資料卡住
    batches = []
    stock_ids = stock_list["stock_id"].unique()
    for i in range(0, len(stock_ids), batch_size):
        batch = stock_list[stock_list["stock_id"].isin(stock_ids[i:i+batch_size])]
        batches.append(batch)
    df = pd.concat(batches)
    df["date"] = pd.to_datetime(df["date"])
    return df

# ------------------------
# 抓月營收資料
# ------------------------
@st.cache_data(ttl=3600)
def get_revenue_data():
    today = datetime.date.today()
    start = today - datetime.timedelta(days=800)
    rev_df = dl.fetch("TaiwanStockMonthRevenue", parameters={"start_date": start.strftime("%Y-%m-%d")})
    rev_df["revenue"] = pd.to_numeric(rev_df["revenue"])
    return rev_df

# ------------------------
# 計算營收YoY
# ------------------------
def compute_revenue_yoy(df):
    df = df.sort_values(["stock_id", "date"])
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
        trade_value = price * vol
        if trade_value < min_trade_value:
            continue  # 過濾流動性不足
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
            "volume": vol,
            "trade_value": trade_value
        })
    return pd.DataFrame(result)

# ------------------------
# 主程式
# ------------------------
if st.button("🚀 開始掃描"):
    with st.spinner("抓取股價資料..."):
        price_df = get_price_data(batch_size=scan_limit)
    with st.spinner("抓取營收資料..."):
        revenue_df = get_revenue_data()
    st.write("資料載入完成")

    with st.spinner("計算技術分析..."):
        tech_df = compute_technical(price_df)
    with st.spinner("計算營收YoY..."):
        rev_df = compute_revenue_yoy(revenue_df)

    # 合併技術 + 營收
    df = pd.merge(tech_df, rev_df, on="stock_id", how="left")
    df["rev_score"] = np.where(df["yoy"] > revenue_threshold / 100, 40, 0)
    df["rev_reason"] = df["yoy"].apply(lambda x: f"營收YoY {round(x*100,1)}%" if pd.notna(x) else "")
    df["total_score"] = df["tech_score"] + df["rev_score"]
    df = df[df["total_score"] >= 50]
    df = df.sort_values("total_score", ascending=False)
    df["建議資金"] = capital * 0.03
    df["停損價"] = df["price"] * 0.9

    display = df[[
        "stock_id", "price", "total_score", "tech_reason", "rev_reason", "建議資金", "停損價"
    ]].rename(columns={
        "stock_id": "股票",
        "price": "股價",
        "total_score": "策略評分",
        "tech_reason": "技術訊號",
        "rev_reason": "基本面"
    })

    st.success(f"找到 {len(display)} 檔潛力股")
    st.dataframe(display.head(50), use_container_width=True)

    csv = display.to_csv(index=False).encode("utf-8-sig")
    st.download_button("下載CSV", csv, "taiwan_stock_radar.csv", "text/csv")

st.markdown("---")
st.caption("策略核心：營收動能 + 成交量爆發 + 技術突破，分批抓取，流動性過濾")
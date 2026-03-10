import streamlit as st
import pandas as pd
import requests
import numpy as np
from FinMind.data import DataLoader
import datetime

st.set_page_config(page_title="台股飆股雷達 Pro", layout="wide")

st.title("🚀 台股飆股雷達 Pro")

# -----------------------
# 參數設定
# -----------------------

st.sidebar.header("策略設定")

capital = st.sidebar.number_input(
    "投資總資金", value=1000000
)

volume_multiplier = st.sidebar.slider(
    "爆量倍數",
    1.2,
    3.0,
    1.5
)

revenue_threshold = st.sidebar.slider(
    "營收 YoY 門檻 %",
    10,
    50,
    20
)

# -----------------------
# 抓台股價格
# -----------------------

@st.cache_data
def get_price_data():

    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"

    r = requests.get(url)
    data = r.json()

    df = pd.DataFrame(data)

    df = df.rename(columns={
        "Code": "stock_id",
        "Name": "name",
        "ClosingPrice": "close",
        "TradeVolume": "volume",
        "TradeValue": "value"
    })

    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    return df


# -----------------------
# 月營收資料
# -----------------------

@st.cache_data
def get_revenue_data(stock_id):

    dl = DataLoader()

    today = datetime.date.today()
    start = today - datetime.timedelta(days=400)

    df = dl.taiwan_stock_month_revenue(
        stock_id=stock_id,
        start_date=start.strftime("%Y-%m-%d")
    )

    return df


# -----------------------
# 技術面計算
# -----------------------

def technical_score(stock_id):

    try:

        url = f"https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPrice&data_id={stock_id}&start_date=2023-01-01"

        res = requests.get(url)
        data = res.json()["data"]

        df = pd.DataFrame(data)

        if len(df) < 200:
            return None

        df["close"] = pd.to_numeric(df["close"])

        high120 = df["close"].tail(120).max()
        price = df["close"].iloc[-1]

        vol = df["Trading_Volume"].iloc[-1]
        vol20 = df["Trading_Volume"].tail(20).mean()

        score = 0
        reason = []

        if price > high120:
            score += 40
            reason.append("突破120日高")

        if vol > vol20 * volume_multiplier:
            score += 30
            reason.append("成交量爆發")

        ma200 = df["close"].rolling(200).mean().iloc[-1]

        if price > ma200:
            score += 10
            reason.append("長期多頭")

        return score, reason, price

    except:

        return None


# -----------------------
# 營收評分
# -----------------------

def revenue_score(stock_id):

    try:

        df = get_revenue_data(stock_id)

        if len(df) < 6:
            return 0

        df["revenue"] = pd.to_numeric(df["revenue"])

        yoy = (df["revenue"].iloc[-1] - df["revenue"].iloc[-13]) / df["revenue"].iloc[-13]

        score = 0
        reason = []

        if yoy > revenue_threshold / 100:
            score += 40
            reason.append(f"營收YoY {round(yoy*100,1)}%")

        return score, reason

    except:

        return 0, []


# -----------------------
# 主分析函數
# -----------------------

def analyze_stock(row):

    stock_id = row["stock_id"]
    name = row["name"]

    # 流動性過濾

    if row["value"] < 30000000:
        return None

    if row["close"] < 8:
        return None

    tech = technical_score(stock_id)

    if tech is None:
        return None

    tech_score, tech_reason, price = tech

    rev_score, rev_reason = revenue_score(stock_id)

    total = tech_score + rev_score

    if total < 50:
        return None

    return {
        "股票": stock_id,
        "名稱": name,
        "股價": price,
        "策略評分": total,
        "技術訊號": " | ".join(tech_reason),
        "基本面": " | ".join(rev_reason),
        "建議資金": int(capital * 0.03),
        "停損": round(price * 0.9, 2)
    }


# -----------------------
# 執行掃描
# -----------------------

if st.button("開始掃描台股"):

    df = get_price_data()

    results = []

    progress = st.progress(0)

    total = len(df)

    for i, row in df.iterrows():

        res = analyze_stock(row)

        if res:
            results.append(res)

        progress.progress((i + 1) / total)

    if results:

        result_df = pd.DataFrame(results)

        result_df = result_df.sort_values(
            "策略評分",
            ascending=False
        )

        st.success(f"找到 {len(result_df)} 檔潛力飆股")

        st.dataframe(result_df.head(30), use_container_width=True)

        csv = result_df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "下載結果",
            csv,
            "taiwan_stock_radar.csv",
            "text/csv"
        )

    else:

        st.warning("未找到符合條件股票")
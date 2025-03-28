# btc_dashboard.py
import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import matplotlib.pyplot as plt
import pandas_ta as ta  # Changed from talib to avoid installation issues
from datetime import datetime, timedelta

# Configure page
st.set_page_config(
    page_title="BTC-USD Trading Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
.small-font { font-size:14px !important; }
.metric-box { padding:20px; background-color:#2d2d2d; border-radius:10px }
</style>
""", unsafe_allow_html=True)

# API Configuration (Use Streamlit Secrets)
if 'LUNARCRUSH_KEY' in st.secrets:
    LUNARCRUSH_KEY = st.secrets['LUNARCRUSH_KEY']
else:
    st.error("Missing LunarCrush API key in secrets")

ALTERNATIVE_API = "https://api.alternative.me"
COINGECKO_API = "https://api.coingecko.com/api/v3"

# Helper functions
@st.cache_data(ttl=300)
def get_live_price():
    btc = yf.Ticker("BTC-USD")
    data = btc.history(period="1d")
    return data.iloc[-1].Close, data.iloc[-1].Close - data.iloc[0].Close

@st.cache_data(ttl=3600)
def get_fear_greed():
    try:
        res = requests.get(f"{ALTERNATIVE_API}/fng/", timeout=10)
        data = res.json()['data'][0]
        return int(data['value']), data['value_classification']
    except Exception as e:
        st.error(f"Fear & Greed Error: {str(e)}")
        return None, "N/A"

@st.cache_data(ttl=600)
def get_social_metrics():
    try:
        # LunarCrush Social Metrics
        lc_res = requests.get(
            f"https://api.lunarcrush.com/v2?data=assets&key={LUNARCRUSH_KEY}&symbol=BTC&data_points=1",
            timeout=10
        )
        lc_data = lc_res.json()['data'][0]
        
        # CoinGecko Social Data
        cg_res = requests.get(f"{COINGECKO_API}/coins/bitcoin", timeout=10)
        cg_data = cg_res.json()
        
        return {
            'social_volume': lc_data.get('social_volume', 'N/A'),
            'sentiment': lc_data.get('sentiment', 'N/A'),
            'galaxy_score': lc_data.get('galaxy_score', 'N/A'),
            'twitter_followers': cg_data['community_data']['twitter_followers'],
            'reddit_subscribers': cg_data['community_data']['reddit_subscribers']
        }
    except Exception as e:
        st.error(f"Social Metrics Error: {str(e)}")
        return None

@st.cache_data(ttl=600)
def get_historical_data(interval='1h', days=7):
    ticker = yf.Ticker("BTC-USD")
    data = ticker.history(interval=interval, period=f"{days}d")
    return data

def calculate_technicals(df):
    # Using pandas_ta instead of talib
    df.ta.rsi(length=14, append=True)
    df.ta.macd(append=True)
    df.ta.sma(length=20, append=True)
    df.ta.bbands(length=20, append=True)
    return df

# Main App
def main():
    st.title("₿ Bitcoin Trading Dashboard")
    
    # Live metrics row
    col1, col2, col3 = st.columns(3)
    price, change = get_live_price()
    
    with col1:
        st.metric("Current Price", f"${price:,.2f}", 
                 f"{change:.2f} ({(change/price)*100:.2f}%)")
    
    with col2:
        fg_value, fg_text = get_fear_greed()
        st.metric("Fear & Greed Index", 
                 f"{fg_value or 'N/A'} ({fg_text})",
                 help="0-100 scale: Extreme Fear to Extreme Greed")
    
    with col3:
        social_data = get_social_metrics()
        if social_data:
            st.markdown(f"""
            <div class="metric-box">
                <div class="small-font">📈 Social Volume: {social_data['social_volume']:,}</div>
                <div class="small-font">😃 Sentiment: {social_data['sentiment']}</div>
                <div class="small-font">🌌 Galaxy Score: {social_data['galaxy_score']}/100</div>
                <div class="small-font">🐦 Twitter Followers: {social_data['twitter_followers']:,}</div>
                <div class="small-font">🎮 Reddit Subscribers: {social_data['reddit_subscribers']:,}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.warning("Social metrics unavailable")

    # Timeframe selection
    timeframe = st.selectbox("Select Timeframe", 
                            ['15m', '1h', '4h', '1d', '1wk'], 
                            index=1,
                            help="Choose chart interval")

    # Historical data and technicals
    timeframe_map = {'15m': 3, '1h': 7, '4h': 14, '1d': 30, '1wk': 52}
    data = get_historical_data(timeframe, timeframe_map[timeframe])
    data = calculate_technicals(data)

    # Price chart
    st.subheader(f"Price Chart ({timeframe})")
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(data['Close'], label='Price', color='#FF4B4B')
    ax.plot(data['SMA_20'], label='20 SMA', color='#00FF00', alpha=0.7)
    ax.fill_between(data.index, 
                   data['BBL_20_2.0'], 
                   data['BBU_20_2.0'], 
                   color='#1F77B4', 
                   alpha=0.1)
    ax.set_facecolor('#0E1117')
    ax.grid(color='#2d2d2d')
    ax.legend()
    st.pyplot(fig)

    # Technical indicators
    st.subheader("Technical Signals")
    cols = st.columns(4)
    with cols[0]:
        rsi = data['RSI_14'].iloc[-1]
        status = "Overbought 🚨" if rsi > 70 else "Oversold 🚨" if rsi < 30 else "Neutral"
        st.metric("RSI (14)", f"{rsi:.1f}", status)
    
    with cols[1]:
        macd = data['MACD_12_26_9'].iloc[-1]
        signal = data['MACDs_12_26_9'].iloc[-1]
        status = "Bullish ↗️" if macd > signal else "Bearish ↘️"
        st.metric("MACD", f"{macd:.2f}", f"Signal: {signal:.2f} ({status})")
    
    with cols[2]:
        bb_percent = ((data['Close'].iloc[-1] - data['BBL_20_2.0'].iloc[-1]) / 
                     (data['BBU_20_2.0'].iloc[-1] - data['BBL_20_2.0'].iloc[-1]))
        status = "High Volatility" if bb_percent > 0.8 else "Low Volatility" if bb_percent < 0.2 else "Normal"
        st.metric("Bollinger %", f"{bb_percent:.2f}", status)
    
    with cols[3]:
        trend = "Bullish ↗️" if data['Close'].iloc[-1] > data['SMA_20'].iloc[-1] else "Bearish ↘️"
        st.metric("Trend Direction", trend)

    # Trading recommendations
    st.subheader("Trading Advice")
    advice = []
    
    # RSI based
    if rsi > 70:
        advice.append("Consider taking profits - RSI indicates overbought condition")
    elif rsi < 30:
        advice.append("Potential buying opportunity - RSI indicates oversold condition")
    
    # MACD based
    if macd > signal + 1.0:
        advice.append("Strong bullish momentum - MACD above signal line")
    elif macd < signal - 1.0:
        advice.append("Bearish momentum building - MACD below signal line")
    
    # Bollinger Bands
    if data['Close'].iloc[-1] > data['BBU_20_2.0'].iloc[-1]:
        advice.append("Price above upper Bollinger Band - possible mean reversion")
    elif data['Close'].iloc[-1] < data['BBL_20_2.0'].iloc[-1]:
        advice.append("Price below lower Bollinger Band - potential bounce opportunity")
    
    if not advice:
        advice.append("No strong signals detected - maintain current positions")
    
    for item in advice:
        st.write(f"• {item}")

    # Disclaimer
    st.markdown("---")
    st.markdown("""
    **Disclaimer**:  
    This dashboard provides informational purposes only and should not be considered financial advice.  
    Cryptocurrency trading involves substantial risk of loss and is not suitable for all investors.  
    Always conduct your own research and consult with a qualified financial advisor.
    """)

if __name__ == "__main__":
    main()
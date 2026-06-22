import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
import urllib.parse

st.set_page_config(page_title="Collectibles Sniper Engine", page_icon="🕹️", layout="wide")

# =====================================================================
# 🔬 CORE DATA ENGINE FUNCTIONS
# =====================================================================

def get_live_pricecharting_data(game_title):
    """Parses PriceCharting search results to extract live market values."""
    encoded_query = urllib.parse.quote(game_title)
    search_url = f"https://www.pricecharting.com/search-products?type=prices&q={encoded_query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        price_table = soup.find('table', id='price_data')
        
        # If it's a search result page with multiple matches, follow the first title link
        if not price_table:
            product_list = soup.find('td', class_='title')
            if product_list and product_list.find('a'):
                direct_url = "https://www.pricecharting.com" + product_list.find('a')['href']
                response = requests.get(direct_url, headers=headers, timeout=10)
                soup = BeautifulSoup(response.content, 'html.parser')
                price_table = soup.find('table', id='price_data')
        
        if price_table:
            prices = {}
            rows = price_table.find_all('tr')
            for row in rows:
                text = row.text.strip()
                if "Loose" in text:
                    prices['Loose'] = float(row.find('td', class_='price').text.strip().replace('$','').replace(',',''))
                elif "CIB" in text:
                    prices['CIB'] = float(row.find('td', class_='price').text.strip().replace('$','').replace(',',''))
                elif "New" in text:
                    prices['New'] = float(row.find('td', class_='price').text.strip().replace('$','').replace(',',''))
            return prices
            
    except Exception:
        return None
    return None


def search_ebay_deals(query, max_price):
    """Combs eBay RSS feed for newly listed Buy It Now items under the target price."""
    encoded_query = urllib.parse.quote(query)
    # _sop=10 (Newly Listed), _lh=1 (Buy It Now Only), _rss=1 (RSS Feed format)
    rss_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&_sop=10&_lh=1&_udhi={max_price}&_rss=1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    try:
        response = requests.get(rss_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
        
        root = ET.fromstring(response.content)
        listings = []
        
        for item in root.findall('.//item'):
            title = item.find('title').text
            link = item.find('link').text
            desc = item.find('description').text if item.find('description') is not None else ""
            
            price = 0.0
            if "Price:" in desc:
                try:
                    price_str = desc.split("Price:")[1].split()[0].replace("$", "").replace(",", "")
                    price = float(price_str)
                except:
                    pass
            
            if 0 < price <= max_price:
                listings.append({
                    "Title": title,
                    "Price": f"${price:.2f}",
                    "RawPrice": price,
                    "Link": link
                })
        return listings
    except Exception:
        return []

# =====================================================================
# 🖥️ STREAMLIT INTERFACE LAYOUT
# =====================================================================

st.title("🕹️ Retro Game & Collectibles Flipping Engine")
st.subheader("Data-Driven Reselling Linked to Long-Term Wealth Compounding")
st.markdown("---")

# --- STEP 1: PRICECHARTING VALUATION LOOKUP ---
st.markdown("### 🔍 Step 1: Live Market Valuation")
search_input = st.text_input("Enter Game Title / Console name:", placeholder="e.g., Pokemon SoulSilver DS")

# Initialize session state variables to hold data across runs
if "market_prices" not in st.session_state:
    st.session_state.market_prices = None
if "last_search" not in st.session_state:
    st.session_state.last_search = ""

# Trigger fresh scrape only if search term changes or state is clear
if search_input and search_input != st.session_state.last_search:
    with st.spinner("Fetching baseline data from PriceCharting..."):
        st.session_state.market_prices = get_live_pricecharting_data(search_input)
        st.session_state.last_search = search_input

# Display data if found
if st.session_state.market_prices:
    prices = st.session_state.market_prices
    st.success(f"📈 Real-Time Market Valuations Found for: **{search_input}**")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Loose Value", f"${prices.get('Loose', 0.0):.2f}")
    c2.metric("CIB Value", f"${prices.get('CIB', 0.0):.2f}")
    c3.metric("New / Sealed Value", f"${prices.get('New', 0.0):.2f}")
    
    st.markdown("---")
    
    # --- STEP 2: FEE AND PROFIT ALLOCATION MARGIN CALCULATOR ---
    st.markdown("### 📊 Step 2: Siphon Margin Optimization Calculator")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        chosen_condition = st.selectbox("Select Target Variant Condition:", ["Loose", "CIB", "New"])
        target_value = prices.get(chosen_condition, 0.0)
        discount_pct = st.slider("Target Sourcing Discount % (Target buy price vs Market)", 10, 60, 40)
        
    with col_m2:
        platform_fee_pct = st.number_input("Platform Fee % (e.g., eBay Standard)", min_value=0.0, value=13.25, step=0.25)
        est_shipping = st.number_input("Estimated Shipping / Material Costs ($)", min_value=0.0, value=5.00, step=0.50)

    # Automated maximum buy price boundary setting
    suggested_buy_price = target_value * (1 - (discount_pct / 100))
    
    # Math Calculations
    gross_revenue = target_value
    fees = gross_revenue * (platform_fee_pct / 100)
    expected_net_profit = gross_revenue - suggested_buy_price - fees - est_shipping
    
    st.markdown("#### **Deal Architecture Matrix**")
    p_col1, p_col2, p_col3 = st.columns(3)
    
    p_col1.metric("Max Suggested Buy Price", f"${suggested_buy_price:.2f}")
    
    if expected_net_profit > 0:
        p_col2.metric("Projected Net Profit", f"${expected_net_profit:.2f}")
        
        # The 40/60 Split Rule Integration
        index_siphon = expected_net_profit * 0.40
        reinvest_ammo = expected_net_profit * 0.60
        p_col3.metric("40% Index Fund Siphon", f"${index_siphon:.2f}")
        
        st.success(f"🔥 Operational Clearance: Buying at or below ${suggested_buy_price:.2f} leaves you with ${reinvest_ammo:.2f} to cycle back into raw inventory.")
    else:
        p_col2.metric("Projected Net Profit", f"${expected_net_profit:.2f}", delta="- Margin Deficit")
        st.error("🚨 Red Light: Friction elements (fees/shipping) exceed the target purchase allocation. Negotiate a steeper discount.")
        
    st.markdown("---")
    
    # --- STEP 3: AUTOMATED EBAY LIVE SNIPER ENGINE ---
    st.markdown("### 🎯 Step 3: Run Live eBay Valuation Sniper")
    st.write(f"Scans active 'Buy It Now' listings for items matching your exact configuration under the **${suggested_buy_price:.2f}** limit threshold.")
    
    if st.button("🚀 Execute Live Deal Scan"):
        with st.spinner("Combing incoming XML data pipeline channels..."):
            deals = search_ebay_deals(search_input, suggested_buy_price)
            
            if deals:
                st.success(f"🎯 Found {len(deals)} listings meeting your target purchase threshold!")
                for deal in deals:
                    with st.container():
                        d_col1, d_col2 = st.columns([4, 1])
                        d_col1.write(f"**{deal['Title']}**")
                        d_col2.write(f"💰 **{deal['Price']}**")
                        st.markdown(f"[⚡ Instantly Open and Purchase Listing on eBay]({deal['Link']})")
                        st.markdown("---")
            else:
                st.warning("No active listings found under your current target buy floor right now. Try expanding your target search term or check back later!")

elif search_input:
    st.info("Waiting for data string execution. If this hangs, verify spelling or append the specific console family to the input field.")
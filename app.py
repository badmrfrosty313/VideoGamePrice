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
    """Parses PriceCharting search results securely with anti-hang fallbacks."""
    clean_query = game_title.strip()
    encoded_query = urllib.parse.quote(clean_query)
    search_url = f"https://www.pricecharting.com/search-products?type=prices&q={encoded_query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=5)
        if response.status_code != 200:
            return None
            
        soup = BeautifulSoup(response.content, 'html.parser')
        price_table = soup.find('table', id='price_data')
        
        # Multi-result fallback logic (if we land on a search list instead of an item page)
        if not price_table:
            product_list = soup.find('td', class_='title')
            if product_list and product_list.find('a'):
                direct_url = "https://www.pricecharting.com" + product_list.find('a')['href']
                response = requests.get(direct_url, headers=headers, timeout=5)
                soup = BeautifulSoup(response.content, 'html.parser')
                price_table = soup.find('table', id='price_data')
        
        if price_table:
            prices = {}
            rows = price_table.find_all('tr')
            for row in rows:
                text = row.text.strip()
                price_td = row.find('td', class_='price')
                if price_td and price_td.text.strip():
                    try:
                        raw_val = float(price_td.text.strip().replace('$','').replace(',','').strip())
                        if "Loose" in text:
                            prices['Loose'] = raw_val
                        elif "CIB" in text:
                            prices['CIB'] = raw_val
                        elif "New" in text:
                            prices['New'] = raw_val
                    except ValueError:
                        pass
            
            if prices:
                return prices
                
    except requests.exceptions.Timeout:
        st.error("⏳ PriceCharting connection timed out. The server is heavily throttled right now.")
        return None
    except Exception as e:
        st.error(f"⚠️ Scraping pipeline error: {e}")
        return None
    return None


def search_ebay_deals(query, max_price):
    """Combs eBay RSS feed for Buy It Now items sorted strictly by Lowest Price + Shipping."""
    clean_query = query.strip()
    encoded_query = urllib.parse.quote(clean_query)
    
    # 🎯 THE DEEP VALUE OPTIMIZATION: 
    # _sop=15 -> Sorts by Price + Shipping: Lowest First.
    # _udlo=2  -> Sets a $2.00 minimum boundary floor to strip away filler/junk accessories.
    rss_url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&_sop=15&_lh=1&_udlo=2&_udhi={max_price}&_rss=1"
    
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
            
            # Enforce the strict pricing Sweet Spot boundary check
            if 2.00 <= price <= max_price:
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
search_input = st.text_input("Enter Game Title / Console name:", placeholder="e.g., Smash Bros Melee Gamecube")

# UI Logic States
if "market_prices" not in st.session_state:
    st.session_state.market_prices = None
if "last_search" not in st.session_state:
    st.session_state.last_search = ""
if "manual_override" not in st.session_state:
    st.session_state.manual_override = False

# Run search if string input updates
if search_input and search_input != st.session_state.last_search:
    with st.spinner("Fetching baseline data from PriceCharting..."):
        data = get_live_pricecharting_data(search_input)
        if data:
            st.session_state.market_prices = data
            st.session_state.manual_override = False
        else:
            st.session_state.market_prices = None
            st.session_state.manual_override = True
        st.session_state.last_search = search_input

# --- BACKUP OVERRIDE CONTAINER ---
if st.session_state.manual_override:
    st.warning("⚠️ Live Automation Check Blocked. PriceCharting firewall intercepted the server. Shifting to Manual Vault Override mode:")
    m_loose = st.number_input("Enter Loose Market Value ($)", min_value=0.0, value=20.0)
    m_cib = st.number_input("Enter CIB Market Value ($)", min_value=0.0, value=45.0)
    m_new = st.number_input("Enter New Market Value ($)", min_value=0.0, value=100.0)
    st.session_state.market_prices = {"Loose": m_loose, "CIB": m_cib, "New": m_new}

# Display calculation layers if data exists
if st.session_state.market_prices:
    prices = st.session_state.market_prices
    
    if not st.session_state.manual_override:
        st.success(f"📈 Real-Time Market Valuations Active for: **{search_input}**")
    
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

    # Calculate optimal entry numbers
    suggested_buy_price = target_value * (1 - (discount_pct / 100))
    gross_revenue = target_value
    fees = gross_revenue * (platform_fee_pct / 100)
    expected_net_profit = gross_revenue - suggested_buy_price - fees - est_shipping
    
    st.markdown("#### **Deal Architecture Matrix**")
    p_col1, p_col2, p_col3 = st.columns(3)
    
    p_col1.metric("Max Suggested Buy Price", f"${suggested_buy_price:.2f}")
    
    if expected_net_profit > 0:
        p_col2.metric("Projected Net Profit", f"${expected_net_profit:.2f}")
        
        # Enforcing our permanent 40% Long-Term Index Vault allocation rule
        index_siphon = expected_net_profit * 0.40
        reinvest_ammo = expected_net_profit * 0.60
        p_col3.metric("40% Index Fund Siphon", f"${index_siphon:.2f}")
        
        st.success(f"🔥 Operational Clearance: Buying at or below ${suggested_buy_price:.2f} leaves you with ${reinvest_ammo:.2f} to cycle back into raw inventory.")
    else:
        p_col2.metric("Projected Net Profit", f"${expected_net_profit:.2f}", delta="- Margin Deficit")
        st.error("🚨 Red Light: Friction elements (fees/shipping) exceed the target purchase allocation. Negotiate a steeper discount.")
        
    st.markdown("---")
    
    # --- STEP 3: AUTOMATED EBAY LIVE SNIPER ENGINE ---
    st.markdown("### 🎯 Step 3: Run Live Lowest-Price eBay Sniper")
    st.write(f"Scans active 'Buy It Now' listings sorted by **Lowest Price + Shipping** under your maximum **${suggested_buy_price:.2f}** margin floor.")
    
    if st.button("🚀 Execute Lowest-Price Scan"):
        with st.spinner("Sweeping market channels for bottom-tier prices..."):
            deals = search_ebay_deals(search_input, suggested_buy_price)
            
            if deals:
                st.success(f"🎯 Found {len(deals)} listings matching your target floor, ranked cheapest first!")
                for deal in deals:
                    with st.container():
                        d_col1, d_col2 = st.columns([4, 1])
                        d_col1.write(f"**{deal['Title']}**")
                        d_col2.write(f"💰 **{deal['Price']}**")
                        st.markdown(f"[⚡ Instantly Open and Purchase Listing on eBay]({deal['Link']})")
                        st.markdown("---")
            else:
                st.warning("No active items found under your margin target right now. Try lowering your Target Sourcing Discount percentage to widen the search pool!")

elif search_input:
    st.info("Waiting for data string execution. If this hangs, verify spelling or append the specific console family to the input field.")

# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import requests
import time # Import time for potential rate limiting
import json # For passing data to JavaScript

# --- CoinGecko API Fetching ---
@st.cache_data(ttl=600) # Cache data for 10 minutes
def fetch_market_data(pages=2, retries=3, delay=5):
    """
    Fetches market data for top cryptocurrencies from CoinGecko API.

    Args:
        pages (int): Number of pages to fetch (250 results per page).
        retries (int): Number of retry attempts on failure.
        delay (int): Delay in seconds between retries.

    Returns:
        list: A list of dictionaries containing coin data (id, symbol, name, market_cap, market_cap_rank, current_price),
              or None if fetching fails after retries.
    """
    all_coins = []
    base_url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "24h" # Included for potential future use
    }

    # Placeholder for progress reporting within the function if needed
    # progress_placeholder = st.empty()

    for page in range(1, pages + 1):
        params["page"] = page
        attempt = 0
        # progress_placeholder.text(f"Fetching page {page}/{pages}...")
        while attempt < retries:
            try:
                headers = {'Accept': 'application/json'}
                response = requests.get(base_url, params=params, timeout=15, headers=headers)
                response.raise_for_status()
                data = response.json()
                if data:
                    all_coins.extend(data)
                    # Add a small delay to potentially avoid rate limits
                    time.sleep(0.5)
                    break
                else:
                    # Don't show warning for empty pages if it's not the first page
                    if page == 1:
                         st.warning(f"Received empty data from page {page}. Stopping fetch.")
                    break # Stop fetching if empty data received
            except requests.exceptions.RequestException as e:
                attempt += 1
                st.warning(f"API Error fetching page {page}: {e}. Attempt {attempt}/{retries}.")
                if attempt < retries:
                    time.sleep(delay)
                else:
                    st.error(f"Failed to fetch data from CoinGecko API after {retries} attempts.")
                    # progress_placeholder.empty()
                    return None

    # progress_placeholder.empty() # Clear progress text after fetching

    if not all_coins:
        st.error("No data fetched from CoinGecko API.")
        return None

    required_keys = ['id', 'symbol', 'name', 'market_cap', 'market_cap_rank', 'current_price']
    processed_coins = []
    skipped_coins_log = [] # Log skipped coins

    for coin in all_coins:
        # Ensure market_cap_rank exists and is not None before checking other keys
        # CoinGecko sometimes returns coins with null market_cap_rank far down the list
        if 'market_cap_rank' not in coin or coin.get('market_cap_rank') is None:
             skipped_coins_log.append(f"Skipped '{coin.get('id', 'Unknown ID')}' due to missing/null market_cap_rank")
             continue # Skip this coin entirely if rank is missing

        missing_keys = [key for key in required_keys if key not in coin or coin.get(key) is None]
        if not missing_keys:
             processed_coins.append({key: coin[key] for key in required_keys})
        else:
            # Log skipped coins instead of printing warnings for each one during fetch
            skipped_coins_log.append(f"Skipped '{coin.get('id', 'Unknown ID')}' (Rank: {coin.get('market_cap_rank', 'N/A')}) due to missing/null: {', '.join(missing_keys)}")

    # Display skipped coins summary once after processing
    if skipped_coins_log:
        with st.expander(f"Skipped {len(skipped_coins_log)} coins due to missing data (e.g., null market cap rank)"):
            # Show only a limited number initially
            MAX_SKIPPED_TO_SHOW = 20
            st.write("\n".join(skipped_coins_log[:MAX_SKIPPED_TO_SHOW]))
            if len(skipped_coins_log) > MAX_SKIPPED_TO_SHOW:
                st.caption(f"... and {len(skipped_coins_log) - MAX_SKIPPED_TO_SHOW} more.")


    return processed_coins


# --- Streamlit App ---

st.set_page_config(layout="wide") # Use wider layout

# App Title
st.title("🪙 BTC/Altcoin Market Cap Rebalancer")

# --- Input Widgets ---
st.subheader("Configuration")

# Use columns for better layout
col1, col2 = st.columns(2)

with col1:
    total_portfolio_usd = st.number_input(
        "Total Portfolio Value (USD)",
        min_value=0.0,
        value=100000.0,
        step=1000.0,
        format="%.2f",
        help="Enter the total value of your portfolio in USD."
    )
    btc_target_weight_percent = st.slider(
        "BTC Target Weight (%)",
        min_value=0.0, # Allow shorting up to 1x
        max_value=300.0,  # Allow leverage up to 2x
        value=150.0,
        step=0.1,
        help="Set the desired target weight for Bitcoin (e.g., -50 for 0.5x short, 150 for 1.5x leverage)."
    )
    alt_target_weight_percent = st.slider(
        "Altcoin Basket Target Weight (%)",
        min_value=0.0, # Allow shorting up to 1x
        max_value=300.0,  # Allow leverage up to 2x
        value=25.0,
        step=0.1,
        help="Set the desired target weight for the Altcoin Basket (e.g., -50 for 0.5x short, 150 for 1.5x leverage)."
    )


with col2:
    excluded_tokens_str = st.text_area(
        "Excluded Tokens (comma-separated, lowercase)",
        # UPDATED default list
        value="usdt,usdc,dai,tusd,busd,bsc-usd,fdusd,usdp,pyusd,usdd,frax,wbtc,wbt,leo,steth,wsteth,weth,usds,weeth,hype,wbeth,figr_heloc,usde",
        help="Enter token symbols (lowercase) to exclude. BTC is handled separately."
    )
    top_n_altcoins = st.number_input(
        "Number of Top Altcoins (N)",
        min_value=1,
        max_value=450, # Max reasonable number based on fetch (2*250 - potential skips)
        value=10,
        step=1,
        help="Select the number of top market cap altcoins for the basket."
    )


st.write("---") # Separator

# --- Calculation Logic ---
if st.button("🚀 Calculate Allocation"):

    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.info("Fetching market data from CoinGecko...")

    # Fetch data (using cache)
    # Fetch more pages to ensure enough data for larger reference table
    market_data = fetch_market_data(pages=3) # Fetch top 750 coins
    progress_bar.progress(20)

    if market_data:
        status_text.success("Market data fetched successfully. Processing...")
        try:
            df = pd.DataFrame(market_data)
            progress_bar.progress(30)

            # Data Cleaning and Type Conversion
            numeric_cols = ['market_cap', 'current_price', 'market_cap_rank']
            initial_rows = len(df)
            for col in numeric_cols:
                 df[col] = pd.to_numeric(df[col], errors='coerce')
            # Drop rows where ANY of the essential numeric columns are missing
            df.dropna(subset=numeric_cols, inplace=True)
            # Ensure market_cap_rank is integer after potential coercion/dropna
            df['market_cap_rank'] = df['market_cap_rank'].astype(int)
            cleaned_rows = len(df)
            if initial_rows > cleaned_rows:
                 st.caption(f"Removed {initial_rows - cleaned_rows} rows with missing numeric data during cleaning.")

            # Sort by rank AFTER cleaning to ensure correct order
            df.sort_values(by='market_cap_rank', ascending=True, inplace=True)
            progress_bar.progress(40)


            # --- Start Calculation for Altcoin Basket ---
            status_text.info("Calculating altcoin basket...")

            # 1. Parse Excluded Tokens
            excluded_tokens = set(t.strip().lower() for t in excluded_tokens_str.split(',') if t.strip())
            excluded_tokens.add('btc') # Ensure BTC is not in the altcoin basket

            # 2. Filter DataFrame
            # Use the cleaned and sorted df
            df_filtered = df[~df['symbol'].str.lower().isin(excluded_tokens)].copy()
            progress_bar.progress(50)


            if df_filtered.empty:
                st.warning("No altcoins remaining after filtering excluded tokens.")
                status_text.warning("Calculation complete: No altcoins remaining after filtering.")
                progress_bar.progress(100)
            else:
                # 3. Sort by Market Cap (already sorted by rank, which implies mcap order from API)
                # Re-sort just to be absolutely sure if needed, but rank sort should suffice
                # df_sorted = df_filtered.sort_values(by='market_cap', ascending=False) # Likely redundant now

                # 4. Select Top N Altcoins from the FILTERED list
                altcoin_basket = df_filtered.head(top_n_altcoins).copy()

                if altcoin_basket.empty:
                    st.warning(f"Could not select Top {top_n_altcoins} altcoins after filtering.")
                    status_text.warning(f"Calculation complete: Could not select Top {top_n_altcoins} altcoins after filtering.")
                    progress_bar.progress(100)
                else:
                    # 5. Calculate Target USD Allocations
                    target_btc_usd = total_portfolio_usd * (btc_target_weight_percent / 100.0)
                    target_altcoin_basket_usd = total_portfolio_usd * (alt_target_weight_percent / 100.0)

                    # 6. Calculate Total Market Cap of Basket
                    total_altcoin_basket_market_cap = altcoin_basket['market_cap'].sum()
                    progress_bar.progress(60)

                    if total_altcoin_basket_market_cap > 0:
                        # 7. Calculate Weight & Target USD within Alt Basket
                        altcoin_basket['Weight (%)'] = \
                            (altcoin_basket['market_cap'] / total_altcoin_basket_market_cap) * 100
                        # Calculate Target USD for each altcoin based on its weight within the *altcoin portion* of the portfolio
                        altcoin_basket['Target Allocation (USD)'] = \
                            (altcoin_basket['Weight (%)'] / 100.0) * target_altcoin_basket_usd

                        progress_bar.progress(70)

                        # 8. Create Final DataFrame for Display
                        display_df = altcoin_basket[[
                            'symbol', 'name', 'current_price', 'market_cap', 'Weight (%)', 'Target Allocation (USD)', 'market_cap_rank'
                        ]].copy() # Include name and rank

                        # Add Basket Rank (1 to N) - based on filtered list order
                        display_df.reset_index(drop=True, inplace=True)
                        display_df.index = display_df.index + 1
                        display_df.insert(0, 'Basket Rank', display_df.index)

                        # Rename and Format Columns
                        display_df.rename(columns={
                            'symbol': 'Symbol',
                            'name': 'Name',
                            'current_price': 'Price (USD)',
                            'market_cap': 'Market Cap (USD)',
                            'Weight (%)': 'Weight within Basket (%)', # Clarify weight context
                            'market_cap_rank': 'Overall Rank' # Show original rank
                        }, inplace=True)

                        display_df['Symbol'] = display_df['Symbol'].str.upper()
                        # Apply formatting and add copy buttons
                        # Price (USD) - original value is float, revert to decimal formatting, no copy button
                        display_df['Price (USD)'] = display_df['Price (USD)'].map(
                            lambda x: f"{x:,.4f}" if pd.notnull(x) else ''
                        )
                        # Market Cap (USD) - original value is float/int, revert to formatted number, no copy button
                        display_df['Market Cap (USD)'] = display_df['Market Cap (USD)'].map(
                            lambda x: f"{x:,.0f}" if pd.notnull(x) else ''
                        )
                        # Weight within Basket (%) - Retain original formatting as it's a percentage
                        display_df['Weight within Basket (%)'] = display_df['Weight within Basket (%)'].map('{:.2f}%'.format)
                        
                        # Target Allocation (USD) - Will be handled by iterating and displaying with st.button
                        # Format as whole number string for potential display if not using Option A for table
                        display_df['Target Allocation (USD)'] = display_df['Target Allocation (USD)'].apply(
                            lambda x: str(int(float(x))) if pd.notnull(x) else ''
                        )

                        # Reorder columns for better display
                        display_df = display_df[[
                            'Basket Rank', 'Symbol', 'Name', 'Overall Rank',
                            'Price (USD)', 'Market Cap (USD)', 'Weight within Basket (%)',
                            'Target Allocation (USD)'
                        ]]

                        # Set Basket Rank as Index for cleaner display
                        display_df.set_index('Basket Rank', inplace=True)
                        progress_bar.progress(85)

                        # 9. Display Results
                        st.subheader("🎯 Target Allocation Summary")
                        col_alloc1, col_alloc2 = st.columns(2)

                        # BTC Target Allocation Metric
                        target_btc_usd_int = int(target_btc_usd)
                        btc_value_to_copy = str(target_btc_usd_int)
                        btc_delta_color_css = "green" if target_btc_usd >= 0 else "red"

                        with col_alloc1:
                            st.markdown(f"**BTC Target Weight**: {btc_target_weight_percent}%")
                            col1_c1, col1_c2 = st.columns([3,1])
                            with col1_c1:
                                st.markdown(f'<span style="font-size: 1.1rem; color: {btc_delta_color_css};">{btc_value_to_copy} USD</span>', unsafe_allow_html=True)
                            with col1_c2:
                                pass # Placeholder for potential future button


                        # Altcoin Basket Target Allocation Metric
                        target_alt_usd_int = int(target_altcoin_basket_usd)
                        alt_value_to_copy = str(target_alt_usd_int)
                        alt_delta_color_css = "green" if target_altcoin_basket_usd >= 0 else "red"

                        with col_alloc2:
                            st.markdown(f"**Altcoin Basket Target Weight**: {alt_target_weight_percent}%")
                            col2_c1, col2_c2 = st.columns([3,1])
                            with col2_c1:
                                st.markdown(f'<span style="font-size: 1.1rem; color: {alt_delta_color_css};">{alt_value_to_copy} USD</span>', unsafe_allow_html=True)
                            with col2_c2:
                                pass # Placeholder for potential future button

                        st.write("---")
                        st.subheader(f"💰 Calculated Altcoin Basket (Top {len(display_df)} Filtered)")
                        # Display dataframe by iterating and using st.columns for Option A
                        # Header for the custom table
                        header_cols = st.columns([1, 2, 3, 2, 3, 3, 3, 4]) # Adjusted for Basket Rank
                        column_names = ['Basket Rank', 'Symbol', 'Name', 'Overall Rank', 'Price (USD)', 'Market Cap (USD)', 'Weight within Basket (%)', 'Target Allocation (USD)']
                        for col, name in zip(header_cols, column_names):
                            col.markdown(f"**{name}**")

                        for index, row in display_df.iterrows():
                            cols = st.columns([1, 2, 3, 2, 3, 3, 3, 4]) # Adjusted for Basket Rank
                            cols[0].write(index) # Basket Rank (already index)
                            cols[1].write(row['Symbol'])
                            cols[2].write(row['Name'])
                            cols[3].write(row['Overall Rank'])
                            cols[4].write(row['Price (USD)'])
                            cols[5].write(row['Market Cap (USD)'])
                            cols[6].write(row['Weight within Basket (%)'])
                            
                            target_alloc_usd_val = row['Target Allocation (USD)'] # This is already a formatted string
                            
                            # Use a sub-column for the value and button to align them
                            val_col, btn_col = cols[7].columns([3,1])
                            val_col.write(target_alloc_usd_val)
                            
                            button_key = f"copy_table_row_{index}_{row['Symbol']}"
                            # Placeholder for potential future button in row
                            st.markdown("---") # Visual separator between rows

                        # Display total market cap of the basket, revert to original formatting (no copy button)
                        formatted_total_mcap_basket = f"{total_altcoin_basket_market_cap:,.0f}"
                        st.markdown(f"""
                            <div style="margin-top:10px;">
                                **Total Market Cap of Displayed Altcoin Basket:** {formatted_total_mcap_basket} USD
                            </div>
                            """, unsafe_allow_html=True)

                        # --- Display Reference Table (Top N Raw Data) ---
                        # INCREASE the number of coins shown in the reference table
                        num_ref_coins = max(top_n_altcoins + 20, 50) # Show at least 50, or N + 20
                        num_ref_coins = min(num_ref_coins, len(df)) # Don't try to show more than available

                        st.subheader(f"📊 Reference: Top {num_ref_coins} Fetched Coins (Raw Data Before Filtering)")
                        # Use the original cleaned & sorted df for reference
                        ref_df = df.head(num_ref_coins).copy()
                        ref_df_display = ref_df[['market_cap_rank', 'symbol', 'name', 'current_price', 'market_cap']].copy()
                        ref_df_display.rename(columns={
                            'market_cap_rank': 'Overall Rank',
                            'symbol': 'Symbol',
                            'name': 'Name',
                            'current_price': 'Price (USD)',
                            'market_cap': 'Market Cap (USD)'
                        }, inplace=True)
                        ref_df_display['Symbol'] = ref_df_display['Symbol'].str.upper()
                        # Apply formatting, revert to original formatting (no copy button)
                        ref_df_display['Price (USD)'] = ref_df_display['Price (USD)'].map(
                            lambda x: f"{x:,.4f}" if pd.notnull(x) else ''
                        )
                        ref_df_display['Market Cap (USD)'] = ref_df_display['Market Cap (USD)'].map(
                            lambda x: f"{x:,.0f}" if pd.notnull(x) else ''
                        )
                        ref_df_display.set_index('Overall Rank', inplace=True)
                        # Display reference dataframe as HTML table (no changes needed here for copy functionality)
                        st.markdown(ref_df_display.to_html(escape=False, index=True, classes='custom_table'), unsafe_allow_html=True)
                        
                        st.write("---")
                        status_text.success("Calculation complete!")
                        progress_bar.progress(100)
                        time.sleep(0.5) # Keep success message visible briefly
                        progress_bar.empty() # Remove progress bar

                    else:
                        st.warning("Total market cap of the selected altcoin basket is zero. Cannot calculate weights or USD allocation.")
                        status_text.warning("Calculation complete: Basket market cap is zero.")
                        progress_bar.progress(100)
                        time.sleep(0.5)
                        progress_bar.empty()

        except KeyError as e:
             st.error(f"Calculation Error: Missing expected data column: '{e}'. This might happen if CoinGecko API response changed.")
             st.exception(e)
             status_text.error("Calculation failed due to missing data.")
             if 'progress_bar' in locals(): progress_bar.empty()
        except Exception as e:
            st.error(f"An unexpected error occurred during calculation: {e}")
            st.exception(e) # Show traceback for debugging
            status_text.error("Calculation failed.")
            if 'progress_bar' in locals(): progress_bar.empty()

    else:
        st.error("Could not proceed with calculation due to data fetching issues.")
        status_text.error("Data fetching failed.")
        if 'progress_bar' in locals(): progress_bar.empty()


# Optional: Add a footer or link
st.markdown("---")
st.markdown("Data sourced from [CoinGecko API](https://www.coingecko.com/en/api)")
st.caption("Disclaimer: This tool is for informational purposes only and does not constitute financial advice.")

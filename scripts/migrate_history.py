import json
import csv
import re
import os
from datetime import datetime

# Configuration
RESULT_JSON_PATH = r"C:\Projek\Bot Trading\Bot-Trading-Easy-Peasy\result.json"
CSV_OUTPUT_PATH = r"C:\Projek\Bot Trading\Bot-Trading-Easy-Peasy\streamlit\data\trade_history.csv"

def parse_message_text(message):
    if "text" not in message:
        return ""
    
    text_content = message["text"]
    if isinstance(text_content, list):
        full_text = ""
        for item in text_content:
            if isinstance(item, str):
                full_text += item
            elif isinstance(item, dict) and "text" in item:
                full_text += item["text"]
        return full_text
    elif isinstance(text_content, str):
        return text_content
    return ""

def main():
    print(f"Loading {RESULT_JSON_PATH}...")
    try:
        with open(RESULT_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: result.json not found.")
        return

    messages = data.get("messages", [])
    print(f"Found {len(messages)} messages.")

    trades = []
    # Dictionary to track active signals by symbol: {symbol: trade_dict}
    # We assume one active signal per symbol at a time for simplicity in this log parsing
    active_orders = {}

    for msg in messages:
        text = parse_message_text(msg)
        timestamp_str = msg.get("date", "")
        
        # 1. Detect AI SIGNAL MATCHED
        if "AI SIGNAL MATCHED" in text:
            try:
                symbol_match = re.search(r"Coin: (\w+/\w+)", text)
                side_match = re.search(r"Signal: \W+ (BUY|SELL)", text)
                strategy_match = re.search(r"Strategy: (.+)", text)
                entry_match = re.search(r"Entry: ([\d.]+)", text)
                size_match = re.search(r"Size: \$([\d.]+)", text)
                reason_match = re.search(r"Reason:\n(.+?)(?=\n\n⚠️|\Z)", text, re.DOTALL)
                
                if symbol_match and side_match:
                    symbol = symbol_match.group(1)
                    parsed_trade = {
                        "timestamp": timestamp_str,
                        "symbol": symbol,
                        "side": side_match.group(1),
                        "type": "LIMIT",
                        "entry_price": entry_match.group(1) if entry_match else "0",
                        "exit_price": "0",
                        "size_usdt": size_match.group(1) if size_match else "0",
                        "pnl_usdt": "0",
                        "pnl_percent": "0",
                        "roi_percent": "0",
                        "fee": "0",
                        "strategy_tag": strategy_match.group(1) if strategy_match else "Unknown",
                        "result": "SIGNAL", # Changed from PENDING
                        "prompt": "",
                        "reason": reason_match.group(1).strip() if reason_match else "",
                        "setup_at": timestamp_str,
                        "filled_at": ""
                    }
                    active_orders[symbol] = parsed_trade
            except Exception as e:
                print(f"Error parsing signal msg {msg.get('id')}: {e}")

        # 2. Detect LIMIT PLACED
        elif "LIMIT PLACED" in text:
            symbol_match = re.search(r"(\w+/\w+) (buy|sell) @", text, re.IGNORECASE)
            if symbol_match:
                symbol = symbol_match.group(1)
                if symbol in active_orders:
                    active_orders[symbol]["result"] = "PLACED"

        # 3. Detect FILLED
        elif "ENTRY FILLED" in text:
            symbol_match = re.search(r"✨ (\w+/\w+)", text)
            if symbol_match:
                symbol = symbol_match.group(1)
                if symbol in active_orders:
                    active_orders[symbol]["result"] = "OPEN"
                    active_orders[symbol]["filled_at"] = timestamp_str

        # 4. Detect HIT (TP/SL)
        elif "HIT" in text and ("STOP LOSS" in text or "TAKE PROFIT" in text):
            symbol_match = re.search(r"✨ (\w+/\w+)", text)
            if symbol_match:
                symbol = symbol_match.group(1)
                if symbol in active_orders:
                    trade = active_orders.pop(symbol)
                    
                    # Extract result details
                    is_tp = "TAKE PROFIT" in text
                    trade["result"] = "WIN" if is_tp else "LOSS"
                    
                    price_match = re.search(r"Price: ([\d.]+)", text)
                    pnl_match = re.search(r"PnL: ([+-]?\$?[\d.]+)", text)
                    roi_match = re.search(r"ROI: ([+-]?[\d.]+)%", text)
                    
                    if price_match:
                        trade["exit_price"] = price_match.group(1)
                    if pnl_match:
                        # Remove $ if present
                        pnl_str = pnl_match.group(1).replace("$", "")
                        trade["pnl_usdt"] = pnl_str
                        trade["pnl_percent"] = pnl_str # Rough estimate if not available
                    if roi_match:
                        trade["roi_percent"] = roi_match.group(1)
                    
                    trades.append(trade)

        # 5. Detect ORDER SYNC / EXPIRED / CANCELLED
        elif "ORDER SYNC" in text or "ORDER EXPIRED" in text or "cancelled manually" in text:
            symbol_match = re.search(r"Order for (\w+/\w+)", text)
            if not symbol_match: # Try direct symbol search
                 symbol_match = re.search(r"(\w+/\w+)", text)
            
            if symbol_match:
                symbol = symbol_match.group(1)
                if symbol in active_orders:
                    status = "EXPIRED" if "EXPIRED" in text or "timeout" in text else "CANCELLED"
                    active_orders[symbol]["result"] = status
                    trades.append(active_orders.pop(symbol))
        
        # 4. Handle generic stops (Bot Stopped Manually) - optional
        # If bot stops, maybe all pending open orders are effectively cancelled/safe to ignore? 
        # For now, we only process explicit cancellations to be safe, or leave them as OPEN if no cancel msg found.

    # Add any remaining active orders (OPEN or PENDING) to trades list
    for symbol, trade in active_orders.items():
        if trade["result"] == "PENDING":
             trade["result"] = "IGNORED" # Signal without placement? Or just PENDING
        trades.append(trade)

    # Sort trades by timestamp
    trades.sort(key=lambda x: x["timestamp"])

    # Write to CSV
    csv_headers = [
        "timestamp", "symbol", "side", "type", "entry_price", "exit_price",
        "size_usdt", "pnl_usdt", "pnl_percent", "roi_percent", "fee",
        "strategy_tag", "result", "prompt", "reason", "setup_at", "filled_at"
    ]

    print(f"Writing {len(trades)} trades to {CSV_OUTPUT_PATH}...")
    
    # Create directory if needed
    os.makedirs(os.path.dirname(CSV_OUTPUT_PATH), exist_ok=True)

    with open(CSV_OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        for trade in trades:
            writer.writerow(trade)

    print("Migration complete.")

if __name__ == "__main__":
    main()

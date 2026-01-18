import config

def calculate_trade_scenarios(price, atr, side, precision=4):
    """
    Menghitung skenario trade untuk Market (Aggressive) vs Liquidity Hunt (Passive).
    
    Args:
        price (float): Harga saat ini (Current Price).
        atr (float): Nilai ATR saat ini.
        side (str): 'BUY' atau 'SELL'.
        precision (int): Desimal untuk pembulatan harga.
        
    Returns:
        dict: {
            "market": {entry, sl, tp, rr},
            "liquidity_hunt": {entry, sl, tp, rr}
        }
    """
    scenarios = {}
    
    # --- 1. MARKET SCENARIO (Aggressive) ---
    # Entry: Current Price
    # SL: Price - (ATR * SL_Multiplier)
    # TP: Price + (ATR * TP_Multiplier)
    
    m_entry = price
    m_dist_sl = atr * config.ATR_MULTIPLIER_SL
    m_dist_tp = atr * config.ATR_MULTIPLIER_TP1
    
    if side.upper() == 'BUY':
        m_sl = m_entry - m_dist_sl
        m_tp = m_entry + m_dist_tp
    else: # SELL
        m_sl = m_entry + m_dist_sl
        m_tp = m_entry - m_dist_tp
        
    m_rr = m_dist_tp / m_dist_sl if m_dist_sl > 0 else 0
    
    scenarios['market'] = {
        "entry": round(m_entry, precision),
        "sl": round(m_sl, precision),
        "tp": round(m_tp, precision),
        "rr": round(m_rr, 2)
    }
    
    # --- 2. LIQUIDITY HUNT SCENARIO (Passive) ---
    # Entry: Limit Order at Market SL level (Sweeping the stops)
    # SL: Baru (New Entry - Buffer)
    # TP: Balik ke arah tren (Bisa pakai TP Market tadi atau dihitung ulang)
    
    # Logic: Kita pasang antrian jaring di tempat orang lain kena SL.
    # Entry Hunt = SL Market (kurang lebih)
    h_dist_entry_offset = atr * config.ATR_MULTIPLIER_SL # Jarak dari harga skrg ke "SL Orang"
    
    # New Safety for Hunt (Buffer setelah kena sweep)
    # config.TRAP_SAFETY_SL biasanya lebih kecil/ketat karena sudah dapat harga pucuk
    h_dist_sl_safety = atr * config.TRAP_SAFETY_SL 
    h_dist_tp_reward = atr * config.ATR_MULTIPLIER_TP1 # Kita samakan reward distance-nya
    
    if side.upper() == 'BUY':
        # Kita mau BUY di bawah (di harga SL Market Buy orang lain)
        h_entry = price - h_dist_entry_offset 
        h_sl = h_entry - h_dist_sl_safety
        h_tp = h_entry + h_dist_tp_reward
    else:
        # Kita mau SELL di atas (di harga SL Market Sell orang lain)
        h_entry = price + h_dist_entry_offset
        h_sl = h_entry + h_dist_sl_safety
        h_tp = h_entry - h_dist_tp_reward
        
    h_rr = h_dist_tp_reward / h_dist_sl_safety if h_dist_sl_safety > 0 else 0
    
    scenarios['liquidity_hunt'] = {
        "entry": round(h_entry, precision),
        "sl": round(h_sl, precision),
        "tp": round(h_tp, precision),
        "rr": round(h_rr, 2)
    }
    
    return scenarios

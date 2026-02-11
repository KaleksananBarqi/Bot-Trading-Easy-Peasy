
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from io import BytesIO
import os

def create_pnl_card(trade_data):
    """
    Generate PnL card image from trade data using Pillow.
    
    Args:
        trade_data (dict): Dictionary with trade details:
            - symbol (str): e.g., 'BTC/USDT'
            - side (str): 'LONG' or 'SHORT'
            - entry_price (float)
            - exit_price (float)
            - pnl_usdt (float)
            - roi_percent (float)
            - timestamp (datetime)
            - leverage (int/str)
            
    Returns:
        BytesIO: Image buffer containing the PNG image.
    """
    # Canvas Settings
    img_width = 800
    img_height = 1000  # Adjusted for better aspect ratio
    
    # Colors
    bg_color = (26, 26, 26)  # #1a1a1a
    card_bg_color = (13, 13, 13) # #0d0d0d
    text_white = (255, 255, 255)
    text_grey = (136, 136, 136) # #888
    
    roi = float(trade_data.get('roi_percent', 0))
    is_win = roi >= 0
    
    accent_color = (0, 255, 136) if is_win else (255, 75, 75) # Green / Red
    
    # Initialize Image
    img = Image.new('RGB', (img_width, img_height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # --- Fonts ---
    # Try to load Arial or generic fonts
    try:
        font_large = ImageFont.truetype("arial.ttf", 80)
        font_medium = ImageFont.truetype("arial.ttf", 40)
        font_small = ImageFont.truetype("arial.ttf", 25)
        font_bold = ImageFont.truetype("arialbd.ttf", 40)
        font_roi = ImageFont.truetype("arialbd.ttf", 100) # Big ROI
    except IOError:
        # Fallback to default if arial not found
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_bold = ImageFont.load_default()
        font_roi = ImageFont.load_default()

    # --- Background Decoration ---
    # Gradient-like effect or simple shapes
    # Draw a colored circle/glow at top right
    glow_size = 300
    glow_bg = Image.new('RGBA', (glow_size, glow_size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_bg)
    glow_draw.ellipse((0, 0, glow_size, glow_size), fill=(accent_color[0], accent_color[1], accent_color[2], 50))
    glow_bg = glow_bg.filter(ImageFilter.GaussianBlur(radius=50))
    img.paste(glow_bg, (img_width - 200, -100), glow_bg)
    
    
    # --- Content Layout ---
    padding = 60
    current_y = padding
    
    # 1. Header: Symbol
    symbol = trade_data.get('symbol', 'UNKNOWN')
    draw.text((padding, current_y), symbol, font=font_large, fill=text_white)
    
    # Perpetual Tag (simulated pill)
    tag_text = "Perpetual"
    tag_width = 150 
    tag_height = 40
    tag_x = padding + 450 # Approx position next to symbol or right aligned
    tag_y = current_y + 20
    
    # Right align the bot name
    bot_name = "Bot EzPeasy"
    bbox = draw.textbbox((0, 0), bot_name, font=font_small)
    text_width = bbox[2] - bbox[0]
    draw.text((img_width - padding - text_width, current_y + 25), bot_name, font=font_small, fill=text_grey)

    current_y += 120
    
    # 2. Side & Leverage
    side = trade_data.get('side', 'LONG').capitalize()
    leverage = trade_data.get('leverage', '1x')
    
    side_text = f"{side} | {leverage}X"
    draw.text((padding, current_y), side_text, font=font_bold, fill=accent_color)
    
    current_y += 100
    
    # 3. ROI Section
    draw.text((padding, current_y), "Return on Investment (ROI)", font=font_small, fill=text_grey)
    current_y += 40
    roi_text = f"{roi:+.2f}%"
    draw.text((padding, current_y), roi_text, font=font_roi, fill=accent_color)
    
    current_y += 150
    
    # 4. Prices (Grid Layout)
    entry = float(trade_data.get('entry_price', 0))
    exit_p = float(trade_data.get('exit_price', 0))
    
    # Left: Entry
    draw.text((padding, current_y), "Entry Price", font=font_small, fill=text_grey)
    draw.text((padding, current_y + 35), f"{entry:,.4f}", font=font_medium, fill=text_white)
    
    # Right: Exit
    # Calculate text width to align right
    exit_lbl = "Exit Price"
    exit_val = f"{exit_p:,.4f}"
    
    bbox_lbl = draw.textbbox((0, 0), exit_lbl, font=font_small)
    w_lbl = bbox_lbl[2] - bbox_lbl[0]
    
    bbox_val = draw.textbbox((0, 0), exit_val, font=font_medium)
    w_val = bbox_val[2] - bbox_val[0]
    
    draw.text((img_width - padding - w_lbl, current_y), exit_lbl, font=font_small, fill=text_grey)
    draw.text((img_width - padding - w_val, current_y + 35), exit_val, font=font_medium, fill=text_white)
    
    current_y += 120
    
    # Divider Line
    draw.line((padding, current_y, img_width - padding, current_y), fill=(50, 50, 50), width=2)
    current_y += 40
    
    # 5. Footer
    date_str = trade_data.get('timestamp').strftime('%Y-%m-%d %H:%M:%S')
    draw.text((padding, current_y), "Automated by", font=font_small, fill=text_grey)
    current_y += 30
    draw.text((padding, current_y), "Bot Trading Easy Peasy", font=font_bold, fill=text_white)
    current_y += 50
    draw.text((padding, current_y), date_str, font=font_small, fill=text_grey)
    
    # Placeholder for QR Code (White box)
    qr_size = 120
    qr_x = img_width - padding - qr_size
    qr_y = current_y - 50 # Align with text block
    draw.rectangle([qr_x, qr_y, qr_x + qr_size, qr_y + qr_size], fill="white")
    
    # Add simple text in QR box
    draw.text((qr_x + 10, qr_y + 50), "QR Code", font=ImageFont.load_default(), fill="black")

    # Save to BytesIO
    img_buffer = BytesIO()
    img.save(img_buffer, format="PNG")
    img_buffer.seek(0)
    
    return img_buffer

if __name__ == '__main__':
    # Test Block
    from datetime import datetime
    dummy_data = {
        'symbol': 'BTC/USDT',
        'side': 'LONG',
        'entry_price': 65000.50,
        'exit_price': 67500.00,
        'pnl_usdt': 250.00,
        'roi_percent': 15.50,
        'timestamp': datetime.now(),
        'leverage': 30
    }
    img = create_pnl_card(dummy_data)
    with open("test_card.png", "wb") as f:
        f.write(img.getbuffer())
    print("Test image saved to test_card.png")


import json
import os
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np
import sys

# Ensure src module can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if project_root not in sys.path:
    sys.path.append(project_root)

# Try Logger Import
try:
    from src.utils.helper import logger
except ImportError:
    import logging
    logger = logging.getLogger("PnLGenerator")

# Coba import qrcode, jika tidak ada, gunakan placeholder
try:
    import qrcode
except ImportError:
    try:
        from src.utils.helper import logger
        logger.warning("⚠️ Library 'qrcode' not found. QR code generation disabled.")
    except:
        print("⚠️ Library 'qrcode' not found. QR code generation disabled.")
    qrcode = None

class CryptoPnLGenerator:
    def __init__(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.config_path = os.path.join(os.path.dirname(__file__), 'pnl_config.json')
        self.config = self._load_config()
        self._ensure_asset_dirs()
        self._load_fonts()
        
    def _load_config(self):
        """Memuat konfigurasi dari file JSON."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            # Default fallback config jika file hilang
            return {}

    def _ensure_asset_dirs(self):
        """Memastikan direktori aset ada."""
        assets_dir = os.path.join(self.base_dir, 'assets')
        os.makedirs(os.path.join(assets_dir, 'fonts'), exist_ok=True)
        os.makedirs(os.path.join(assets_dir, 'icons'), exist_ok=True)

    def _get_asset_path(self, relative_path):
        """Mendapatkan absolute path untuk aset."""
        if not relative_path:
            return None
        return os.path.join(self.base_dir, relative_path)

    def _load_fonts(self):
        """Memuat font dari konfigurasi atau fallback ke default sistem."""
        fonts_cfg = self.config.get('fonts', {})
        
        # Mapping font type ke path
        self.fonts = {}
        
        # Helper untuk memuat font dengan ukuran tertentu
        def load_font(key, size, fallback_key=None):
            # 1. Coba load dari config user (Local Assets)
            font_path_rel = fonts_cfg.get(key)
            if font_path_rel:
                full_path = self._get_asset_path(font_path_rel)
                if os.path.exists(full_path):
                    try: return ImageFont.truetype(full_path, size)
                    except: pass
            
            # 2. Coba load font fallback dari sistem (Windows specific hardcoded fallback for common fonts)
            # Ini untk memberikan hasil yang lebih baik daripada 'default' pixelated font
            base_font = "arial.ttf"
            if "bold" in key or (fallback_key and "bold" in fallback_key): 
                base_font = "arialbd.ttf"
            
            try:
                return ImageFont.truetype(base_font, size)
            except:
                return ImageFont.load_default()

        self.font_loader = load_font

    def _hex_to_rgb(self, hex_color):
        """Konversi HEX ke RGB/RGBA. Supports #RGB, #RGBA, #RRGGBB and #RRGGBBAA"""
        hex_color = hex_color.lstrip('#')
        # Expand shorthand: #RGB → #RRGGBB, #RGBA → #RRGGBBAA
        if len(hex_color) in (3, 4):
            hex_color = ''.join(c * 2 for c in hex_color)
        if len(hex_color) == 8:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4, 6))
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def _create_gradient_bg(self, width, height, colors):
        """Membuat background gradient vertikal."""
        bg_rgb = [self._hex_to_rgb(c) for c in colors]
        base = Image.new('RGB', (width, height), bg_rgb[0])
        
        def create_two_color_gradient(c1, c2, w, h):
            base = Image.new('RGB', (w, h), c1)
            top = Image.new('RGB', (w, h), c2)
            gradient = np.linspace(0, 255, h, dtype=np.uint8)
            mask_data = np.repeat(gradient, w).tolist()
            mask = Image.new('L', (w, h))
            mask.putdata(mask_data)
            return Image.composite(top, base, mask)

        num_sections = len(bg_rgb) - 1
        if num_sections < 1: return base
        
        section_height = height // num_sections
        full_img = Image.new('RGB', (width, height))
        
        for i in range(num_sections):
            c1 = bg_rgb[i]
            c2 = bg_rgb[i+1]
            h = section_height
            if i == num_sections - 1:
                h = height - (section_height * i)
            grad_chunk = create_two_color_gradient(c1, c2, width, h)
            full_img.paste(grad_chunk, (0, section_height * i))
            
        return full_img

    def generate_card(self, trade_data):
        """
        Membuat gambar PnL Card.
        """
        style = self.config.get('style', {})
        card_setting = self.config.get('card_settings', {})
        
        # Determine dimensions based on config or default logic
        width = card_setting.get('width', 1920)
        height = card_setting.get('height', 1080)
        margin = card_setting.get('margin', 60)
        
        # 1. Background
        bg_colors = style.get('bg_gradient_colors', ['#1E2329'])
        img = self._create_gradient_bg(width, height, bg_colors)
        
        # Check Layout Mode
        is_landscape = width > height
        
        if is_landscape:
            self._draw_landscape_layout(img, width, height, margin, trade_data)
        else:
            # Fallback/Legacy Portrait Mode (Just in case)
            draw = ImageDraw.Draw(img)
            self._draw_header(img, draw, width, margin)
            self._draw_stats(img, draw, width, height, margin, trade_data)
            self._draw_footer(img, draw, width, height, margin)
        
        # Watermark (layer terakhir, di atas semua konten)
        self._draw_watermark(img, width, height)
        
        # Return as BytesIO
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        return img_buffer

    def _draw_landscape_layout(self, img, width, height, margin, data):
        """Menggambar layout landscape dengan 2 panel + footer horizontal."""
        style = self.config.get('style', {})
        user_cfg = self.config.get('user', {})
        images_cfg = self.config.get('images', {})
        
        # --- Config & Colors ---
        text_primary = self._hex_to_rgb(style.get('text_primary', '#FFFFFF'))
        text_secondary = self._hex_to_rgb(style.get('text_secondary', '#AAAAAA'))
        
        up_color = self._hex_to_rgb(style.get('up_color', '#2EBD85'))
        down_color = self._hex_to_rgb(style.get('down_color', '#F6465D'))
        
        # --- Right Panel Background (dinamis berdasarkan rasio gambar) ---
        footer_height = 160  # Area footer di bagian bawah
        panel_content_h = height - footer_height
        
        # Hitung lebar panel berdasarkan gambar (atau fallback 35%)
        right_panel_width = self._calc_panel_width(width, panel_content_h)
        right_panel_x = width - right_panel_width
        
        # Draw right panel (custom image or color overlay)
        self._draw_right_panel_bg(img, right_panel_x, 0, right_panel_width, panel_content_h)
        
        # Draw footer background (subtle separator)
        footer_y = height - footer_height
        footer_overlay = Image.new('RGBA', (width, footer_height), (0, 0, 0, 0))
        footer_draw = ImageDraw.Draw(footer_overlay)
        footer_draw.rectangle([(0, 0), (width, footer_height)], fill=(0, 0, 0, 80))
        img_rgba = img.convert('RGBA')
        img_rgba.paste(Image.alpha_composite(
            img_rgba.crop((0, footer_y, width, height)),
            footer_overlay
        ), (0, footer_y))
        img.paste(img_rgba, (0, 0))
        
        # Separator line above footer
        draw = ImageDraw.Draw(img)
        draw.line([(margin, footer_y), (width - margin, footer_y)], 
                  fill=self._hex_to_rgb(style.get('text_tertiary', '#5E6673')), width=2)
        
        # --- 1. User Info (Top Left) ---
        self._draw_user_info(img, draw, margin, margin)
        
        # --- 2. Exchange Logo (Top Right) ---
        self._draw_logo(img, width - margin, margin + 20)
        
        # --- 3. Main Stats (Left Panel) ---
        symbol = data.get('symbol', 'BTC/USDT').replace('/', '')
        side = data.get('side', 'LONG').upper()
        leverage = data.get('leverage', 20)
        roi = float(data.get('roi_percent', 0))
        pnl = float(data.get('pnl_usdt', 0))
        is_win = roi >= 0
        roi_color = up_color if is_win else down_color
        badge_color = up_color if side in ["LONG", "BUY"] else down_color
        
        # Symbol Title
        font_symbol = self.font_loader('bold', 72, fallback_key='bold')
        draw.text((margin, 250), f"{symbol} Perpetual", font=font_symbol, fill=text_primary)
        
        # Side + Leverage Badge
        font_side = self.font_loader('bold', 36, fallback_key='bold')
        side_text = f"{side} {leverage}x"
        bbox = draw.textbbox((0, 0), side_text, font=font_side)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        pad_x, pad_y = 25, 12
        w_badge = text_w + pad_x * 2
        h_badge = text_h + pad_y * 2
        badge_x = margin
        badge_y = 360
        
        draw.rounded_rectangle(
            (badge_x, badge_y, badge_x + w_badge, badge_y + h_badge),
            radius=10,
            fill=self._hex_to_rgb(style.get('leverage_bg_color', '#333'))
        )
        # Kompensasi offset font metrics agar teks center di badge
        text_offset_x = -bbox[0]
        text_offset_y = -bbox[1]
        draw.text((badge_x + pad_x + text_offset_x, badge_y + pad_y + text_offset_y), side_text, font=font_side, fill=badge_color)
        
        # ROI (Big Number)
        font_roi = self.font_loader('data_bold', 180, fallback_key='bold')
        roi_str = f"{roi:+.2f}%"
        draw.text((margin, 440), roi_str, font=font_roi, fill=roi_color)
        
        # PnL Value
        font_pnl = self.font_loader('data_regular', 60, fallback_key='regular')
        pnl_str = f"{pnl:+.4f} USDT"
        draw.text((margin, 680), pnl_str, font=font_pnl, fill=text_primary)
        
        # Strategy Name
        strategy_name = data.get('strategy', 'Unknown Strategy').replace('_', ' ')
        font_strat = self.font_loader('regular', 32, fallback_key='regular')
        draw.text((margin, 755), strategy_name, font=font_strat, fill=text_secondary)
        
        # Tagline - Bot Trading with AI Integration (hardcoded, standout)
        accent_color = self._hex_to_rgb(style.get('accent_color', '#F0B90B'))
        font_tagline = self.font_loader('bold', 28, fallback_key='bold')
        draw.text((margin, 800), "Bot Trading with AI Integration", font=font_tagline, fill=accent_color)
        
        # GitHub URL (hardcoded)
        font_url = self.font_loader('regular', 24, fallback_key='regular')
        draw.text((margin, 838), "github.com/KaleksananBarqi/Bot-Trading-Easy-Peasy", font=font_url, fill=text_secondary)
        
        # --- 4. Horizontal Footer (Entry, Last, Referral, QR) ---
        entry = float(data.get('entry_price', 0))
        exit_price = float(data.get('exit_price', 0))
        
        font_label = self.font_loader('regular', 26, fallback_key='regular')
        font_val = self.font_loader('data_bold', 38, fallback_key='bold')
        
        # Divide footer into 4 columns
        usable_width = width - (margin * 2)
        qr_size = 120
        # Col widths: entry, last, ref take equal space, QR gets fixed
        col_text_width = (usable_width - qr_size - 40) // 3
        
        footer_text_y = footer_y + 25
        footer_val_y = footer_y + 65
        
        # Col 1: Entry Price
        col1_x = margin
        draw.text((col1_x, footer_text_y), "Entry Price", font=font_label, fill=text_secondary)
        draw.text((col1_x, footer_val_y), f"{entry:,.4f}", font=font_val, fill=text_primary)
        
        # Col 2: Last Price
        col2_x = margin + col_text_width
        draw.text((col2_x, footer_text_y), "Last Price", font=font_label, fill=text_secondary)
        draw.text((col2_x, footer_val_y), f"{exit_price:,.4f}", font=font_val, fill=text_primary)
        
        # Col 3: Referral Code
        col3_x = margin + col_text_width * 2
        ref_title = user_cfg.get('referral_title', 'Referral Code')
        ref_code = user_cfg.get('referral_code', '-')
        draw.text((col3_x, footer_text_y), ref_title, font=font_label, fill=text_secondary)
        draw.text((col3_x, footer_val_y), ref_code, font=font_val, fill=text_primary)
        
        # Col 4: QR Code (right-aligned)
        qr_x = width - margin - qr_size
        qr_y = footer_y + (footer_height - qr_size) // 2
        self._draw_qr(img, qr_x, qr_y, qr_size)

    def _crop_to_fill(self, src_img, target_w, target_h):
        """Crop gambar ke rasio target (object-fit: cover) lalu resize."""
        src_w, src_h = src_img.size
        target_ratio = target_w / target_h
        src_ratio = src_w / src_h
        
        if src_ratio > target_ratio:
            # Gambar lebih lebar → crop horizontal
            new_w = int(src_h * target_ratio)
            left = (src_w - new_w) // 2
            cropped = src_img.crop((left, 0, left + new_w, src_h))
        else:
            # Gambar lebih tinggi → crop vertikal
            new_h = int(src_w / target_ratio)
            top = (src_h - new_h) // 2
            cropped = src_img.crop((0, top, src_w, top + new_h))
        
        return cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)

    def _create_diagonal_blur_mask(self, w, h):
        """Buat mask diagonal: kiri-bawah putih (blur), kanan-atas hitam (tajam)."""
        import numpy as np
        x = np.linspace(1, 0, w)
        y = np.arange(h) / max(h - 1, 1)
        ny, nx = np.meshgrid(y, x, indexing='ij')
        mask_data = ((nx + ny) / 2.0 * 255).astype(np.uint8)
        return Image.fromarray(mask_data, 'L')

    def _get_panel_image_path(self):
        """Helper: dapatkan path gambar panel jika valid."""
        images_cfg = self.config.get('images', {})
        path = self._get_asset_path(images_cfg.get('right_panel_image_path'))
        if path and os.path.exists(path):
            return path
        return None

    def _calc_panel_width(self, card_width, panel_height):
        """Hitung lebar panel kanan berdasarkan rasio gambar asli."""
        min_ratio = 0.30  # Minimal 30% card
        max_ratio = 0.65  # Maksimal 65% card
        default_ratio = 0.35
        
        panel_img_path = self._get_panel_image_path()
        if panel_img_path:
            try:
                with Image.open(panel_img_path) as tmp_img:
                    img_w, img_h = tmp_img.size
                    # Scale gambar agar tingginya = panel_height, hitung width natural
                    scale = panel_height / img_h
                    natural_w = int(img_w * scale)
                    # Clamp antara min dan max
                    ratio = max(min_ratio, min(max_ratio, natural_w / card_width))
                    return int(card_width * ratio)
            except:
                pass
        
        return int(card_width * default_ratio)

    def _draw_right_panel_bg(self, img, x, y, w, h):
        """Menggambar background panel kanan: custom image atau warna transparan."""
        images_cfg = self.config.get('images', {})
        style = self.config.get('style', {})
        opacity = images_cfg.get('right_panel_image_opacity', 0.4)
        
        panel_img_path = self._get_panel_image_path()
        if panel_img_path:
            try:
                panel_img = Image.open(panel_img_path).convert("RGBA")
                
                # Scale berdasarkan tinggi panel, lalu right-crop jika lebih lebar dari w
                img_w, img_h = panel_img.size
                scale = h / img_h
                scaled_w = int(img_w * scale)
                panel_img = panel_img.resize((scaled_w, h), Image.Resampling.LANCZOS)
                
                # Jika gambar lebih lebar dari panel → crop dari kanan (right-align)
                if scaled_w > w:
                    panel_img = panel_img.crop((scaled_w - w, 0, scaled_w, h))
                elif scaled_w < w:
                    # Jika lebih kecil → crop-to-fill
                    panel_img = self._crop_to_fill(panel_img, w, h)
                
                # Diagonal blur: kiri-bawah blur, kanan-atas tajam
                blurred = panel_img.filter(ImageFilter.GaussianBlur(radius=40))
                blur_mask = self._create_diagonal_blur_mask(w, h)
                panel_img = Image.composite(blurred, panel_img, blur_mask)
                
                # Apply gradient opacity: kiri=transparan, kanan atas=opaque
                import numpy as np
                alpha = np.array(panel_img.split()[3], dtype=np.float32)
                
                # Gradient diagonal: kiri-bawah=0, kanan-atas=max_opacity
                grad = np.zeros((h, w), dtype=np.float32)
                gx = np.linspace(0, 1, w)
                gy = 1.0 - (np.arange(h) / max(h - 1, 1))
                gny, gnx = np.meshgrid(gy, gx, indexing='ij')
                grad = (gnx * (0.7 + gny * 0.3) * opacity)
                
                alpha = (alpha * grad).clip(0, 255).astype(np.uint8)
                panel_img.putalpha(Image.fromarray(alpha, 'L'))
                
                # Composite onto main image
                img_rgba = img.convert('RGBA')
                temp = Image.new('RGBA', img_rgba.size, (0, 0, 0, 0))
                temp.paste(panel_img, (x, y))
                result = Image.alpha_composite(img_rgba, temp)
                img.paste(result, (0, 0))
                return
            except Exception as e:
                print(f"Error loading right panel image: {e}")
        
        # Fallback: warna transparan
        right_bg_hex = style.get('right_panel_bg_color', '#1E232966')
        right_bg_color = self._hex_to_rgb(right_bg_hex)
        
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle([(x, y), (x + w, y + h)], fill=right_bg_color)
        result = Image.alpha_composite(img.convert('RGBA'), overlay)
        img.paste(result, (0, 0))

    def _draw_user_info(self, img, draw, x, y):
        """Menggambar info user (foto profil + username + tanggal)."""
        user_cfg = self.config.get('user', {})
        style = self.config.get('style', {})
        text_primary = self._hex_to_rgb(style.get('text_primary', '#FFFFFF'))
        text_secondary = self._hex_to_rgb(style.get('text_secondary', '#AAAAAA'))
        
        pp_size = 120
        pp_path = self._get_asset_path(user_cfg.get('profile_picture_path'))
        
        try:
            pp_img = Image.open(pp_path).convert("RGBA")
            pp_img = pp_img.resize((pp_size, pp_size), Image.Resampling.LANCZOS)
        except:
            pp_img = Image.new('RGBA', (pp_size, pp_size), (200, 200, 200, 255))
            
        mask = Image.new('L', (pp_size, pp_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, pp_size, pp_size), fill=255)
        img.paste(pp_img, (x, y), mask)
        
        text_x = x + pp_size + 30
        text_y = y + 10
        
        font_name = self.font_loader('bold', 40, fallback_key='bold')
        font_date = self.font_loader('regular', 24, fallback_key='regular')
        
        username = user_cfg.get('username', 'Trader')
        draw.text((text_x, text_y), username, font=font_name, fill=text_primary)
        
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        draw.text((text_x, text_y + 50), date_str, font=font_date, fill=text_secondary)

    def _draw_logo(self, img, right_x, y):
        """Menggambar logo exchange (ukuran configurable dari JSON)."""
        images_cfg = self.config.get('images', {})
        logo_path = self._get_asset_path(images_cfg.get('exchange_logo_path'))
        
        max_w = images_cfg.get('exchange_logo_max_width', 250)
        max_h = images_cfg.get('exchange_logo_max_height', 100)
        
        if logo_path and os.path.exists(logo_path):
            try:
                logo = Image.open(logo_path).convert("RGBA")
                logo.thumbnail((max_w, max_h))
                real_x = right_x - logo.width
                img.paste(logo, (real_x, y), logo)
            except Exception as e:
                print(f"Error loading logo: {e}")

    def _draw_watermark(self, img, width, height):
        """Menggambar watermark semi-transparan di tengah card."""
        images_cfg = self.config.get('images', {})
        
        if not images_cfg.get('show_watermark', False):
            return
        
        wm_path = self._get_asset_path(images_cfg.get('watermark_path'))
        if not wm_path or not os.path.exists(wm_path):
            return
        
        try:
            wm_img = Image.open(wm_path).convert("RGBA")
            
            # Scale watermark: max 40% lebar card, proporsional
            max_wm_w = int(width * 0.4)
            max_wm_h = int(height * 0.4)
            wm_img.thumbnail((max_wm_w, max_wm_h), Image.Resampling.LANCZOS)
            
            # Terapkan opacity rendah (15%) agar tidak menutupi konten
            opacity = 38  # ~15% dari 255
            wm_w, wm_h = wm_img.size
            alpha = wm_img.split()[3]
            alpha = alpha.point(lambda p: min(p, opacity))
            wm_img.putalpha(alpha)
            
            # Posisi: tengah card
            paste_x = (width - wm_w) // 2
            paste_y = (height - wm_h) // 2
            
            # Composite ke gambar utama
            img_rgba = img.convert('RGBA')
            temp = Image.new('RGBA', img_rgba.size, (0, 0, 0, 0))
            temp.paste(wm_img, (paste_x, paste_y))
            result = Image.alpha_composite(img_rgba, temp)
            img.paste(result, (0, 0))
        except Exception as e:
            print(f"Error drawing watermark: {e}")

    def _draw_qr(self, img, x, y, size):
        """Menggambar QR code."""
        user_cfg = self.config.get('user', {})
        if user_cfg.get('show_qr', True):
            if not qrcode:
                logger.warning("⚠️ QR Code requested but 'qrcode' library is not installed.")
                return

            qr_data = user_cfg.get('qr_data', 'https://example.com')
            try:
                # Border=3 memberikan whitespace (quiet zone) yang cukup tebal dan rapi
                qr = qrcode.QRCode(box_size=10, border=3)
                qr.add_data(qr_data)
                qr.make(fit=True)
                
                # Standard Black on White agar lebih kontras dan 'clean'
                # Menggunakan LANCZOS untuk hasil resize yang lebih halus
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_img = qr_img.resize((size, size), Image.Resampling.LANCZOS)
                
                img.paste(qr_img, (x, y))
            except Exception as e:
                logger.error(f"❌ Error generating QR: {e}")

    # --- Legacy Methods (fallback untuk portrait mode) ---
    def _draw_header(self, img, draw, width, margin):
        self._draw_user_info(img, draw, margin, margin + 20)
        self._draw_logo(img, width - margin, margin + 40)

    def _draw_stats(self, img, draw, width, height, margin, data):
        pass

    def _draw_footer(self, img, draw, width, height, margin):
        pass

# Standalone execution for testing
if __name__ == "__main__":
    generator = CryptoPnLGenerator()
    dummy_data = {
        'symbol': 'BTC/USDT',
        'side': 'SHORT',
        'entry_price': 98500.50,
        'exit_price': 92000.00,
        'pnl_usdt': 3250.00,
        'roi_percent': 315.50,
        'leverage': 50,
        'strategy': 'MACD Crossover'
    }
    
    img_buffer = generator.generate_card(dummy_data)
    with open("test_new_pnl.png", "wb") as f:
        f.write(img_buffer.getbuffer())
    print("Test image saved as test_new_pnl.png")

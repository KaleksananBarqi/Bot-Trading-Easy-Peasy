# 🛡️ Bot Trading V3 - Smart Conservative (ADX Filtered)

Bot trading crypto otomatis untuk **Binance Futures**. Didesain dengan logika **konservatif** untuk meminimalisir risiko, namun tetap fleksibel untuk disesuaikan dengan gaya trading Anda.

---

## ⚙️ Konfigurasi Mudah (Customizable)

Strategi default bot ini menggunakan kombinasi **EMA, RSI, dan ADX**. Namun, Anda tidak terpaku pada settingan ini! Semua parameter bisa diganti sesuka hati melalui file `config.py`.

Anda bebas mengatur:
* **Indikator:** Ubah periode EMA (Fast/Slow/Trend), batas RSI, atau sensitivitas ADX.
* **Risk Management:** Sesuaikan lebar Stop Loss & Take Profit (berbasis Multiplier ATR).
* **Safety:** Atur maksimal jumlah posisi terbuka (*Max Open Positions*) agar margin tetap aman.
* **Money Management:** Atur modal per koin dan leverage sesuai saldo Anda.

> Cukup buka file `config.py`, ubah angkanya, dan bot akan berjalan sesuai aturan baru Anda.

---

## 📋 Requirements (Persiapan)

Sebelum menjalankan bot, pastikan hal-hal berikut sudah siap:

- [ ] Akun **Binance** (Fitur Futures harus sudah aktif).
- [ ] **API Key & Secret Key** dari Binance (Pastikan opsi *Enable Futures* dicentang pada pengaturan API).
- [ ] **Bot Telegram** (Buat melalui `@BotFather`, simpan Token-nya).
- [ ] **ID Telegram** (Cek melalui bot `@userinfobot` untuk mendapatkan ID angka).
- [ ] **Python 3.8+** (Wajib terinstall di Laptop atau VPS).

---

## 🚀 Cara Install (Local / Laptop)

Jika ingin menjalankan bot melalui laptop/PC sendiri:

### 1. Clone / Download Repository
Download atau clone repository ini, kemudian buka terminal/CMD di dalam folder project.

### 2. Install Library Python
Jalankan perintah berikut untuk menginstall semua library yang dibutuhkan:

```bash
# Update pip (opsional)
python -m pip install --upgrade pip

# Install dependencies
pip install ccxt pandas pandas_ta requests python-dotenv
````

### 3\. Konfigurasi Environment (`.env`)

Bot membutuhkan file `.env` untuk menyimpan kredensial secara aman.
Buat file baru bernama `.env` di dalam folder project, lalu isi dengan format berikut:

```env
BINANCE_API_KEY=masukan_api_key_binance_disini
BINANCE_SECRET_KEY=masukan_secret_key_binance_disini
TELEGRAM_TOKEN=masukan_token_bot_telegram_disini
TELEGRAM_CHAT_ID=masukan_id_telegram_disini
```

> **Note:** Jangan gunakan spasi sebelum atau sesudah tanda sama dengan (=).

### 4\. Konfigurasi Bot (`config.py`)

Buka file `config.py` untuk menyesuaikan pengaturan:

  * **Mode Trading:** Ubah `DEMO_MODE = True` untuk Testnet (uang mainan) atau `False` untuk Live Trading (uang asli).
  * **Daftar Koin:** Atur koin apa saja yang ingin ditradingkan pada variabel `DAFTAR_KOIN`.

### 5\. Jalankan Bot

Ketik perintah berikut di terminal:

```bash
python main_bot_15m.py
```

Jika berhasil, bot akan mengirim notifikasi ke Telegram bahwa koneksi berhasil.

-----

## ☁️ Cara Deploy di VPS (Server 24 Jam)

Untuk penggunaan jangka panjang, disarankan menggunakan VPS (Ubuntu) agar bot berjalan 24/7 tanpa perlu menyalakan laptop terus-menerus.

### 1\. Login ke Server

Masuk ke VPS menggunakan SSH:

```bash
ssh root@ip_server_anda
```

### 2\. Update & Install Python

Update repository server dan install paket yang diperlukan:

```bash
sudo apt update
sudo apt install python3-pip screen -y
```

### 3\. Upload File

Upload file `main_bot_15m.py`, `config.py`, dan `.env` ke server (bisa menggunakan SCP, FileZilla, atau git clone).

### 4\. Install Library di Server

```bash
pip3 install ccxt pandas pandas_ta requests python-dotenv
```

### 5\. Jalankan Bot di Background (Screen)

Gunakan `screen` agar bot tetap berjalan meskipun terminal ditutup.

**Buat sesi screen:**

```bash
screen -S bot_trading
```

**Jalankan bot:**

```bash
python3 main_bot_15m.py
```

**Detach (Keluar tanpa mematikan bot):**
Tekan tombol `CTRL + A`, kemudian tekan `D`.
*(Sekarang Anda bisa menutup terminal SSH dengan aman).*

**Monitoring (Cek bot kembali):**
Login ke VPS dan ketik:

```bash
screen -r bot_trading
```

-----

## 🛠 Troubleshooting

  * **ModuleNotFoundError:** Library belum terinstall. Ulangi langkah install library.
  * **API Key Invalid/Error:** Periksa kembali file `.env`. Pastikan tidak ada spasi berlebih. Jika menggunakan VPS, pastikan IP Address VPS sudah di-*whitelist* di pengaturan API Binance (atau matikan fitur IP restriction sementara).
  * **Bot Tidak Open Posisi:** Bot ini menggunakan filter ketat (`ADX > 20`). Jika pasar sedang *sideways* (datar), bot tidak akan melakukan entry demi keamanan. Cek log untuk memastikan bot sedang "Scanning Market".

-----

## ⚠️ Disclaimer

> **Trading Crypto Futures memiliki risiko finansial yang tinggi.** Bot ini hanyalah alat bantu eksekusi strategi dan bukan jaminan keuntungan. Gunakan dengan bijak dan resiko ditanggung pengguna (**DYOR**).

Happy Trading\! 🚀

```
```

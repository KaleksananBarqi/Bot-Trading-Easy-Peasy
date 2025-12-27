LIQ HUNT + EMA + ADX + ATR + BTC Filter + Vol Filter + BB Filter + StochRSI

saran
Berikut analisa + kritik teknis (berdasarkan kode yang kamu upload), fokus ke **bug yang bikin perilaku bot melenceng**, **risiko safety**, dan **bottleneck eksekusi**.

---

## 1) Gambaran strategi bot kamu (yang terbaca dari kode)

* Kamu pakai **filter tren BTC** via EMA di timeframe 1h, lalu membatasi alt jadi **LONG only / SHORT only** sesuai tren BTC.  
* Eksekusi sinyal per koin pakai timeframe 15m, indikator: EMA(FAST/SLOW/MAJOR), ATR, ADX, RSI, Bollinger Bands, StochRSI, plus volume MA.  
* Mode eksekusi ada 2:

  * **Normal**: market order + pasang SL/TP langsung. 
  * **Liquidity hunt**: pasang **limit entry di level retail SL**, lalu SL/TP dipasang belakangan oleh “satpam” saat posisi terdeteksi sudah terbuka.  
* Kamu bikin **JSON tracker** supaya satpam tidak spam pasang SL/TP, dan ada cleanup cancel order saat posisi sudah tutup.  

---

## 2) Yang sudah bagus

* Pakai candle “confirm” (`df.iloc[-2]`) itu bagus karena menghindari sinyal dari candle yang belum close. 
* Ada **safety monitor** yang mencoba memastikan setiap posisi punya SL/TP + ada cleanup order nyangkut.  
* Ada **filter volume** (volume > MA) yang biasanya membantu ngurangin fake move. 

---

## 3) Bug logika paling fatal: mode “BOTH” hampir tidak pernah SHORT ✅

Di bagian sinyal, kamu pakai pola:

* Trending:

  * `if allowed_signal in ["LONG_ONLY","BOTH"]:` … LONG
  * `elif allowed_signal in ["SHORT_ONLY","BOTH"]:` … SHORT 

* Sideways juga sama (LONG pakai `if`, SHORT pakai `elif`). 

Masalahnya: kalau `allowed_signal == "BOTH"`, kondisi `if` pertama sudah True, jadi blok `elif` **tidak akan pernah dieksekusi**. Akibatnya:

* Saat BTC netral (allowed_signal default “BOTH”), bot condong cuma cari LONG.
* Untuk BTC sendiri juga “BOTH” (karena kamu bypass filter BTC), jadi BTC cenderung cuma LONG juga.  

**Fix paling aman (minimal change):** ganti `elif` jadi `if`, atau bikin dua blok terpisah dan hanya set sinyal kalau `signal is None`.

Contoh patch (inti idenya):

```python
if adx_val > config.ADX_LIMIT_TREND:
    if allowed_signal in ["LONG_ONLY", "BOTH"]:
        # cek LONG...
        if kondisi_long:
            signal = "LONG"
            strategy_type = "TREND_STRONG"

    if signal is None and allowed_signal in ["SHORT_ONLY", "BOTH"]:
        # cek SHORT...
        if kondisi_short:
            signal = "SHORT"
            strategy_type = "TREND_STRONG"
else:
    if allowed_signal in ["LONG_ONLY", "BOTH"]:
        # cek reversal LONG...
        if kondisi_long:
            signal = "LONG"
            strategy_type = "SCALP_REVERSAL"

    if signal is None and allowed_signal in ["SHORT_ONLY", "BOTH"]:
        # cek reversal SHORT...
        if kondisi_short:
            signal = "SHORT"
            strategy_type = "SCALP_REVERSAL"
```

---

## 4) Masalah serius di `config.py`: duplikasi blok + parameter saling menimpa ✅

`config.py` kamu terlihat **terduplikasi** (ada blok config diulang lagi setelah bagian liquidity hunt). 

Efek nyatanya:

* `BTC_EMA_PERIOD` didefinisikan **dua kali**: 50 di awal, lalu 21 di blok kedua. Dalam Python, yang kepakai adalah definisi terakhir (21).  
* Ini bikin komentar/setting kamu bisa “ngibulin diri sendiri” (kamu merasa pakai 50 tapi realnya 21).

Saran: rapikan jadi **1 blok config saja**, pastikan tidak ada redefinisi variabel yang tidak sengaja.

---

## 5) Concurrency & rate-limit: `CONCURRENCY_LIMIT` ada, tapi tidak dipakai ✅

Di config ada `CONCURRENCY_LIMIT = 20`. 
Tapi di main loop kamu langsung:

* `tasks = [analisa_market(...)]` untuk seluruh koin,
* lalu `await asyncio.gather(*tasks)` tanpa semaphore. 

Padahal tiap `analisa_market()` melakukan beberapa call berat: `fetch_open_orders`, `fetch_ohlcv` (bahkan 2 timeframe), dll. 
Ini rawan:

* kena rate limit / request burst,
* error acak,
* delay data tidak konsisten antar koin.

**Fix:** pakai `asyncio.Semaphore(config.CONCURRENCY_LIMIT)` untuk membatasi call paralel.

---

## 6) Inefisiensi: fetch timeframe trend (1h) tapi tidak dipakai✅

Kamu fetch:

```python
bars_h1 = await exchange.fetch_ohlcv(symbol, config.TIMEFRAME_TREND, limit=config.LIMIT_TREND)
if not bars or not bars_h1: return
```

tapi setelah itu indikator dihitung hanya dari `df` (15m) dan `bars_h1` tidak dipakai sama sekali. 

Kalau memang tidak dipakai, hapus fetch 1h itu supaya hemat request. Kalau mau dipakai, jadikan filter “major trend” beneran (misal EMA50 di 1h untuk bias).

---

## 7) Risiko safety: JSON tracker bisa bikin posisi jadi “dianggap aman” padahal SL/TP hilang

Di satpam, kamu skip pemasangan SL/TP kalau tracker bilang True. 
Tracker itu diload saat startup. 

Risikonya:

* Kalau bot restart, tracker bisa bilang “aman”, padahal order SL/TP sebenarnya **sudah ke-cancel**, expired, atau gagal dibuat sebelumnya.
* Karena kamu tidak memverifikasi keberadaan protective orders saat `tracker=True`, posisi bisa jalan tanpa SL/TP.

**Saran upgrade satpam:**

* Kalau `tracker=True`, tetap lakukan verifikasi “apakah ada order STOP/TP yang reduceOnly untuk simbol itu”.
* Kalau tidak ada, pasang ulang dan update tracker.

---

## 8) Mode Liquidity Hunt: TP dihitung dari harga “sekarang”, bukan dari entry limit

Di `calculate_trade_parameters()`:

* `retail_tp` dihitung dari `current_price` (close terakhir). 
* Saat liquidity hunt aktif, `new_entry = retail_sl` (lebih jauh dari current), tapi `final_tp = retail_tp` tetap yang dihitung dari current_price. 

Artinya: saat entry kamu “nanti” keisi di harga berbeda, TP bisa jadi:

* terlalu jauh (jadi jarang kena), atau
* profil risk/reward jadi tidak seperti yang kamu bayangkan.

Saran: kalau entry digeser, maka TP/SL sebaiknya dihitung relatif ke **entry** (atau minimal ada mode pilihan).

---

## 9) Catatan kompatibilitas CCXT/Binance (perlu kamu cek)

Di main kamu pakai `exchange.enable_demo_trading(True)` saat demo. 
[Belum Diverifikasi] Di beberapa versi CCXT, pola yang umum untuk testnet/sandbox adalah `set_sandbox_mode(True)`. Kalau method kamu tidak ada, bot akan crash di startup. (Ini perlu kamu cek sesuai versi CCXT yang kamu install.)

---

## 10) Prioritas perbaikan (urut paling “ngaruh”)

1. **Perbaiki bug `BOTH` vs `elif`** supaya SHORT bisa jalan saat allowed_signal BOTH. 
2. Rapikan `config.py` yang duplikat supaya parameter tidak ketimpa diam-diam (terutama `BTC_EMA_PERIOD`).  
3. Terapkan **Semaphore** pakai `CONCURRENCY_LIMIT` karena sekarang gather tanpa batas.  
4. Ubah satpam: **tracker=True tetap verifikasi SL/TP exist**, bukan langsung skip. 
5. Buang `bars_h1` kalau memang tidak dipakai (atau pakai benar untuk filter). 

---

Kalau kamu mau, aku bisa kasih “patch versi rapi” (bukan rewrite total) yang:

* fix BOTH/SHORT,
* pakai semaphore,
* verifikasi SL/TP walau tracker sudah True,
* dan bersihin config yang dobel.

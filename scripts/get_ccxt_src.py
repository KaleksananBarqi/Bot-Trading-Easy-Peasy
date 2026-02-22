import ccxt
import inspect

# Coba lihat argumen dari create_order di binance
print("Mencari create_order...")
try:
    source = inspect.getsource(ccxt.binance.create_order)
    print("Ketemu!")
    with open("ccxt_create_order.py", "w", encoding="utf-8") as f:
        f.write(source)
except Exception as e:
    print(e)


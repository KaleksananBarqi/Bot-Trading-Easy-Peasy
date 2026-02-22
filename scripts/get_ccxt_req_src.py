import ccxt
import inspect

try:
    with open("ccxt_create_order_request.py", "w", encoding="utf-8") as f:
        f.write(inspect.getsource(ccxt.binance.create_order_request))
except Exception as e:
    print(e)

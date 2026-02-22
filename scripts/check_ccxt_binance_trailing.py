import ccxt
import urllib.parse
exchange = ccxt.binance({
    'options': {'defaultType': 'future'},
    'apiKey': 'test',
    'secret': 'test'
})
exchange.load_markets() # Load real markets

def mock_request(path, *args, **kwargs):
    method = kwargs.get('method', args[1] if len(args) > 1 else 'GET')
    body = kwargs.get('body', args[4] if len(args) > 4 else None)
    
    if "order" in path and method == 'POST':
        print("\n=== REQUEST ENCODED ===")
        # print("BODY PARAMS:", body)
        if body:
            parsed = urllib.parse.urlencode(body) if isinstance(body, dict) else body
            print("DECODED PARAMS:", urllib.parse.unquote(parsed))
        return {'id': '123', 'info': {}} # Return dummy success instead of raise

    return {} # dummy for others

exchange.request = mock_request

print("--- TEST 1 with RAW BINANCE PARAMS ---")
try:
    exchange.create_order(
        symbol='BTC/USDT',
        type='TRAILING_STOP_MARKET',
        side='sell',
        amount=0.005,
        price=None,
        params={
            'callbackRate': 0.1,
            'activationPrice': '67640.10',
            'workingType': 'MARK_PRICE',
            'reduceOnly': True
        }
    )
except Exception as e:
    print("FAILED:", e)

print("\n--- TEST 2 with UNIFIED PARAMS ---")
try:
    exchange.create_order(
        symbol='BTC/USDT',
        type='TRAILING_STOP_MARKET',
        side='sell',
        amount=0.005,
        price=None,
        params={
            'trailingPercent': 0.1,
            'trailingTriggerPrice': 67640.10,
            'workingType': 'MARK_PRICE',
            'reduceOnly': True
        }
    )
except Exception as e:
    print("FAILED:", e)

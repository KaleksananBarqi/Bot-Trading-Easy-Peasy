import asyncio
import os
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
src_dir = os.path.join(project_root, 'src')
sys.path.insert(0, project_root)
sys.path.insert(0, src_dir)

import ccxt.async_support as ccxt
import config

async def main():
    exchange = ccxt.binance({
        'apiKey': config.API_KEY_DEMO,
        'secret': config.SECRET_KEY_DEMO,
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    exchange.enable_demo_trading(True)

    try:
        ticker = await exchange.fetch_ticker('BTC/USDT')
        current_price = float(ticker['last'])
        activation = current_price * 1.05
        activation_str = exchange.price_to_precision('BTC/USDT', activation)
        print(f"Current price: {current_price}, setting activationPrice to: {activation_str}")
        
        # Test RAW REQUEST to /fapi/v1/order
        request = {
            'symbol': 'BTCUSDT',
            'side': 'SELL',
            'type': 'TRAILING_STOP_MARKET',
            'quantity': '0.005',
            'callbackRate': '0.1',
            'activationPrice': activation_str,
            'workingType': 'MARK_PRICE'
        }
        
        import json
        res = await exchange.fapiPrivatePostOrder(request)
        with open("raw_res.json", "w") as f:
            json.dump(res, f, indent=4)
        print("Raw response saved to raw_res.json")
        
    except Exception as e:
        print("FAILED:", e)
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import sys
import json

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
        
        activation = current_price * 1.05 # 5% higher
        
        activation_str = exchange.price_to_precision('BTC/USDT', activation)
        print(f"Current price: {current_price}, setting activationPrice to: {activation_str}")
        
        params = {
            'callbackRate': 0.1,
            'activationPrice': activation_str,
            'workingType': 'MARK_PRICE'
        }
        
        order = await exchange.create_order(
            symbol='BTC/USDT',
            type='TRAILING_STOP_MARKET',
            side='sell',
            amount=0.005,
            price=None,
            params=params
        )
        with open("order_res.json", "w") as f:
            json.dump(order, f, indent=4)
        print("Order placed successfully, saved to order_res.json")
        
    except Exception as e:
        print("FAILED:", e)
    finally:
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())

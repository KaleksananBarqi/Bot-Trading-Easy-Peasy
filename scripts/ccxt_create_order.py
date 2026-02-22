    def create_order(self, symbol: str, type: OrderType, side: OrderSide, amount: float, price: Num = None, params={}):
        """
        create a trade order

        https://developers.binance.com/docs/binance-spot-api-docs/rest-api/trading-endpoints#new-order-trade
        https://developers.binance.com/docs/binance-spot-api-docs/testnet/rest-api/trading-endpoints#test-new-order-trade
        https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order
        https://developers.binance.com/docs/derivatives/coin-margined-futures/trade/rest-api
        https://developers.binance.com/docs/derivatives/option/trade/New-Order
        https://developers.binance.com/docs/binance-spot-api-docs/rest-api/trading-endpoints#sor
        https://developers.binance.com/docs/binance-spot-api-docs/testnet/rest-api/trading-endpoints#sor
        https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-UM-Order
        https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-CM-Order
        https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-Margin-Order
        https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-UM-Conditional-Order
        https://developers.binance.com/docs/derivatives/portfolio-margin/trade/New-CM-Conditional-Order
        https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Algo-Order

        :param str symbol: unified symbol of the market to create an order in
        :param str type: 'market' or 'limit' or 'STOP_LOSS' or 'STOP_LOSS_LIMIT' or 'TAKE_PROFIT' or 'TAKE_PROFIT_LIMIT' or 'STOP'
        :param str side: 'buy' or 'sell'
        :param float amount: how much of you want to trade in units of the base currency
        :param float [price]: the price that the order is to be fulfilled, in units of the quote currency, ignored in market orders
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :param str [params.reduceOnly]: for swap and future reduceOnly is a string 'true' or 'false' that cant be sent with close position set to True or in hedge mode. For spot margin and option reduceOnly is a boolean.
        :param str [params.marginMode]: 'cross' or 'isolated', for spot margin trading
        :param boolean [params.sor]: *spot only* whether to use SOR(Smart Order Routing) or not, default is False
        :param boolean [params.test]: *spot only* whether to use the test endpoint or not, default is False
        :param float [params.trailingPercent]: the percent to trail away from the current market price
        :param float [params.trailingTriggerPrice]: the price to trigger a trailing order, default uses the price argument
        :param float [params.triggerPrice]: the price that a trigger order is triggered at
        :param float [params.stopLossPrice]: the price that a stop loss order is triggered at
        :param float [params.takeProfitPrice]: the price that a take profit order is triggered at
        :param boolean [params.portfolioMargin]: set to True if you would like to create an order in a portfolio margin account
        :param str [params.selfTradePrevention]: set unified value for stp, one of NONE, EXPIRE_MAKER, EXPIRE_TAKER or EXPIRE_BOTH
        :param float [params.icebergAmount]: set iceberg amount for limit orders
        :param str [params.stopLossOrTakeProfit]: 'stopLoss' or 'takeProfit', required for spot trailing orders
        :param str [params.positionSide]: *swap and portfolio margin only* "BOTH" for one-way mode, "LONG" for buy side of hedged mode, "SHORT" for sell side of hedged mode
        :param bool [params.hedged]: *swap and portfolio margin only* True for hedged mode, False for one way mode, default is False
        :returns dict: an `order structure <https://docs.ccxt.com/#/?id=order-structure>`
        """
        self.load_markets()
        market = self.market(symbol)
        # don't handle/omit params here, omitting happens inside createOrderRequest
        marketType = self.safe_string(params, 'type', market['type'])
        marginMode = self.safe_string(params, 'marginMode')
        porfolioOptionsValue = self.safe_bool_2(self.options, 'papi', 'portfolioMargin', False)
        isPortfolioMargin = self.safe_bool_2(params, 'papi', 'portfolioMargin', porfolioOptionsValue)
        triggerPrice = self.safe_string_2(params, 'triggerPrice', 'stopPrice')
        stopLossPrice = self.safe_string(params, 'stopLossPrice')
        takeProfitPrice = self.safe_string(params, 'takeProfitPrice')
        trailingPercent = self.safe_string_2(params, 'trailingPercent', 'callbackRate')
        isTrailingPercentOrder = trailingPercent is not None
        isStopLoss = stopLossPrice is not None
        isTakeProfit = takeProfitPrice is not None
        isConditional = (triggerPrice is not None) or isTrailingPercentOrder or isStopLoss or isTakeProfit
        sor = self.safe_bool_2(params, 'sor', 'SOR', False)
        test = self.safe_bool(params, 'test', False)
        params = self.omit(params, ['sor', 'SOR', 'test'])
        # if isPortfolioMargin:
        #     params['portfolioMargin'] = isPortfolioMargin
        # }
        request = self.create_order_request(symbol, type, side, amount, price, params)
        response = None
        if market['option']:
            response = self.eapiPrivatePostOrder(request)
        elif sor:
            if test:
                response = self.privatePostSorOrderTest(request)
            else:
                response = self.privatePostSorOrder(request)
        elif market['linear']:
            if isPortfolioMargin:
                if isConditional:
                    response = self.papiPostUmConditionalOrder(request)
                else:
                    response = self.papiPostUmOrder(request)
            else:
                if isConditional:
                    request['algoType'] = 'CONDITIONAL'
                    response = self.fapiPrivatePostAlgoOrder(request)
                else:
                    response = self.fapiPrivatePostOrder(request)
        elif market['inverse']:
            if isPortfolioMargin:
                if isConditional:
                    response = self.papiPostCmConditionalOrder(request)
                else:
                    response = self.papiPostCmOrder(request)
            else:
                response = self.dapiPrivatePostOrder(request)
        elif marketType == 'margin' or marginMode is not None or isPortfolioMargin:
            if isPortfolioMargin:
                response = self.papiPostMarginOrder(request)
            else:
                response = self.sapiPostMarginOrder(request)
        else:
            if test:
                response = self.privatePostOrderTest(request)
            else:
                response = self.privatePostOrder(request)
        return self.parse_order(response, market)

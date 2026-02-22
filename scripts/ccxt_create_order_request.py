def create_order_request(self, symbol: str, type: OrderType, side: OrderSide, amount: float, price: Num = None, params={}):
        """
 @ignore
        helper function to build the request
        :param str symbol: unified symbol of the market to create an order in
        :param str type: 'market' or 'limit'
        :param str side: 'buy' or 'sell'
        :param float amount: how much you want to trade in units of the base currency
        :param float [price]: the price that the order is to be fulfilled, in units of the quote currency, ignored in market orders
        :param dict [params]: extra parameters specific to the exchange API endpoint
        :returns dict: request to be sent to the exchange
        """
        market = self.market(symbol)
        marketType = self.safe_string(params, 'type', market['type'])
        clientOrderId = self.safe_string_n(params, ['clientAlgoId', 'newClientOrderId', 'clientOrderId'])
        initialUppercaseType = type.upper()
        isMarketOrder = initialUppercaseType == 'MARKET'
        isLimitOrder = initialUppercaseType == 'LIMIT'
        request: dict = {
            'symbol': market['id'],
            'side': side.upper(),
        }
        isPortfolioMargin = None
        isPortfolioMargin, params = self.handle_option_and_params_2(params, 'createOrder', 'papi', 'portfolioMargin', False)
        marginMode = None
        marginMode, params = self.handle_margin_mode_and_params('createOrder', params)
        reduceOnly = self.safe_bool(params, 'reduceOnly', False)
        if reduceOnly:
            if marketType == 'margin' or (not market['contract'] and (marginMode is not None)):
                params = self.omit(params, 'reduceOnly')
                request['sideEffectType'] = 'AUTO_REPAY'
        triggerPrice = self.safe_string_2(params, 'triggerPrice', 'stopPrice')
        stopLossPrice = self.safe_string(params, 'stopLossPrice', triggerPrice)  # fallback to stopLoss
        takeProfitPrice = self.safe_string(params, 'takeProfitPrice')
        trailingDelta = self.safe_string(params, 'trailingDelta')
        trailingTriggerPrice = self.safe_string_2(params, 'trailingTriggerPrice', 'activationPrice')
        trailingPercent = self.safe_string_n(params, ['trailingPercent', 'callbackRate', 'trailingDelta'])
        priceMatch = self.safe_string(params, 'priceMatch')
        isTrailingPercentOrder = trailingPercent is not None
        isStopLoss = stopLossPrice is not None or trailingDelta is not None
        isTakeProfit = takeProfitPrice is not None
        isTriggerOrder = triggerPrice is not None
        isConditional = isTriggerOrder or isTrailingPercentOrder or isStopLoss or isTakeProfit
        isPortfolioMarginConditional = (isPortfolioMargin and isConditional)
        isPriceMatch = priceMatch is not None
        priceRequiredForTrailing = True
        uppercaseType = type.upper()
        stopPrice = None
        if isTrailingPercentOrder:
            if market['swap']:
                uppercaseType = 'TRAILING_STOP_MARKET'
                request['callbackRate'] = trailingPercent
                if trailingTriggerPrice is not None:
                    request['activationPrice'] = self.price_to_precision(symbol, trailingTriggerPrice)
            else:
                if (uppercaseType != 'STOP_LOSS') and (uppercaseType != 'TAKE_PROFIT') and (uppercaseType != 'STOP_LOSS_LIMIT') and (uppercaseType != 'TAKE_PROFIT_LIMIT'):
                    stopLossOrTakeProfit = self.safe_string(params, 'stopLossOrTakeProfit')
                    params = self.omit(params, 'stopLossOrTakeProfit')
                    if (stopLossOrTakeProfit != 'stopLoss') and (stopLossOrTakeProfit != 'takeProfit'):
                        raise InvalidOrder(self.id + symbol + ' trailingPercent orders require a stopLossOrTakeProfit parameter of either stopLoss or takeProfit')
                    if isMarketOrder:
                        if stopLossOrTakeProfit == 'stopLoss':
                            uppercaseType = 'STOP_LOSS'
                        elif stopLossOrTakeProfit == 'takeProfit':
                            uppercaseType = 'TAKE_PROFIT'
                    else:
                        if stopLossOrTakeProfit == 'stopLoss':
                            uppercaseType = 'STOP_LOSS_LIMIT'
                        elif stopLossOrTakeProfit == 'takeProfit':
                            uppercaseType = 'TAKE_PROFIT_LIMIT'
                if (uppercaseType == 'STOP_LOSS') or (uppercaseType == 'TAKE_PROFIT'):
                    priceRequiredForTrailing = False
                if trailingTriggerPrice is not None:
                    stopPrice = self.price_to_precision(symbol, trailingTriggerPrice)
                trailingPercentConverted = Precise.string_mul(trailingPercent, '100')
                request['trailingDelta'] = trailingPercentConverted
        elif isStopLoss:
            stopPrice = stopLossPrice
            if isMarketOrder:
                # spot STOP_LOSS market orders are not a valid order type
                uppercaseType = 'STOP_MARKET' if market['contract'] else 'STOP_LOSS'
            elif isLimitOrder:
                uppercaseType = 'STOP' if market['contract'] else 'STOP_LOSS_LIMIT'
        elif isTakeProfit:
            stopPrice = takeProfitPrice
            if isMarketOrder:
                # spot TAKE_PROFIT market orders are not a valid order type
                uppercaseType = 'TAKE_PROFIT_MARKET' if market['contract'] else 'TAKE_PROFIT'
            elif isLimitOrder:
                uppercaseType = 'TAKE_PROFIT' if market['contract'] else 'TAKE_PROFIT_LIMIT'
        if market['option']:
            if type == 'market':
                raise InvalidOrder(self.id + ' ' + type + ' is not a valid order type for the ' + symbol + ' market')
        else:
            validOrderTypes = self.safe_list(market['info'], 'orderTypes')
            if not self.in_array(uppercaseType, validOrderTypes):
                if initialUppercaseType != uppercaseType:
                    raise InvalidOrder(self.id + ' triggerPrice parameter is not allowed for ' + symbol + ' ' + type + ' orders')
                else:
                    raise InvalidOrder(self.id + ' ' + type + ' is not a valid order type for the ' + symbol + ' market')
        clientOrderIdRequest = 'newClientStrategyId' if isPortfolioMarginConditional else 'newClientOrderId'
        if market['linear'] and market['swap'] and isConditional and not isPortfolioMargin:
            clientOrderIdRequest = 'clientAlgoId'
        if clientOrderId is None:
            broker = self.safe_dict(self.options, 'broker', {})
            defaultId = 'x-xcKtGhcu' if (market['contract']) else 'x-TKT5PX2F'
            idMarketType = 'spot'
            if market['contract']:
                idMarketType = 'swap' if (market['swap'] and market['linear']) else 'inverse'
            brokerId = self.safe_string(broker, idMarketType, defaultId)
            request[clientOrderIdRequest] = brokerId + self.uuid22()
        else:
            request[clientOrderIdRequest] = clientOrderId
        postOnly = None
        if not isPortfolioMargin:
            postOnly = self.is_post_only(isMarketOrder, initialUppercaseType == 'LIMIT_MAKER', params)
            if market['spot'] or marketType == 'margin':
                # only supported for spot/margin api(all margin markets are spot markets)
                if postOnly:
                    uppercaseType = 'LIMIT_MAKER'
                if marginMode == 'isolated':
                    request['isIsolated'] = True
        else:
            postOnly = self.is_post_only(isMarketOrder, initialUppercaseType == 'LIMIT_MAKER', params)
            if postOnly:
                if not market['contract']:
                    uppercaseType = 'LIMIT_MAKER'
                else:
                    request['timeInForce'] = 'GTX'
        # handle newOrderRespType response type
        if ((marketType == 'spot') or (marketType == 'margin')) and not isPortfolioMargin:
            request['newOrderRespType'] = self.safe_string(self.options['newOrderRespType'], type, 'FULL')  # 'ACK' for order id, 'RESULT' for full order or 'FULL' for order with fills
        else:
            # swap, futures and options
            request['newOrderRespType'] = 'RESULT'  # "ACK", "RESULT", default "ACK"
        typeRequest = 'strategyType' if isPortfolioMarginConditional else 'type'
        request[typeRequest] = uppercaseType
        # additional required fields depending on the order type
        closePosition = self.safe_bool(params, 'closePosition', False)
        timeInForceIsRequired = False
        priceIsRequired = False
        triggerPriceIsRequired = False
        quantityIsRequired = False
        #
        # spot/margin
        #
        #     LIMIT                timeInForce, quantity, price
        #     MARKET               quantity or quoteOrderQty
        #     STOP_LOSS            quantity, stopPrice
        #     STOP_LOSS_LIMIT      timeInForce, quantity, price, stopPrice
        #     TAKE_PROFIT          quantity, stopPrice
        #     TAKE_PROFIT_LIMIT    timeInForce, quantity, price, stopPrice
        #     LIMIT_MAKER          quantity, price
        #
        # futures
        #
        #     LIMIT                timeInForce, quantity, price
        #     MARKET               quantity
        #     STOP/TAKE_PROFIT     quantity, price, stopPrice
        #     STOP_MARKET          stopPrice
        #     TAKE_PROFIT_MARKET   stopPrice
        #     TRAILING_STOP_MARKET callbackRate
        #
        if uppercaseType == 'MARKET':
            if market['spot']:
                quoteOrderQty = self.safe_bool(self.options, 'quoteOrderQty', True)
                if quoteOrderQty:
                    quoteOrderQtyNew = self.safe_string_2(params, 'quoteOrderQty', 'cost')
                    precision = market['precision']['price']
                    if quoteOrderQtyNew is not None:
                        request['quoteOrderQty'] = self.decimal_to_precision(quoteOrderQtyNew, TRUNCATE, precision, self.precisionMode)
                    elif price is not None:
                        amountString = self.number_to_string(amount)
                        priceString = self.number_to_string(price)
                        quoteOrderQuantity = Precise.string_mul(amountString, priceString)
                        request['quoteOrderQty'] = self.decimal_to_precision(quoteOrderQuantity, TRUNCATE, precision, self.precisionMode)
                    else:
                        quantityIsRequired = True
                else:
                    quantityIsRequired = True
            else:
                quantityIsRequired = True
        elif uppercaseType == 'LIMIT':
            priceIsRequired = True
            timeInForceIsRequired = True
            quantityIsRequired = True
        elif (uppercaseType == 'STOP_LOSS') or (uppercaseType == 'TAKE_PROFIT'):
            triggerPriceIsRequired = True
            quantityIsRequired = True
            if (market['linear'] or market['inverse']) and priceRequiredForTrailing:
                priceIsRequired = True
        elif (uppercaseType == 'STOP_LOSS_LIMIT') or (uppercaseType == 'TAKE_PROFIT_LIMIT'):
            quantityIsRequired = True
            triggerPriceIsRequired = True
            priceIsRequired = True
            timeInForceIsRequired = True
        elif uppercaseType == 'LIMIT_MAKER':
            priceIsRequired = True
            quantityIsRequired = True
        elif uppercaseType == 'STOP':
            quantityIsRequired = True
            triggerPriceIsRequired = True
            priceIsRequired = True
        elif (uppercaseType == 'STOP_MARKET') or (uppercaseType == 'TAKE_PROFIT_MARKET'):
            if not closePosition:
                quantityIsRequired = True
            triggerPriceIsRequired = True
        elif uppercaseType == 'TRAILING_STOP_MARKET':
            if not closePosition:
                quantityIsRequired = True
            if trailingPercent is None:
                raise InvalidOrder(self.id + ' createOrder() requires a trailingPercent param for a ' + type + ' order')
        if quantityIsRequired:
            marketAmountPrecision = self.safe_string(market['precision'], 'amount')
            isPrecisionAvailable = (marketAmountPrecision is not None)
            if isPrecisionAvailable:
                request['quantity'] = self.amount_to_precision(symbol, amount)
            else:
                request['quantity'] = self.parse_to_numeric(amount)  # some options don't have the precision available
        if priceIsRequired and not isPriceMatch:
            if price is None:
                raise InvalidOrder(self.id + ' createOrder() requires a price argument for a ' + type + ' order')
            pricePrecision = self.safe_string(market['precision'], 'price')
            isPricePrecisionAvailable = (pricePrecision is not None)
            if isPricePrecisionAvailable:
                request['price'] = self.price_to_precision(symbol, price)
            else:
                request['price'] = self.parse_to_numeric(price)  # some options don't have the precision available
        if triggerPriceIsRequired:
            if market['contract']:
                if stopPrice is None:
                    raise InvalidOrder(self.id + ' createOrder() requires a triggerPrice extra param for a ' + type + ' order')
            else:
                # check for delta price
                if trailingDelta is None and stopPrice is None and trailingPercent is None:
                    raise InvalidOrder(self.id + ' createOrder() requires a triggerPrice, trailingDelta or trailingPercent param for a ' + type + ' order')
            if stopPrice is not None:
                if market['linear'] and market['swap'] and not isPortfolioMargin:
                    request['triggerPrice'] = self.price_to_precision(symbol, stopPrice)
                else:
                    request['stopPrice'] = self.price_to_precision(symbol, stopPrice)
        if timeInForceIsRequired and (self.safe_string(params, 'timeInForce') is None) and (self.safe_string(request, 'timeInForce') is None):
            request['timeInForce'] = self.safe_string(self.options, 'defaultTimeInForce')  # 'GTC' = Good To Cancel(default), 'IOC' = Immediate Or Cancel
        if not isPortfolioMargin and market['contract'] and postOnly:
            request['timeInForce'] = 'GTX'
        # remove timeInForce from params because PO is only used by self.is_post_only and it's not a valid value for Binance
        if self.safe_string(params, 'timeInForce') == 'PO':
            params = self.omit(params, 'timeInForce')
        hedged = self.safe_bool(params, 'hedged', False)
        if not market['spot'] and not market['option'] and hedged:
            if reduceOnly:
                params = self.omit(params, 'reduceOnly')
                side = 'sell' if (side == 'buy') else 'buy'
            request['positionSide'] = 'LONG' if (side == 'buy') else 'SHORT'
        # unified stp
        selfTradePrevention = None
        selfTradePrevention, params = self.handle_option_and_params(params, 'createOrder', 'selfTradePrevention')
        if selfTradePrevention is not None:
            if market['spot']:
                request['selfTradePreventionMode'] = selfTradePrevention.upper()  # binance enums exactly match the unified ccxt enums(but needs uppercase)
        # unified iceberg
        icebergAmount = self.safe_number(params, 'icebergAmount')
        if icebergAmount is not None:
            if market['spot']:
                request['icebergQty'] = self.amount_to_precision(symbol, icebergAmount)
        requestParams = self.omit(params, ['type', 'newClientOrderId', 'clientOrderId', 'postOnly', 'stopLossPrice', 'takeProfitPrice', 'stopPrice', 'triggerPrice', 'trailingTriggerPrice', 'trailingPercent', 'quoteOrderQty', 'cost', 'test', 'hedged', 'icebergAmount'])
        return self.extend(request, requestParams)

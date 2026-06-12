import yfinance as yf

for ticker in ['SERV', 'COHR']:
    stock = yf.Ticker(ticker)
    hist = stock.history(period='2y', auto_adjust=True, back_adjust=True)
    highs  = hist['High'].tolist()
    lows   = hist['Low'].tolist()
    closes = hist['Close'].tolist()
    highs_52w = highs[-252:]
    lows_52w  = lows[-252:]
    print(f'{ticker}:')
    print(f'  52W Low:  ${round(min(lows_52w), 2)}')
    print(f'  52W High: ${round(max(highs_52w), 2)}')
    print(f'  Current:  ${round(closes[-1], 2)}')
    print()
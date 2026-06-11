import yfinance as yf
stock = yf.Ticker('COHR')
hist = stock.history(period='2y', auto_adjust=True, back_adjust=True)
closes = hist['Close'].tolist()
closes_52w = closes[-252:]
print(f'52W Low:  ${round(min(closes_52w), 2)}')
print(f'52W High: ${round(max(closes_52w), 2)}')
print(f'Current:  ${round(closes[-1], 2)}')
from mootdx.reader import Reader

tdx_path = r"D:\Install\zd_zxzq_gm"
reader = Reader.factory(market='std', tdxdir=tdx_path)

df = reader.daily(symbol='002706')

# 查看数据的时间范围
print(f"数据起始日期: {df.index[0]}")
print(f"数据结束日期: {df.index[-1]}")

# 获取最新一条数据
latest = df.iloc[-1]
print(f"最新日期: {latest.name}")
print(f"最新收盘价: {latest['close']:.2f}")

# 或者用 tail(1)
# latest_df = df.tail(1)
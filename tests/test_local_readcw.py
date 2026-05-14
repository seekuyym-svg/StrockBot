import pandas as pd

# --- 路径配置 ---
PARQUET_FILE = r'E:\LearnPY\Projects\StockBot\files\findata_20251231.parquet'

def query_stock_perfect_format(code='002706.SZ'):
    try:
        # 1. 设置浮点数显示（针对金额，保留2位小数，不使用科学计数法）
        pd.options.display.float_format = '{:.2f}'.format
        
        # 读取已处理好的 Parquet
        df = pd.read_parquet(PARQUET_FILE)
        
        if code not in df.index:
            print(f"❌ 数据库中未找到代码: {code}")
            return

        # 2. 构造查询的物理位置列表
        # 前10个 (0-9) + 你指定的几个关键索引
        target_pos = list(range(10)) + [74, 92, 96, 107, 242]
        
        # 确保索引在文件范围内
        valid_pos = [i for i in target_pos if i < len(df.columns)]
        selected_cols = df.columns[valid_pos]
        
        # 3. 提取数据并转为 object 类型
        # 关键：只有 object 类型能让我们在 float 序列里强行插入 str 格式的日期
        stock_series = df.loc[code, selected_cols].astype(object)
        
        # 4. 强制抹除日期字段的 .00 (锁定 col0)
        for col in stock_series.index:
            if col.startswith('col0') or '人数' in col:
                val = stock_series[col]
                if pd.notna(val):
                    try:
                        # 转换逻辑：float -> int -> str (抹除 .00)
                        stock_series[col] = str(int(float(val)))
                    except:
                        pass
                    
        # 5. 美化输出
        print(f"\n" + "═"*60)
        print(f"  股票代码: {code}  核心指标明细 (前10项 + 指定专项)")
        print("═"*60)
        # 使用 to_string() 隐藏末尾的 Name 和 dtype
        print(stock_series.to_string())
        print("═"*60)

    except Exception as e:
        print(f"读取出错: {e}")

if __name__ == "__main__":
    query_stock_perfect_format('002706.SZ')
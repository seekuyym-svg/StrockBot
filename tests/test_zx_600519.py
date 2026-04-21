import pandas as pd

# --- 配置路径 ---
PARQUET_FILE = r'E:\LearnPY\Projects\StockBot\files\fin_data_20251231.parquet'
STOCK_CODE = '600519.SH'  # 茅台，记得带上我们之前生成的后缀

def query_stock_fin(code):
    # 1. 加载处理好的数据
    try:
        df = pd.read_parquet(PARQUET_FILE)
    except FileNotFoundError:
        print(f"❌ 未找到文件: {PARQUET_FILE}")
        return

    # 2. 检查代码是否存在于索引中
    if code in df.index:
        # 获取该行数据
        stock_data = df.loc[[code]] 
        
        # 3. 仅选取前 10 个字段 (列)
        # .iloc[:, :10] 表示选取所有行，以及从第 0 到 第 9 列
        result = stock_data.iloc[:, :10]
        
        print(f"--- {code} 财务数据预览 (前10项) ---")
        # 转置显示 (T) 可以让数据更易读（变成一列显示）
        print(result.T) 
    else:
        print(f"❌ 索引中未找到代码: {code}")
        # 打印前 5 个索引参考格式
        print("当前索引示例:", df.index[:5].tolist())

if __name__ == "__main__":
    query_stock_fin(STOCK_CODE)
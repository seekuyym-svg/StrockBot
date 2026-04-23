import pandas as pd

PARQUET_FILE = r'E:\LearnPY\Projects\StockBot\files\findata_20251231.parquet'

def filter_by_multiple_criteria(profit_yi=500, roe_threshold=10.0):
    try:
        # 1. 设置显示格式
        pd.options.display.float_format = '{:.2f}'.format
        df = pd.read_parquet(PARQUET_FILE)
        
        # 2. 定位字段列名 (使用模糊匹配确保兼容性)
        col96_name = next((c for c in df.columns if c.startswith('col96')), None)  # 净利润
        col6_name = next((c for c in df.columns if c.startswith('col6')), None)    # 净资产收益率
        col284_name = next((c for c in df.columns if c.startswith('col284')), None) # 目标显示字段
        
        if not all([col96_name, col6_name]):
            print(f"❌ 缺少必要字段: col96({col96_name}), col6({col6_name})")
            return

        # 3. 构造筛选条件
        # 净利润 > 500亿 且 净资产收益率 > 10%
        profit_val = profit_yi * 10**8
        condition = (df[col96_name] > profit_val) & (df[col6_name] > roe_threshold)
        
        # 4. 执行筛选与去重
        result_df = df[condition].copy()
        result_df = result_df[~result_df.index.duplicated(keep='first')]

        # 5. 输出结果
        print(f"\n" + "═"*70)
        print(f" 筛选条件: 净利润 > {profit_yi}亿 且 {col6_name} > {roe_threshold}%")
        print("═"*70)

        if not result_df.empty:
            # 定义要显示的列：代码(Index) + col284 + col6 + col96
            # 加上 col6 和 col96 是为了方便你验证筛选结果是否正确
            display_cols = [c for c in [col284_name, col6_name, col96_name] if c]
            
            # 排序（按净利润降序排列，让赚钱最多的在上面）
            result_df = result_df.sort_values(by=col96_name, ascending=False)
            
            print(result_df[display_cols].to_string())
            print("═"*70)
            print(f" 合计数量: {len(result_df)}")
        else:
            print(" 没有找到同时符合这两个条件的股票。")

    except Exception as e:
        print(f"筛选出错: {e}")

if __name__ == "__main__":
    # 筛选：净利润 > 500亿 且 ROE > 10%
    filter_by_multiple_criteria(profit_yi=500, roe_threshold=10.0)
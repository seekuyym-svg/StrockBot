import os
import re
import pandas as pd
from pytdx.reader import HistoryFinancialReader

# --- 配置区 ---
TDX_DIR = r'D:\Install\zd_zxzq_gm'
FIN_FILE = os.path.join(TDX_DIR, 'vipdoc', 'cw', 'gpcw20251231.dat')
MAPPER_CSV = r'E:\LearnPY\Projects\StockBot\files\financial_mapping.csv'
OUTPUT_PARQUET = r'E:\LearnPY\Projects\StockBot\files\fin_data_20251231.parquet'

def clean_name(text):
    """去掉名称中 [备注] 及其之后的内容"""
    if pd.isna(text):
        return text
    return re.sub(r'\[.*?\]', '', str(text)).strip()

def process_financial_data():
    print("正在加载并清洗字段映射表...")

    # 1. 读取映射表（只取前两列）
    try:
        mapping_df = pd.read_csv(MAPPER_CSV, encoding='gbk', usecols=[0, 1],
                                 names=['FN', 'name'], header=0, engine='python')
    except:
        mapping_df = pd.read_csv(MAPPER_CSV, encoding='utf-8', usecols=[0, 1],
                                 names=['FN', 'name'], header=0, engine='python')

    # 2. 构建 {财务编号: 中文名称} 字典
    field_map = {}
    for _, row in mapping_df.iterrows():
        try:
            fn_raw = str(row['FN'])
            fn_num = int(re.search(r'\d+', fn_raw).group())
            pure_name = clean_name(row['name'])
            field_map[fn_num] = pure_name
        except (AttributeError, ValueError, TypeError):
            continue

    # 3. 读取二进制财务数据
    if not os.path.exists(FIN_FILE):
        print(f"❌ 找不到财务文件: {FIN_FILE}")
        return

    print("正在解析二进制财务数据...")
    reader = HistoryFinancialReader()
    df = reader.get_df(FIN_FILE)

    if df is None or df.empty:
        print("❌ 解析结果为空。")
        return

    # 4. 关键：按位置顺序将列名映射为中文财务指标
    orig_cols = df.columns.tolist()
    new_cols = []
    for idx, orig_col in enumerate(orig_cols):
        if idx == 0:
            fin_code = 0          # 第一列通常是报告期（FN0）
        else:
            fin_code = idx        # 第 idx 列对应 FNidx
        cn_name = field_map.get(fin_code, f'FN{fin_code}')
        new_cols.append(cn_name)

    df.columns = new_cols

    # 5. 股票代码处理（补齐6位 + 市场后缀）
    df.index = df.index.map(lambda x: str(x).zfill(6))
    df.index = df.index.map(lambda x: x + '.SZ' if x[0] in ['0', '3'] else x + '.SH')
    df.index.name = 'code'

    # 6. 保存为 Parquet
    print(f"正在保存至: {OUTPUT_PARQUET}")
    df.to_parquet(OUTPUT_PARQUET, compression='snappy')

    print("✅ 处理完成！")
    return df

if __name__ == "__main__":
    final_df = process_financial_data()
    if final_df is not None:
        print("\n清洗后的字段预览（前5行，前8列）：")
        print(final_df.iloc[:5, :8])
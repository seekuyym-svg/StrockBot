import os
import re
import pandas as pd
from pytdx.reader import HistoryFinancialReader

# --- 配置区 ---
TDX_DIR = r'D:\Install\zd_zxzq_gm'  
FIN_FILE = os.path.join(TDX_DIR, 'vipdoc', 'cw', 'gpcw20251231.dat')
MAPPER_CSV = r'E:\LearnPY\Projects\StockBot\files\financial_mapping.csv'
OUTPUT_PARQUET = r'E:\LearnPY\Projects\StockBot\files\findata_20251231.parquet'

def clean_name(text):
    """去掉名称中 [备注] 及其内容"""
    if pd.isna(text): return ""
    return re.sub(r'\[.*?\]', '', str(text)).strip()

def process_financial_data_v7():
    print("正在加载字段映射表...")
    
    # 1. 加载映射表
    try:
        mapping_df = pd.read_csv(MAPPER_CSV, encoding='gbk', usecols=[0, 1], names=['FN', 'name'], header=0, engine='python')
    except:
        mapping_df = pd.read_csv(MAPPER_CSV, encoding='utf-8', usecols=[0, 1], names=['FN', 'name'], header=0, engine='python')

    # 2. 构建映射字典
    name_dict = {}
    for _, row in mapping_df.iterrows():
        try:
            fn_idx = int(re.search(r'\d+', str(row['FN'])).group())
            name_dict[fn_idx] = clean_name(row['name'])
        except:
            continue

    # 3. 读取原始二进制数据
    reader = HistoryFinancialReader()
    df = reader.get_df(FIN_FILE)
    
    if df is not None and not df.empty:
        # 4. 构造复合列名 (核心修复：基于列的索引位置 i 来命名)
        new_columns = []
        for i, old_col_name in enumerate(df.columns):
            # 无论原始叫 report_date 还是 col0，直接通过循环索引 i 来确定编号
            idx = i 
            
            # 强制将第 0 列命名为报告期
            if idx == 0:
                new_columns.append("col0-报告期")
                continue
                
            chinese_name = name_dict.get(idx, "")
            if chinese_name:
                new_columns.append(f"col{idx}-{chinese_name}")
            else:
                new_columns.append(f"col{idx}")
        
        df.columns = new_columns

        # 5. 强制将日期列转为整数，消除 2.025e+07 这种科学计数法
        col0_name = "col0-报告期"
        if col0_name in df.columns:
            df[col0_name] = pd.to_numeric(df[col0_name], errors='coerce').fillna(0).astype('int64')

        # 6. 股票代码标准化
        df.index = df.index.map(lambda x: str(x).zfill(6))
        df.index = df.index.map(lambda x: x + '.SZ' if x[0] in ['0', '3'] else x + '.SH')
        df.index.name = 'code'

        # 7. 存储
        print(f"正在保存至: {OUTPUT_PARQUET}")
        df.to_parquet(OUTPUT_PARQUET, compression='snappy')
        print(f"✅ 处理成功！第一个字段已成功强制锁定为：{col0_name}")
        return df

if __name__ == "__main__":
    process_financial_data_v7()
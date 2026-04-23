from mootdx.reader import Reader
import pandas as pd
import numpy as np
import os
import yaml
from pathlib import Path
from datetime import datetime, timedelta
from utils import get_stock_name, calculate_trend_score, calculate_price_change  # 导入综合评分和涨跌幅计算功能

# ==================== 配置区 ====================
def load_config():
    """
    加载配置文件
    
    数据来源:
        - 本地 config.yaml 文件
    
    Returns:
        dict: 配置字典
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, '..', 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN] 加载配置文件失败: {e}，使用默认配置")
        return {}

config = load_config()
# 数据来源: 配置文件中的 TDX_DIR，默认为常见安装路径
# 优化点: 建议将路径配置化，避免硬编码，方便不同环境部署
TDX_DIR = config.get('TDX_DIR', r"D:\Install\zd_zxzq_gm")  # 通达信安装目录
DATA_DIR = Path(__file__).parent.parent / "data"  # 选股结果输出目录（项目根目录下的data文件夹）

# 涨跌幅过滤配置
MAX_PRICE_CHANGE_PCT = config.get('VOLUME_STRATEGY', {}).get('max_price_change_pct', 20.0)  # 最大允许涨跌幅（%）

def ensure_data_dir():
    """确保data目录存在"""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        print(f"[OK] 创建目录: {DATA_DIR}")

def save_selected_stocks(selected: list):
    """
    将选股结果保存到txt文件
    
    Args:
        selected: 选中的股票列表 [(code, name), ...]
    
    Returns:
        bool: 保存是否成功
    """
    if not selected:
        print("[WARN] 没有选中的股票，跳过保存")
        return False
    
    ensure_data_dir()
    
    # 生成文件名：stockpool_YYYYMMDD.txt
    date_str = datetime.now().strftime('%Y%m%d')
    filename = f"stockpool_{date_str}.txt"
    filepath = DATA_DIR / filename
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # 写入表头注释
            f.write(f"# 选股结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# 格式: 股票代码,综合评分\n")
            f.write(f"# 总数: {len(selected)} 只\n")
            f.write("-" * 30 + "\n")
            
            # 遍历每只股票，计算综合评分并保存
            for code, name in selected:
                # 确定市场前缀
                if code.startswith('6') or code.startswith('9'):
                    market = 'sh'
                else:
                    market = 'sz'
                
                # 计算综合评分
                print(f"[INFO] 正在计算 {code} ({name}) 的综合评分...")
                score = calculate_trend_score(market, code)
                
                # 如果评分失败，标记为N/A
                if score is None:
                    score_str = "N/A"
                else:
                    score_str = f"{score:+.1f}"
                
                # 写入文件：股票代码,评分
                f.write(f"{code},{score_str}\n")
        
        print(f"\n[SAVE] 选股结果已保存至: {filepath}")
        print(f"[INFO] 共保存 {len(selected)} 只股票")
        return True
        
    except Exception as e:
        print(f"[ERROR] 保存选股结果失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_all_stocks_from_tdx():
    """
    获取全部A股股票列表
    
    数据来源:
        - akshare (HTTP API): 用于获取最新的股票代码和名称映射。
          由于 mootdx 主要专注于解析通达信本地二进制行情数据，不直接提供全市场股票列表接口，
          因此借用 akshare 的轻量级接口获取列表是最可靠的方案。
    
    Returns:
        DataFrame: 包含 code（代码）和 name（名称）的股票列表
    """
    try:
        # 优化点: akshare 依赖网络请求，若网络不佳可考虑缓存该列表到本地 JSON/CSV，每日更新一次即可
        import akshare as ak
        stock_info = ak.stock_info_a_code_name()
        
        # 过滤规则: 只保留主板(60/00)、创业板(30)、科创板(68)
        # 注意: 北交所(83/87等)未包含在内，如需包含需修改正则
        stock_info = stock_info[stock_info['code'].str.match(r'^(00|30|60|68)')]
        
        print(f"[OK] 成功获取 {len(stock_info)} 只A股股票列表")
        return stock_info
        
    except Exception as e:
        print(f"[ERROR] 获取股票列表失败: {e}")
        return pd.DataFrame()

def is_st_or_terminated(stock_code, stock_name):
    """
    判断是否为ST或退市股
    
    Args:
        stock_code: 股票代码
        stock_name: 股票名称
    
    Returns:
        bool: True表示是ST或退市股，需要剔除
    """
    if not stock_name:
        return False
    
    # 检查名称中是否包含ST、*ST、退等关键字
    if 'ST' in stock_name or '*ST' in stock_name or '退' in stock_name:
        return True
    
    return False


def is_suspended_or_delisted(reader, stock_code, max_data_age_days=3):
    """
    判断股票是否停牌或已摘牌
    
    判断逻辑（多层检测）:
        1. **数据时效性检查**：最新数据日期距离今天超过 max_data_age_days 天，判定为异常
           - 正常交易股票的数据应该是最新的
           - 考虑周末因素：周一运行时，最新数据可能是上周五（间隔2-3天）
           - 如果超过3天没有更新，很可能是停牌或已摘牌
        2. **成交量检查**：最近5个交易日成交量全部为0，判定为停牌
        3. **综合判断**：满足任一条件即过滤
    
    Args:
        reader: mootdx Reader实例
        stock_code: 股票代码（不含市场前缀）
        max_data_age_days: 最大数据年龄（天数），默认3天（考虑周末）
    
    Returns:
        bool: True表示股票停牌或已摘牌，需要剔除
    """
    try:
        from datetime import datetime, timedelta
        
        # 读取日线数据
        df = reader.daily(symbol=stock_code)
        
        if df is None or df.empty:
            return True  # 无数据，视为异常
        
        # ========== 检测1：数据时效性检查 ==========
        latest_date = df.index[-1]  # 最新数据日期
        
        # 如果是字符串类型，转换为datetime
        if isinstance(latest_date, str):
            latest_date = pd.to_datetime(latest_date)
        
        # 计算距离今天的天数
        today = datetime.now()
        days_since_last_update = (today - latest_date).days
        
        # 如果最新数据超过max_data_age_days天，判定为异常（停牌或摘牌）
        # 这个阈值可以容忍周末（最多间隔2-3天）
        if days_since_last_update >= max_data_age_days:
            print(f"  [WARN] {stock_code} 数据过时: 最新日期={latest_date.strftime('%Y-%m-%d')}, 距今{days_since_last_update}天")
            return True
        
        # ========== 检测2：成交量检查 ==========
        # 获取最近5个交易日的成交量
        check_days = min(5, len(df))
        if check_days > 0:
            volumes = df['volume'].iloc[-check_days:].values
            
            # 如果所有成交量都为0，则判定为停牌
            if all(v == 0 for v in volumes):
                return True
        
        return False
        
    except Exception as e:
        # 静默处理错误，但打印调试信息
        # print(f"  ⚠️  {stock_code} 检测异常: {e}")
        return False

def check_continuous_volume(reader, stock_code, period=5):
    """
    检查单只股票是否满足持续放量条件
    
    数据来源:
        - 通达信本地数据 (via mootdx): 读取 vipdoc 目录下的 .day 文件。
          优点是速度极快（本地IO），缺点是需要定期更新通达信数据以保持最新。
    
    逻辑说明:
        - 所谓"持续放量"，此处定义为成交量连续 N 天严格递增。
    
    Args:
        reader: mootdx Reader实例
        stock_code: 股票代码（不含市场前缀）
        period: 连续放量的天数，默认5天
    
    Returns:
        bool: True表示满足持续放量条件
    """
    try:
        # 读取日线数据 (本地二进制解析)
        df = reader.daily(symbol=stock_code)
        
        if df is None or df.empty:
            return False
        
        # 数据处理: 确保时间序列有序
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # 边界检查: 数据长度必须大于需要判断的天数 + 1 (因为要比较前一日)
        if len(df) < period + 1:
            return False
        
        # 提取最近 period+1 天的成交量
        volumes = df['volume'].iloc[-period-1:].values
        
        # 核心逻辑: 检查是否连续 period 天递增
        # volumes[-1] 是今天, volumes[-2] 是昨天...
        # 需要满足: today > yesterday > ... > (today-period)
        for i in range(1, period + 1):
            if volumes[-i] <= volumes[-i-1]:
                return False
        
        return True
        
    except Exception as e:
        # 优化点: 生产环境中建议记录具体错误日志，以便排查是个股数据损坏还是其他问题
        # 静默处理错误，避免在遍历几千只股票时刷屏
        return False

def main(period=5):
    """
    主函数：执行持续放量选股策略
    
    流程概述:
        1. 初始化 mootdx Reader (绑定本地通达信目录)
        2. 获取全市场股票列表 (akshare)
        3. 循环遍历每只股票:
           - 预处理: 剔除 ST/退市股、停牌股
           - 核心计算: 检查本地数据是否满足持续放量
        4. 二次筛选: 对选中的股票计算period天内的涨跌幅，过滤涨幅过大的股票
        5. 输出结果
    
    性能优化点:
        - 当前为单线程串行处理，扫描全市场约需几分钟。
        - 若需提速，可引入 concurrent.futures 进行多进程并行处理 (注意 mootdx 实例线程安全性，建议每个进程独立创建 Reader)。
    
    Args:
        period: 连续放量天数，默认5天
    
    Returns:
        list: 选中的股票列表 [(code, name), ...]
    """
    print("=" * 80)
    print(f"[INFO] 持续放量选股工具（本地数据源）")
    print(f"[INFO] 连续放量天数: {period} 天")
    print(f"[INFO] 涨跌幅过滤阈值: +{MAX_PRICE_CHANGE_PCT}% (超过此涨幅的股票将被过滤)")
    print("=" * 80)
    
    # 初始化 Reader: 指向本地通达信数据目录
    reader = Reader.factory(market='std', tdxdir=TDX_DIR)
    
    # 获取股票列表
    print("\n[LOAD] 正在获取股票列表...")
    stock_list = get_all_stocks_from_tdx()
    
    if stock_list.empty:
        print("[ERROR] 无法获取股票列表，退出")
        return []
    
    selected_codes = []  # 第一阶段选中的股票代码
    total_count = len(stock_list)
    processed_count = 0
    filtered_st_count = 0  # 被过滤的ST股数量
    filtered_suspended_count = 0  # 被过滤的停牌股数量
    
    print(f"\n[SCAN] 开始扫描 {total_count} 只股票...\n")
    
    # 第一阶段：基础筛选（停牌、ST、成交量）
    for idx, row in stock_list.iterrows():
        code = row['code']
        name = row['name']
        
        processed_count += 1
        
        # 进度反馈: 每100只打印一次，减少IO开销
        if processed_count % 100 == 0:
            print(f"[PROGRESS] 进度: {processed_count}/{total_count} ({processed_count/total_count*100:.1f}%)")
        
        # 1. 基本面过滤: 剔除 ST / 退市股
        if is_st_or_terminated(code, name):
            filtered_st_count += 1
            continue
        
        # 2. 停牌/摘牌检测: 剔除停牌股和已摘牌股
        if is_suspended_or_delisted(reader, code):
            filtered_suspended_count += 1
            continue
        
        # 3. 技术面过滤: 判断持续放量
        if check_continuous_volume(reader, code, period):
            selected_codes.append((code, name))
    
    print(f"\n[PHASE1] 第一阶段筛选完成，候选股票: {len(selected_codes)} 只")
    
    # 第二阶段：涨跌幅过滤
    final_selected = []
    filtered_high_change_count = 0
    
    if selected_codes:
        print(f"\n[PHASE2] 开始第二阶段筛选：涨跌幅过滤...\n")
        
        for idx, (code, name) in enumerate(selected_codes, 1):
            # 确定市场前缀
            if code.startswith('6') or code.startswith('9'):
                market = 'sh'
            else:
                market = 'sz'
            
            # 计算时间区间：从period天前到今天
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period+5)  # 多取几天确保有足够数据
            
            # 格式化日期
            start_date_str = start_date.strftime('%Y-%m-%d')
            end_date_str = end_date.strftime('%Y-%m-%d')
            
            # 计算涨跌幅
            change_pct = calculate_price_change(market, code, start_date_str, end_date_str)
            
            if change_pct is None:
                # 计算失败，保守起见保留该股票
                final_selected.append((code, name))
                print(f"[KEEP] {code} {name} (涨跌幅计算失败，保留)")
                continue
            
            # 检查是否超过阈值
            if change_pct >= MAX_PRICE_CHANGE_PCT:
                filtered_high_change_count += 1
                print(f"[FILTER] {code} {name} - 涨跌幅: {change_pct:+.2f}% (超过阈值，过滤)")
            else:
                final_selected.append((code, name))
                print(f"[SELECTED] {code} {name} - 涨跌幅: {change_pct:+.2f}%")
    
    # 输出最终统计结果
    print("\n" + "=" * 80)
    print(f"[DONE] 选股完成！")
    print(f"[INFO] 扫描总数: {total_count} 只")
    print(f"[FILTER] 过滤ST/退市股: {filtered_st_count} 只")
    print(f"[FILTER] 过滤停牌/摘牌股: {filtered_suspended_count} 只")
    print(f"[FILTER] 过滤高涨幅股(>+{MAX_PRICE_CHANGE_PCT}%): {filtered_high_change_count} 只")
    print(f"[RESULT] 最终选中数量: {len(final_selected)} 只")
    print(f"[INFO] 选中比例: {len(final_selected)/total_count*100:.2f}%")
    print("=" * 80)
    
    if final_selected:
        print("\n[LIST] 最终选中股票列表:")
        print("-" * 40)
        for code, name in final_selected:
            print(f"{code}  {name}")
    
    return final_selected

if __name__ == "__main__":
    # 可以修改这里的period参数
    period = 5  # 连续5天放量
    selected_stocks = main(period)
    
    # 保存选股结果到文件
    if selected_stocks:
        save_selected_stocks(selected_stocks)
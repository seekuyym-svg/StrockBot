"""
股票列表管理工具

功能说明:
    1. 扫描通达信本地数据，获取全市场A股代码列表
    2. 检测并标记ST/退市股、停牌/摘牌股
    3. 生成股票白名单和黑名单文件
    4. 每日自动更新，支持增量检测（复牌、摘帽等）

使用方法:
    python local/manage_stock_list.py [--update] [--date YYYYMMDD]

参数说明:
    --update: 强制更新股票列表（默认检查今日是否已更新）
    --date: 指定日期（默认今天）
"""

import pandas as pd
import os
import yaml
from pathlib import Path
from datetime import datetime, timedelta
import sys
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mootdx.reader import Reader
from local.utils import get_stock_name

# ==================== 配置区 ====================
def load_config():
    """加载配置文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, '..', 'config.yaml')
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN] 加载配置文件失败: {e}，使用默认配置")
        return {}

config = load_config()
TDX_DIR = config.get('TDX_DIR', r"D:\Install\zd_zxzq_gm")
DATA_DIR = Path(__file__).parent.parent / "data"

def ensure_data_dir():
    """确保data目录存在"""
    if not DATA_DIR.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)

def scan_all_stocks_from_local():
    """
    从通达信本地数据文件扫描全部A股股票代码
    
    Returns:
        list: 股票代码列表（6位字符串）
    """
    stock_codes = set()
    vipdoc_dir = Path(TDX_DIR) / "vipdoc"
    
    print("[SCAN] 正在扫描本地通达信数据文件...")
    
    for market in ['sh', 'sz']:
        lday_dir = vipdoc_dir / market / "lday"
        
        if not lday_dir.exists():
            print(f"[WARN] 目录不存在: {lday_dir}")
            continue
        
        day_files = list(lday_dir.glob("*.day"))
        
        for day_file in day_files:
            filename = day_file.stem
            
            if len(filename) >= 6:
                code = filename[-6:]
                
                if code.isdigit():
                    # 只保留A股：主板(60/00)、创业板(30)、科创板(68)
                    if code.startswith(('00', '30', '60', '68')):
                        stock_codes.add(code)
    
    stock_list = sorted(list(stock_codes))
    print(f"[OK] 扫描到 {len(stock_list)} 只A股股票")
    
    return stock_list

def check_stock_status(reader, stock_code):
    """
    检查单只股票的状态
    
    Returns:
        dict: {
            'is_st': bool,      # 是否ST
            'is_suspended': bool,  # 是否停牌
            'name': str         # 股票名称
        }
    """
    status = {
        'is_st': False,
        'is_suspended': False,
        'name': ''
    }
    
    try:
        # 获取股票名称
        name = get_stock_name(stock_code)
        status['name'] = name
        
        # 检查是否ST或退市
        if name and ('ST' in name or '*ST' in name or '退' in name):
            status['is_st'] = True
        
        # 检查是否停牌（通过成交量判断）
        df = reader.daily(symbol=stock_code)
        
        if df is None or df.empty:
            status['is_suspended'] = True
            return status
        
        # 检查最近一个交易日成交量
        latest_volume = df['volume'].iloc[-1]
        if latest_volume == 0:
            status['is_suspended'] = True
        
        # 额外检查：数据时效性（超过3天未更新视为异常）
        latest_date = df.index[-1]
        if isinstance(latest_date, str):
            latest_date = pd.to_datetime(latest_date)
        
        days_since_update = (datetime.now() - latest_date).days
        if days_since_update >= 3:
            status['is_suspended'] = True
        
    except Exception as e:
        # 出错时保守处理，标记为停牌
        status['is_suspended'] = True
    
    return status

def load_previous_blacklist(date_str=None):
    """
    加载前一天的黑名单
    
    Args:
        date_str: 日期字符串 YYYYMMDD，默认为昨天
    
    Returns:
        set: 黑名单股票代码集合
    """
    if date_str is None:
        yesterday = datetime.now() - timedelta(days=1)
        date_str = yesterday.strftime('%Y%m%d')
    
    blacklist_file = DATA_DIR / f"blacklist_{date_str}.txt"
    
    if not blacklist_file.exists():
        return set()
    
    try:
        blacklisted_codes = set()
        with open(blacklist_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(',')
                    if parts:
                        blacklisted_codes.add(parts[0])
        
        print(f"[LOAD] 加载前一天黑名单: {len(blacklisted_codes)} 只股票")
        return blacklisted_codes
    except Exception as e:
        print(f"[WARN] 加载黑名单失败: {e}")
        return set()

def save_stock_list(all_stocks, blacklisted_stocks, date_str):
    """
    保存股票列表和黑名单
    
    Args:
        all_stocks: 全量股票列表 [(code, name, status), ...]
        blacklisted_stocks: 黑名单股票集合
        date_str: 日期字符串 YYYYMMDD
    """
    ensure_data_dir()
    
    # 保存全量股票列表
    all_stocks_file = DATA_DIR / f"all_stocks_{date_str}.txt"
    with open(all_stocks_file, 'w', encoding='utf-8') as f:
        f.write(f"# 全量A股股票列表 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 格式: 股票代码,股票名称,状态\n")
        f.write(f"# 状态: NORMAL=正常, ST=ST股, SUSPENDED=停牌, DELISTED=退市\n")
        f.write(f"# 总数: {len(all_stocks)} 只\n")
        f.write("-" * 50 + "\n")
        
        for code, name, status in all_stocks:
            f.write(f"{code},{name},{status}\n")
    
    print(f"[SAVE] 全量股票列表已保存: {all_stocks_file}")
    
    # 保存黑名单
    blacklist_file = DATA_DIR / f"blacklist_{date_str}.txt"
    with open(blacklist_file, 'w', encoding='utf-8') as f:
        f.write(f"# 股票黑名单 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 包含: ST股、退市股、停牌股\n")
        f.write(f"# 格式: 股票代码,股票名称,原因\n")
        f.write(f"# 总数: {len(blacklisted_stocks)} 只\n")
        f.write("-" * 50 + "\n")
        
        for code, name, reason in blacklisted_stocks:
            f.write(f"{code},{name},{reason}\n")
    
    print(f"[SAVE] 黑名单已保存: {blacklist_file}")
    
    # 保存白名单（正常股票）
    whitelist_file = DATA_DIR / f"whitelist_{date_str}.txt"
    whitelist_count = 0
    with open(whitelist_file, 'w', encoding='utf-8') as f:
        f.write(f"# 股票白名单（正常交易股票）- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 可用于选股工具快速过滤\n")
        f.write(f"# 格式: 股票代码\n")
        
        for code, name, status in all_stocks:
            if status == 'NORMAL':
                f.write(f"{code}\n")
                whitelist_count += 1
    
    print(f"[SAVE] 白名单已保存: {whitelist_file} ({whitelist_count} 只)")

def main(force_update=False, target_date=None):
    """
    主函数：生成股票列表和黑名单
    
    Args:
        force_update: 是否强制更新
        target_date: 目标日期 YYYYMMDD，默认今天
    """
    if target_date is None:
        date_str = datetime.now().strftime('%Y%m%d')
    else:
        date_str = target_date
    
    print("=" * 70)
    print("[INFO] 股票列表管理工具")
    print("=" * 70)
    print(f"[INFO] 目标日期: {date_str}")
    print(f"[INFO] 强制更新: {'是' if force_update else '否'}")
    print("=" * 70)
    
    # 检查今日是否已生成
    all_stocks_file = DATA_DIR / f"all_stocks_{date_str}.txt"
    blacklist_file = DATA_DIR / f"blacklist_{date_str}.txt"
    
    if not force_update and all_stocks_file.exists() and blacklist_file.exists():
        print(f"\n[INFO] 今日股票列表已存在，跳过生成")
        print(f"[TIP] 如需重新生成，请使用 --update 参数")
        return
    
    # 初始化 Reader
    try:
        reader = Reader.factory(market='std', tdxdir=TDX_DIR)
        print(f"[OK] 成功初始化 mootdx Reader")
    except Exception as e:
        print(f"[ERROR] 初始化 Reader 失败: {e}")
        return
    
    # 步骤1: 扫描全量股票
    print("\n[STEP 1] 扫描全量A股股票...")
    stock_codes = scan_all_stocks_from_local()
    
    if not stock_codes:
        print("[ERROR] 未扫描到任何股票，请检查 TDX_DIR 配置")
        return
    
    # 步骤2: 加载前一天黑名单（用于对比变化）
    print("\n[STEP 2] 加载前一天黑名单...")
    previous_blacklist = load_previous_blacklist()
    
    # 步骤3: 检测每只股票状态
    print(f"\n[STEP 3] 检测股票状态（共 {len(stock_codes)} 只）...\n")
    
    all_stocks = []  # [(code, name, status), ...]
    blacklisted_stocks = []  # [(code, name, reason), ...]
    
    normal_count = 0
    st_count = 0
    suspended_count = 0
    
    for idx, code in enumerate(stock_codes, 1):
        # 进度显示
        if idx % 100 == 0:
            print(f"[PROGRESS] 已检测: {idx}/{len(stock_codes)}")
        
        # 检查股票状态
        status_info = check_stock_status(reader, code)
        
        name = status_info['name']
        
        # 确定状态
        if status_info['is_st']:
            stock_status = 'ST'
            st_count += 1
            blacklisted_stocks.append((code, name, 'ST或退市'))
        elif status_info['is_suspended']:
            stock_status = 'SUSPENDED'
            suspended_count += 1
            blacklisted_stocks.append((code, name, '停牌或数据过时'))
        else:
            stock_status = 'NORMAL'
            normal_count += 1
        
        all_stocks.append((code, name, stock_status))
    
    # 步骤4: 对比变化（可选）
    if previous_blacklist:
        current_blacklist_codes = {item[0] for item in blacklisted_stocks}
        
        # 新加入黑名单的股票
        new_blacklisted = current_blacklist_codes - previous_blacklist
        # 从黑名单移除的股票（复牌或摘帽）
        removed_blacklisted = previous_blacklist - current_blacklist_codes
        
        if new_blacklisted:
            print(f"\n[CHANGE] 新加入黑名单: {len(new_blacklisted)} 只")
            for code in list(new_blacklisted)[:10]:  # 只显示前10个
                print(f"   - {code}")
            if len(new_blacklisted) > 10:
                print(f"   ... 还有 {len(new_blacklisted) - 10} 只")
        
        if removed_blacklisted:
            print(f"\n[CHANGE] 从黑名单移除（复牌/摘帽）: {len(removed_blacklisted)} 只")
            for code in list(removed_blacklisted)[:10]:
                print(f"   + {code}")
            if len(removed_blacklisted) > 10:
                print(f"   ... 还有 {len(removed_blacklisted) - 10} 只")
    
    # 步骤5: 保存结果
    print(f"\n[STEP 4] 保存结果...")
    save_stock_list(all_stocks, blacklisted_stocks, date_str)
    
    # 输出统计
    print("\n" + "=" * 70)
    print("[INFO] 股票列表生成完成！")
    print("=" * 70)
    print(f"[STAT] 全量股票: {len(all_stocks)} 只")
    print(f"[STAT] 正常股票: {normal_count} 只")
    print(f"[STAT] ST/退市: {st_count} 只")
    print(f"[STAT] 停牌/异常: {suspended_count} 只")
    print(f"[STAT] 黑名单总计: {len(blacklisted_stocks)} 只")
    print("=" * 70)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='股票列表管理工具')
    parser.add_argument('--update', action='store_true', 
                        help='强制更新股票列表')
    parser.add_argument('--date', type=str, default=None,
                        help='指定日期 (YYYYMMDD)，默认今天')
    
    args = parser.parse_args()
    
    main(force_update=args.update, target_date=args.date)

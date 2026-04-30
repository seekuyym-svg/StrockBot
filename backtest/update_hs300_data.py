# -*- coding: utf-8 -*-
"""
更新沪深300历史数据

从东方财富网获取最新的沪深300指数数据，并保存到本地CSV文件。
建议定期运行此脚本（如每周或每月）以保持数据最新。
"""

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime


def update_hs300_data():
    """
    从东方财富网获取沪深300历史数据并保存到本地
    
    Returns:
        bool: 是否成功
    """
    print("=" * 80)
    print("更新沪深300历史数据")
    print("=" * 80)
    
    try:
        # 东方财富API - 沪深300指数K线
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": "1.000300",  # 1表示上海交易所，000300是沪深300代码
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",  # 日K线
            "fqt": "1",    # 前复权
            "beg": "20200101",  # 从2020年开始
            "end": "20261231",  # 到2026年底
            "lmt": "100000"     # 最大记录数
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        print("\n[STEP 1] 正在从东方财富网获取数据...")
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get('data') or not data['data'].get('klines'):
            print("❌ 未获取到数据")
            return False
        
        klines = data['data']['klines']
        print(f"✅ 成功获取 {len(klines)} 条记录")
        
        # 解析数据
        print("\n[STEP 2] 正在解析数据...")
        records = []
        for line in klines:
            parts = line.split(',')
            if len(parts) >= 6:
                date_str = parts[0]
                open_price = float(parts[1])
                close_price = float(parts[2])
                high_price = float(parts[3])
                low_price = float(parts[4])
                volume = float(parts[5])
                
                records.append({
                    'date': pd.to_datetime(date_str),
                    'open': open_price,
                    'close': close_price,
                    'high': high_price,
                    'low': low_price,
                    'volume': volume
                })
        
        df = pd.DataFrame(records)
        df = df.sort_values('date').reset_index(drop=True)
        
        print(f"   日期范围: {df.iloc[0]['date'].strftime('%Y-%m-%d')} 至 {df.iloc[-1]['date'].strftime('%Y-%m-%d')}")
        print(f"   起始价格: {df.iloc[0]['close']:.2f}")
        print(f"   结束价格: {df.iloc[-1]['close']:.2f}")
        
        # 计算收益率
        start_price = df.iloc[0]['close']
        end_price = df.iloc[-1]['close']
        return_pct = (end_price - start_price) / start_price * 100
        print(f"   总收益率: {return_pct:.2f}%")
        
        # 保存为CSV
        print("\n[STEP 3] 正在保存到本地文件...")
        csv_file = Path("data/hs300_eastmoney.csv")
        
        # 确保目录存在
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 备份旧文件（如果存在）
        if csv_file.exists():
            backup_file = csv_file.with_suffix(f'.{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
            csv_file.rename(backup_file)
            print(f"   已备份旧文件: {backup_file.name}")
        
        # 保存新文件
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"   ✅ 已保存到: {csv_file}")
        
        # 显示文件大小
        file_size = csv_file.stat().st_size
        print(f"   文件大小: {file_size / 1024:.2f} KB")
        
        print("\n" + "=" * 80)
        print("✅ 数据更新完成！")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = update_hs300_data()
    
    if success:
        print("\n💡 提示:")
        print("   - 建议定期运行此脚本以保持数据最新")
        print("   - 可以设置定时任务（如每周执行一次）")
        print("   - 回测时将自动使用此本地数据文件")
    else:
        print("\n⚠️ 数据更新失败，请检查网络连接或稍后重试")

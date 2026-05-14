# -*- coding: utf-8 -*-
"""
更新沪深300历史数据（增量更新模式）

从东方财富网获取沪深300指数数据，并保存到本地CSV文件。
支持增量更新：自动检测本地最新日期，只获取新增数据。

使用示例:
    # 增量更新（从本地最新日期+1天到今天）
    python backtest/update_hs300_data.py
    
    # 指定日期范围
    python backtest/update_hs300_data.py --start 2026-04-01 --end 2026-04-30
    
    # 重新获取完整历史数据
    python backtest/update_hs300_data.py --start 2020-01-01
"""

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import argparse


def update_hs300_data(start_date: str = None, end_date: str = None):
    """
    从东方财富网获取沪深300数据并保存到本地（支持增量更新）
    
    Args:
        start_date: 起始日期 (YYYY-MM-DD)，默认从本地文件最新日期+1天
        end_date: 结束日期 (YYYY-MM-DD)，默认为今天
    
    Returns:
        bool: 是否成功
    """
    print("=" * 80)
    print("更新沪深300数据")
    print("=" * 80)
    
    # 使用项目根目录的 data 文件夹
    project_root = Path(__file__).parent.parent
    csv_file = project_root / "data" / "hs300_eastmoney.csv"
    
    try:
        # ========== 智能确定日期范围 ==========
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
            print(f"[INFO] 使用当前日期作为结束日期: {end_date}")
        
        if start_date is None:
            # 尝试从本地文件读取最新日期
            if csv_file.exists():
                print("[INFO] 检测到本地数据文件，正在读取最新日期...")
                try:
                    last_df = pd.read_csv(csv_file, parse_dates=['date'])
                    if not last_df.empty:
                        latest_date = last_df['date'].max()
                        start_date = (latest_date + timedelta(days=1)).strftime('%Y-%m-%d')
                        print(f"[INFO] 本地最新日期: {latest_date.strftime('%Y-%m-%d')}")
                        print(f"[INFO] 将更新从 {start_date} 到 {end_date} 的数据")
                    else:
                        start_date = "2020-01-01"
                        print("[WARN] 本地文件为空，将获取完整历史数据")
                except Exception as e:
                    print(f"[WARN] 读取本地文件失败: {e}，将获取完整历史数据")
                    start_date = "2020-01-01"
            else:
                start_date = "2020-01-01"
                print("[INFO] 首次运行，将获取完整历史数据（2020-01-01 至今）")
        else:
            print(f"[INFO] 使用指定起始日期: {start_date}")
        
        print(f"[INFO] 最终日期范围: {start_date} 至 {end_date}")
        
        # ========== 从东方财富网获取数据 ==========
        url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
        params = {
            "secid": "1.000300",  # 1表示上海交易所，000300是沪深300代码
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "klt": "101",  # 日K线
            "fqt": "1",    # 前复权
            "beg": start_date.replace('-', ''),  # 起始日期 YYYYMMDD
            "end": end_date.replace('-', ''),    # 结束日期 YYYYMMDD
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
        
        # ========== 解析数据 ==========
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
        
        new_df = pd.DataFrame(records)
        new_df = new_df.sort_values('date').reset_index(drop=True)
        
        if new_df.empty:
            print("⚠️  没有新数据需要更新")
            return True
        
        print(f"   新数据日期范围: {new_df.iloc[0]['date'].strftime('%Y-%m-%d')} 至 {new_df.iloc[-1]['date'].strftime('%Y-%m-%d')}")
        print(f"   起始价格: {new_df.iloc[0]['close']:.2f}")
        print(f"   结束价格: {new_df.iloc[-1]['close']:.2f}")
        
        # 计算收益率
        start_price = new_df.iloc[0]['close']
        end_price = new_df.iloc[-1]['close']
        return_pct = (end_price - start_price) / start_price * 100
        print(f"   区间收益率: {return_pct:.2f}%")
        
        # ========== 合并数据并保存 ==========
        print("\n[STEP 3] 正在保存数据...")
        
        # 确保目录存在
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 如果本地文件存在，合并新旧数据
        if csv_file.exists():
            print("[INFO] 检测到本地文件，正在合并数据...")
            
            # 备份旧文件
            backup_file = csv_file.with_suffix(f'.{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
            csv_file.rename(backup_file)
            print(f"   [BACKUP] 已备份旧文件: {backup_file.name}")
            
            # 读取旧数据
            old_df = pd.read_csv(backup_file, parse_dates=['date'])
            print(f"   原有数据: {len(old_df)} 条")
            
            # 合并并去重
            df = pd.concat([old_df, new_df], ignore_index=True)
            df = df.drop_duplicates(subset=['date'], keep='last')
            df = df.sort_values('date').reset_index(drop=True)
            
            print(f"   [OK] 合并完成: 原有 {len(old_df)} 条 + 新增 {len(new_df)} 条 = 总计 {len(df)} 条")
        else:
            # 首次运行，直接使用新数据
            df = new_df
            print(f"   [OK] 首次保存: {len(df)} 条记录")
        
        # 保存为CSV
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        print(f"   ✅ 已保存到: {csv_file}")
        
        # 显示文件大小
        file_size = csv_file.stat().st_size
        print(f"   文件大小: {file_size / 1024:.2f} KB")
        
        # 显示最终统计
        print(f"\n   最终日期范围: {df.iloc[0]['date'].strftime('%Y-%m-%d')} 至 {df.iloc[-1]['date'].strftime('%Y-%m-%d')}")
        print(f"   总记录数: {len(df)} 条")
        
        print("\n" + "=" * 80)
        print("✅ 数据更新完成！")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='更新沪深300历史数据（支持增量更新）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 增量更新（从本地最新日期+1天到今天）
  python backtest/update_hs300_data.py
  
  # 指定日期范围
  python backtest/update_hs300_data.py --start 2026-04-01 --end 2026-04-30
  
  # 重新获取完整历史数据
  python backtest/update_hs300_data.py --start 2020-01-01
        """
    )
    
    parser.add_argument('--start', type=str, help='起始日期 (YYYY-MM-DD)，默认从本地最新日期+1天')
    parser.add_argument('--end', type=str, help='结束日期 (YYYY-MM-DD)，默认为今天')
    
    args = parser.parse_args()
    
    # 验证日期格式
    def validate_date(date_str, name):
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            print(f"❌ 错误: {name} 日期格式不正确，应为 YYYY-MM-DD")
            return False
        return True
    
    if args.start and not validate_date(args.start, '--start'):
        return
    
    if args.end and not validate_date(args.end, '--end'):
        return
    
    # 执行更新
    success = update_hs300_data(start_date=args.start, end_date=args.end)
    
    if success:
        print("\n💡 提示:")
        print("   - 建议定期运行此脚本以保持数据最新（如每周一次）")
        print("   - 回测时将自动使用此本地数据文件")
        print("   - 如需重新获取完整历史数据，使用: --start 2020-01-01")
    else:
        print("\n⚠️ 数据更新失败，请检查网络连接或稍后重试")


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
通用指数历史数据更新脚本（增量更新模式）

从东方财富网获取指定指数历史K线数据，保存到本地CSV文件。
增量模式下只获取缺失数据并追加到文件末尾，不碰旧数据。

支持任意东方财富指数（通过 --secid 指定）

使用示例:
    # 增量更新科创综指（从本地最新日期+1天到今天）
    python trade_decision/update_index_data.py --name kc_index --secid 1.000680
    
    # 增量更新沪深300
    python trade_decision/update_index_data.py --name hs300_eastmoney --secid 1.000300
    
    # 全量更新（指定日期范围）
    python trade_decision/update_index_data.py --name kc_index --secid 1.000680 --start 2020-01-01
    
    # 重命名（可指定输出文件名，默认 data/{name}.csv）
    python trade_decision/update_index_data.py --name kc_index --secid 1.000680 --out data/my_kc.csv
"""

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import argparse


def fetch_data_from_api(secid: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从东方财富网获取指数历史K线数据

    Args:
        secid: 东方财富secid，如 "1.000300"（沪深300）、"1.000680"（科创综指）
        start_date: 起始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)

    Returns:
        DataFrame，列: date, open, close, high, low, volume
    """
    url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",   # 日K线
        "fqt": "1",     # 前复权
        "beg": start_date.replace('-', ''),
        "end": end_date.replace('-', ''),
        "lmt": "100000"
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    response = requests.get(url, params=params, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()

    if not data.get('data') or not data['data'].get('klines'):
        return pd.DataFrame()

    records = []
    for line in data['data']['klines']:
        parts = line.split(',')
        if len(parts) >= 6:
            records.append({
                'date': pd.to_datetime(parts[0]),
                'open': float(parts[1]),
                'close': float(parts[2]),
                'high': float(parts[3]),
                'low': float(parts[4]),
                'volume': float(parts[5]),
            })

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values('date').reset_index(drop=True)
    return df


def update_index_data(index_name: str, secid: str, output_path: str = None,
                      start_date: str = None, end_date: str = None) -> bool:
    """
    从东方财富网获取指数数据并保存到本地（增量/全量更新模式）

    增量模式：只获取缺失数据，直接追加到CSV末尾
    全量模式（指定 --start）：覆盖写入完整数据

    Args:
        index_name: 指数名称（仅用于显示）
        secid: 东方财富secid
        output_path: 输出CSV路径，默认 data/{name}.csv
        start_date: 起始日期，None=增量模式，指定=全量模式
        end_date: 结束日期，默认今天

    Returns:
        bool: 是否成功
    """
    print("=" * 80)
    print(f"更新 {index_name} 数据")
    print("=" * 80)

    project_root = Path(__file__).parent.parent

    if output_path is None:
        csv_file = project_root / "data" / f"{index_name}.csv"
    else:
        csv_file = Path(output_path)
        if not csv_file.is_absolute():
            csv_file = project_root / csv_file

    try:
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')

        # ========== 判断模式：增量 vs 全量 ==========
        if start_date is not None:
            mode = "全量"
            print(f"[INFO] 全量模式: {start_date} 至 {end_date}")
        else:
            mode = "增量"
            if csv_file.exists():
                try:
                    last_df = pd.read_csv(csv_file, parse_dates=['date'])
                    if not last_df.empty:
                        latest_date = last_df['date'].max()
                        start_date = (latest_date + timedelta(days=1)).strftime('%Y-%m-%d')
                        print(f"[INFO] 增量模式: 本地最新 {latest_date.strftime('%Y-%m-%d')}, 更新 {start_date} ~ {end_date}")
                    else:
                        start_date = "2020-01-01"
                        mode = "全量（本地文件为空）"
                except Exception:
                    start_date = "2020-01-01"
                    mode = "全量（读取本地文件失败）"
            else:
                start_date = "2020-01-01"
                mode = "全量（首次运行）"

        # 如果起始日期大于结束日期，说明已经是最新
        if start_date > end_date:
            print("✅ 本地数据已是最新，无需更新")
            return True

        # ========== 获取数据 ==========
        print(f"\n[STEP 1] 正在从东方财富网获取数据 ({mode})...")
        print(f"   secid: {secid}")
        print(f"   日期范围: {start_date} ~ {end_date}")

        df = fetch_data_from_api(secid, start_date, end_date)

        if df.empty:
            print("⚠️  未获取到新数据")
            return True

        print(f"✅ 获取 {len(df)} 条记录: {df.iloc[0]['date'].strftime('%Y-%m-%d')} ~ {df.iloc[-1]['date'].strftime('%Y-%m-%d')}")
        print(f"   起止价格: {df.iloc[0]['close']:.2f} → {df.iloc[-1]['close']:.2f}")

        ret = (df.iloc[-1]['close'] - df.iloc[0]['close']) / df.iloc[0]['close'] * 100
        print(f"   区间收益率: {ret:.2f}%")

        # ========== 保存数据 ==========
        print(f"\n[STEP 2] 正在保存数据...")
        csv_file.parent.mkdir(parents=True, exist_ok=True)

        if mode.startswith("全量"):
            df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            print(f"✅ 全量写入 {len(df)} 条 → {csv_file.name}")
        else:
            df.to_csv(csv_file, mode='a', header=False, index=False, encoding='utf-8-sig')
            print(f"✅ 追加 {len(df)} 条 → {csv_file.name}（旧数据未改动）")

        final_df = pd.read_csv(csv_file, parse_dates=['date'])
        print(f"\n   最终: {len(final_df)} 条, {final_df.iloc[0]['date'].strftime('%Y-%m-%d')} ~ {final_df.iloc[-1]['date'].strftime('%Y-%m-%d')}")
        print(f"   文件大小: {csv_file.stat().st_size / 1024:.1f} KB")

        print("\n" + "=" * 80)
        print(f"✅ {index_name} 数据更新完成！")
        print("=" * 80)
        return True

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    parser = argparse.ArgumentParser(
        description='通用指数历史数据更新（增量/全量）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  # 增量更新科创综指
  python trade_decision/update_index_data.py --name kc_index --secid 1.000680

  # 增量更新沪深300
  python trade_decision/update_index_data.py --name hs300_eastmoney --secid 1.000300

  # 全量更新
  python trade_decision/update_index_data.py --name kc_index --secid 1.000680 --start 2020-01-01

  # 自定义输出路径
  python trade_decision/update_index_data.py --name kc_index --secid 1.000680 --out data/my_kc.csv

支持任意东方财富指数 secid:
  1.000300  沪深300
  1.000001  上证指数
  1.000016  上证50
  1.000688  科创50
  1.000680  科创综指
  0.399001  深证成指
  0.399006  创业板指
        """
    )
    parser.add_argument('--name', type=str, required=True,
                        help='指数名称标识（用于文件名和显示，如 kc_index）')
    parser.add_argument('--secid', type=str, required=True,
                        help='东方财富secid，如 1.000680（科创综指）')
    parser.add_argument('--out', type=str, default=None,
                        help='输出CSV路径（默认 data/{name}.csv）')
    parser.add_argument('--start', type=str, default=None,
                        help='起始日期 (YYYY-MM-DD)，指定则全量覆盖，不指定则增量追加')
    parser.add_argument('--end', type=str, default=None,
                        help='结束日期 (YYYY-MM-DD)，默认今天')

    args = parser.parse_args()

    success = update_index_data(
        index_name=args.name,
        secid=args.secid,
        output_path=args.out,
        start_date=args.start,
        end_date=args.end
    )

    if success:
        print("\n💡 提示: 建议定期增量更新（每周一次），保持本地数据最新")
    else:
        print("\n⚠️  更新失败，请检查网络后重试")


if __name__ == "__main__":
    main()

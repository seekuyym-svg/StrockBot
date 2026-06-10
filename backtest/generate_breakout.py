# -*- coding: utf-8 -*-
"""
横盘突破选股工具

功能：
1. 识别"长期横盘整理 + 突然放量突破"的股票
2. 独立于原来的 generate_stockpool.py，互不干扰
3. 输出文件格式同原股票池一致，可直接用于评分工具

选股逻辑：
  ① 横盘识别：过去60天内最高最低波动 < 10%
  ② 放量突破：今日收盘 > 60天最高价（突破上沿）
  ③ 放量确认：今日成交量 > 20日均量 × 1.5
  ④ 站稳确认：收阳线 + 不冲高回落（上影线 < 5%）

使用方法：
    python backtest/generate_breakout.py --date 2026-04-13
    python backtest/generate_breakout.py --start-date 2026-01-01 --end-date 2026-04-30
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import requests
from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from local.utils import load_whitelist
from mootdx.reader import Reader


class BreakoutGenerator:
    """横盘突破选股器"""
    
    def __init__(self, config: dict):
        """
        初始化横盘突破选股器
        
        Args:
            config: 配置字典
                - start_date: 起始日期
                - end_date: 结束日期
                - tdx_dir: 通达信目录
                - consolidation_days: 横盘天数，默认60
                - consolidation_range: 横盘波动幅度上限(%)，默认10
                - vol_ratio_threshold: 放量倍数阈值，默认1.5
                - pullback_threshold: 冲高回落上限(%)，默认5
        """
        self.start_date = config['start_date']
        self.end_date = config['end_date']
        self.tdx_dir = config.get('tdx_dir', r"D:\Install\zd_zxzq_gm")
        
        # 从 config.yaml 读取横盘突破参数（作为默认值）
        file_cfg = {}
        try:
            import yaml
            cfg_file = project_root / "config.yaml"
            if cfg_file.exists():
                with open(cfg_file, 'r', encoding='utf-8') as f:
                    y = yaml.safe_load(f)
                    file_cfg = y.get('breakout', {})
        except Exception:
            pass
        
        # 横盘突破参数（优先级：config字典 > config.yaml > 硬编码默认值）
        self.consolidation_days = config.get('consolidation_days', file_cfg.get('consolidation_days', 60))
        self.consolidation_range = config.get('consolidation_range', file_cfg.get('consolidation_range', 15.0))
        self.vol_ratio_threshold = config.get('vol_ratio_threshold', file_cfg.get('vol_ratio_threshold', 1.5))
        self.pullback_threshold = config.get('pullback_threshold', file_cfg.get('pullback_threshold', 5.0))
        
        # 初始化通达信本地数据读取器
        self.reader = Reader.factory(market='std', tdxdir=self.tdx_dir)
        
        # 缓存
        self.whitelist = set()
        self.data_dir = project_root / "data"
        self.data_cache = {}
        self.cache_dir = project_root / "data" / "kline_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[INIT] 横盘突破选股器初始化完成")
        logger.info(f"  - 回测周期: {self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}")
        logger.info(f"  - 横盘天数: {self.consolidation_days}天")
        logger.info(f"  - 波动上限: {self.consolidation_range}%")
        logger.info(f"  - 放量倍数: ≥{self.vol_ratio_threshold}x")
        logger.info(f"  - 冲高回落: <{self.pullback_threshold}%")
    
    def get_stock_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """
        获取股票K线数据（从通达信本地数据读取）
        """
        if stock_code in self.data_cache:
            return self.data_cache[stock_code]
        
        try:
            df = self.reader.daily(symbol=stock_code)
            if df is None or df.empty:
                self.data_cache[stock_code] = None
                return None
            
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            self.data_cache[stock_code] = df
            return df
        except Exception:
            self.data_cache[stock_code] = None
            return None
    
    def load_whitelist(self):
        """加载白名单"""
        data_dir = project_root / "data"
        whitelist_files = sorted(data_dir.glob("whitelist_*.txt"))
        
        if not whitelist_files:
            raise ValueError(f"未找到白名单文件，请先运行 local/manage_stock_list.py --update")
        
        latest_file = whitelist_files[-1]
        with open(latest_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.whitelist.add(line)
        
        logger.info(f"[LOAD] 加载白名单: {latest_file.name} ({len(self.whitelist)}只)")
    
    def get_trading_days(self) -> List[datetime]:
        """获取交易日列表"""
        try:
            import akshare as ak
            trade_dates_df = ak.tool_trade_date_hist_sina()
            if trade_dates_df is None or trade_dates_df.empty:
                return self._get_trading_days_fallback()
            
            trade_dates = pd.to_datetime(trade_dates_df['trade_date']).tolist()
            trading_days = [d for d in trade_dates if self.start_date <= d <= self.end_date]
            trading_days.sort()
            logger.info(f"[INFO] 获取 {len(trading_days)} 个交易日")
            return trading_days
        except Exception:
            return self._get_trading_days_fallback()
    
    def _get_trading_days_fallback(self) -> List[datetime]:
        """降级：仅过滤周末"""
        days = []
        current = self.start_date
        while current <= self.end_date:
            if current.weekday() < 5:
                days.append(current)
            current += timedelta(days=1)
        return days
    
    def check_breakout(self, stock_code: str, check_date: datetime) -> Optional[dict]:
        """
        检查股票是否满足横盘突破条件
        
        Returns:
            dict: 通过时返回关键数据
            None: 不满足条件
        """
        try:
            df = self.get_stock_data(stock_code)
            if df is None or df.empty:
                return None
            
            df_before = df[df.index <= check_date]
            # 需要至少 consolidation_days + 20天数据用于均线计算
            if len(df_before) < self.consolidation_days + 20:
                return None
            
            # === 条件①：横盘识别（过去 consolidation_days 天内波动 < 阈值）===
            high_period = df_before['high'].iloc[-self.consolidation_days:].max()
            low_period = df_before['low'].iloc[-self.consolidation_days:].min()
            range_pct = (high_period - low_period) / low_period * 100
            
            if range_pct >= self.consolidation_range:
                return None  # 波动太大，不是横盘
            
            latest_close = df_before['close'].iloc[-1]
            latest_open = df_before['open'].iloc[-1]
            latest_high = df_before['high'].iloc[-1]
            latest_vol = df_before['volume'].iloc[-1]
            
            # === 条件②：放量突破上沿 ===
            if latest_close <= high_period:
                return None  # 收盘价没突破横盘上沿
            
            # === 条件③：放量确认 ===
            vol_ma20 = df_before['volume'].rolling(20).mean().iloc[-1]
            vol_ratio = latest_vol / vol_ma20 if vol_ma20 > 0 else 1
            if vol_ratio < self.vol_ratio_threshold:
                return None  # 放量不够
            
            # === 条件④：站稳确认（收阳线 + 不冲高回落）===
            if latest_close <= latest_open:
                return None  # 收阴线，不算站稳
            
            # 冲高回落检查
            pullback = (latest_high - latest_close) / latest_high * 100
            if pullback >= self.pullback_threshold:
                return None  # 冲高回落太多，不算站稳
            
            # === 条件⑤：连续3天小幅新高（每天涨幅1%~5%）===
            # 目的：确认突破是稳步推进的真突破，排除一日游和爆拉出货
            closes_3d = df_before['close'].iloc[-3:].values
            for i in range(1, len(closes_3d)):
                daily_ret = (closes_3d[i] - closes_3d[i-1]) / closes_3d[i-1] * 100
                if not (1 <= daily_ret <= 5):
                    return None  # 涨幅不在1%~5%范围内
            
            # 全部通过
            return {
                'close': round(float(latest_close), 2),
                'high_60d': round(float(high_period), 2),
                'low_60d': round(float(low_period), 2),
                'range_pct': round(float(range_pct), 2),
                'vol_ratio': round(float(vol_ratio), 2),
                'pullback': round(float(pullback), 2),
            }
            
        except Exception:
            return None
    
    def save_results(self, date: datetime, results: Dict[str, dict]):
        """保存选股结果"""
        if not results:
            logger.debug(f"[SKIP] {date.strftime('%Y-%m-%d')}: 无横盘突破股票")
            return
        
        date_str = date.strftime('%Y%m%d')
        filename = f"breakout_{date_str}.txt"
        filepath = self.data_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# 横盘突破选股结果 - {date.strftime('%Y-%m-%d')}\n")
            f.write(f"# 总数: {len(results)} 只\n")
            f.write(f"# 格式: 股票代码,收盘价,横盘上沿,波动率%,量比,上影线%\n")
            f.write("-" * 60 + "\n")
            f.write("code,close,high_60d,range_pct,vol_ratio,pullback\n")
            
            for code in sorted(results.keys()):
                info = results[code]
                f.write(f"{code},{info['close']},{info['high_60d']},{info['range_pct']},{info['vol_ratio']},{info['pullback']}\n")
        
        logger.info(f"[SAVE] {date.strftime('%Y-%m-%d')}: 保存 {len(results)} 只 -> {filename}")
    
    def diagnose(self, stock_code: str, check_date: str):
        """
        对单只股票逐条件诊断，输出每个条件的通过情况
        """
        check_dt = pd.to_datetime(check_date)
        
        print(f"\n{'='*60}")
        print(f"  横盘突破诊断 - {stock_code} - {check_date}")
        print(f"{'='*60}")
        
        df = self.get_stock_data(stock_code)
        if df is None or df.empty:
            print("❌ 无法读取股票数据")
            return
        
        df_before = df[df.index <= check_dt]
        print(f"\n数据条数: {len(df_before)}")
        
        if len(df_before) < self.consolidation_days + 20:
            print(f"❌ 数据不足: {len(df_before)}条 < 需要{self.consolidation_days + 20}条")
            return
        
        # 条件①
        high_period = df_before['high'].iloc[-self.consolidation_days:].max()
        low_period = df_before['low'].iloc[-self.consolidation_days:].min()
        range_pct = (high_period - low_period) / low_period * 100
        print(f"\n{'─'*50}")
        print(f"条件①: 横盘{self.consolidation_days}天波动 < {self.consolidation_range}%?")
        print(f"  最高 {high_period:.2f}, 最低 {low_period:.2f}")
        print(f"  波动率: {range_pct:.2f}%")
        if range_pct >= self.consolidation_range:
            print(f"  ❌ 波动率{range_pct:.2f}% >= {self.consolidation_range}%，不是横盘")
        else:
            print(f"  ✅ 波动率{range_pct:.2f}% < {self.consolidation_range}%，横盘确认")
        
        latest_close = df_before['close'].iloc[-1]
        latest_open = df_before['open'].iloc[-1]
        latest_high = df_before['high'].iloc[-1]
        latest_vol = df_before['volume'].iloc[-1]
        
        # 条件②
        print(f"\n{'─'*50}")
        print(f"条件②: 收盘价 > 横盘上沿({high_period:.2f})?")
        print(f"  收盘价: {latest_close:.2f}")
        if latest_close <= high_period:
            print(f"  ❌ 收盘{latest_close:.2f} <= 上沿{high_period:.2f}，未突破")
        else:
            print(f"  ✅ 收盘{latest_close:.2f} > 上沿{high_period:.2f}，突破")
        
        # 条件③
        vol_ma20 = df_before['volume'].rolling(20).mean().iloc[-1]
        vol_ratio = latest_vol / vol_ma20 if vol_ma20 > 0 else 1
        print(f"\n{'─'*50}")
        print(f"条件③: 量比 >= {self.vol_ratio_threshold}x?")
        print(f"  今日量: {latest_vol:.0f}, 20日均量: {vol_ma20:.0f}")
        print(f"  量比: {vol_ratio:.2f}x")
        if vol_ratio < self.vol_ratio_threshold:
            print(f"  ❌ 量比{vol_ratio:.2f}x < {self.vol_ratio_threshold}x，放量不够")
        else:
            print(f"  ✅ 量比{vol_ratio:.2f}x >= {self.vol_ratio_threshold}x")
        
        # 条件④
        pullback = (latest_high - latest_close) / latest_high * 100
        print(f"\n{'─'*50}")
        print(f"条件④: 收阳线 + 上影线 < {self.pullback_threshold}%?")
        print(f"  开盘: {latest_open:.2f}, 收盘: {latest_close:.2f}, 最高: {latest_high:.2f}")
        print(f"  上影线: {pullback:.2f}%")
        cond4_fail = False
        if latest_close <= latest_open:
            print(f"  ❌ 收阴线(开{latest_open:.2f} > 收{latest_close:.2f})")
            cond4_fail = True
        elif pullback >= self.pullback_threshold:
            print(f"  ❌ 上影线{pullback:.2f}% >= {self.pullback_threshold}%，冲高回落")
            cond4_fail = True
        else:
            print(f"  ✅ 收阳线 + 上影线{pullback:.2f}% < {self.pullback_threshold}%")
        
        # 条件⑤
        closes_3d = df_before['close'].iloc[-3:].values
        print(f"\n{'─'*50}")
        print(f"条件⑤: 连续3天涨幅1%~5%?")
        dates_3d = df_before.index[-3:].strftime('%m-%d')
        cond5_fail = False
        for i in range(1, len(closes_3d)):
            daily_ret = (closes_3d[i] - closes_3d[i-1]) / closes_3d[i-1] * 100
            mark = "✅" if 1 <= daily_ret <= 5 else "❌"
            if not (1 <= daily_ret <= 5):
                cond5_fail = True
            print(f"  {mark} {dates_3d[i-1]}→{dates_3d[i]}: {closes_3d[i-1]:.2f}→{closes_3d[i]:.2f} 涨幅{daily_ret:.2f}%")
        
        # 总结
        print(f"\n{'='*60}")
        fails = []
        if range_pct >= self.consolidation_range:
            fails.append("①横盘")
        if latest_close <= high_period:
            fails.append("②突破")
        if vol_ratio < self.vol_ratio_threshold:
            fails.append("③放量")
        if cond4_fail:
            fails.append("④站稳")
        if cond5_fail:
            fails.append("⑤连续涨")
        
        if fails:
            print(f"  结果: ❌ 不通过 (未通过条件: {' + '.join(fails)})")
        else:
            print(f"  结果: ✅ 全部通过！")
        print(f"{'='*60}\n")
    
    def run(self):
        """执行横盘突破选股"""
        logger.info("=" * 80)
        logger.info("[START] 横盘突破选股")
        logger.info("=" * 80)
        
        # 1. 加载白名单
        logger.info("\n[STEP 1] 加载白名单...")
        self.load_whitelist()
        
        # 2. 获取交易日
        logger.info("\n[STEP 2] 获取交易日...")
        trading_days = self.get_trading_days()
        
        # 3. 逐日选股
        logger.info(f"\n[STEP 3] 开始选股（共{len(trading_days)}个交易日）...\n")
        total_found = 0
        
        for idx, current_date in enumerate(trading_days):
            results = {}
            
            for stock_code in self.whitelist:
                info = self.check_breakout(stock_code, current_date)
                if info is not None:
                    results[stock_code] = info
            
            self.save_results(current_date, results)
            total_found += len(results)
            
            if (idx + 1) % 10 == 0:
                progress = (idx + 1) / len(trading_days) * 100
                logger.info(f"[PROGRESS] {idx+1}/{len(trading_days)} ({progress:.0f}%) - 累计找到 {total_found} 只")
        
        logger.info(f"\n[DONE] 完成！共 {total_found} 只横盘突破股票")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="横盘突破选股工具")
    parser.add_argument('--start-date', type=str, help='起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='结束日期 (YYYY-MM-DD)')
    parser.add_argument('--date', type=str, help='指定日期 (YYYY-MM-DD)')
    parser.add_argument('--consolidation-days', type=int, default=60, help='横盘天数，默认60')
    parser.add_argument('--consolidation-range', type=float, default=15.0, help='横盘波动上限(%%), 默认15')
    parser.add_argument('--vol-ratio', type=float, default=1.5, help='放量倍数, 默认1.5')
    parser.add_argument('--diagnose', type=str, help='诊断单只股票 (股票代码)，需配合--date使用')
    
    args = parser.parse_args()
    
    # 读取通达信目录（诊断和选股都需要）
    try:
        import yaml
        config_file = project_root / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                tdx_dir = yaml_config.get('TDX_DIR', r"D:\Install\zd_zxzq_gm")
        else:
            tdx_dir = r"D:\Install\zd_zxzq_gm"
    except Exception:
        tdx_dir = r"D:\Install\zd_zxzq_gm"
    
    if args.diagnose:
        if not args.date:
            print("❌ 诊断模式需要指定 --date")
            return
        config = {
            'start_date': datetime.strptime(args.date, '%Y-%m-%d'),
            'end_date': datetime.strptime(args.date, '%Y-%m-%d'),
            'tdx_dir': tdx_dir,
            'consolidation_days': args.consolidation_days,
            'consolidation_range': args.consolidation_range,
            'vol_ratio_threshold': args.vol_ratio,
        }
        generator = BreakoutGenerator(config)
        generator.diagnose(args.diagnose, args.date)
        return
    
    if args.date:
        start_date = end_date = args.date
    elif args.start_date and args.end_date:
        start_date = args.start_date
        end_date = args.end_date
    else:
        parser.print_help()
        return
    
    config = {
        'start_date': datetime.strptime(start_date, '%Y-%m-%d'),
        'end_date': datetime.strptime(end_date, '%Y-%m-%d'),
        'tdx_dir': tdx_dir,
        'consolidation_days': args.consolidation_days,
        'consolidation_range': args.consolidation_range,
        'vol_ratio_threshold': args.vol_ratio,
    }
    
    generator = BreakoutGenerator(config)
    generator.run()


if __name__ == "__main__":
    main()

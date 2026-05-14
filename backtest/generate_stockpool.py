# -*- coding: utf-8 -*-
"""
每日选股股票池生成器

功能：
1. 遍历回测期间的每个交易日
2. 对每只股票检查是否满足持续放量条件
3. 将选中的股票保存到 data/stockpool_YYYYMMDD.txt

使用方法:
    python backtest/generate_stockpool.py --start-date 2024-01-01 --end-date 2026-01-01
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Set
import pandas as pd
from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from local.utils import load_whitelist
from mootdx.reader import Reader


class StockPoolGenerator:
    """股票池生成器"""
    
    def __init__(self, config: dict):
        """
        初始化股票池生成器
        
        Args:
            config: 配置字典，包含：
                - start_date: 起始日期 (datetime)
                - end_date: 结束日期 (datetime)
                - volume_period: 连续放量天数 (int)
                - hold_days: 持仓天数（决定选股频率）(int)
                - whitelist_file: 白名单文件路径 (str)
                - tdx_dir: 通达信安装目录 (str)
                - min_price_change_pct: 最小涨跌幅 (float)
                - max_price_change_pct: 最大涨跌幅 (float)
                - min_volume_ratio: 最小量比 (float)
                - max_volume_ratio: 最大量比 (float)
        """
        self.config = config
        self.start_date = config['start_date']
        self.end_date = config['end_date']
        self.volume_period = config.get('volume_period', 3)
        self.hold_days = config.get('hold_days', 3)  # 持仓天数，默认3天
        self.whitelist_file = config.get('whitelist_file')
        self.tdx_dir = config.get('tdx_dir', r"D:\Install\zd_zxzq_gm")
        
        # 粗筛参数配置（从配置文件读取）
        self.min_price_change_pct = config.get('min_price_change_pct', -5.0)
        self.max_price_change_pct = config.get('max_price_change_pct', 25.0)
        self.min_volume_ratio = config.get('min_volume_ratio', 1.3)
        self.max_volume_ratio = config.get('max_volume_ratio', 8.0)
        
        # 数据缓存
        self.whitelist = set()
        self.data_dir = project_root / "data"
        self.data_cache = {}  # 内存缓存: {stock_code: DataFrame}
        
        # 初始化Reader
        self.reader = Reader.factory(market='std', tdxdir=self.tdx_dir)
        
        logger.info(f"[INIT] 股票池生成器初始化完成")
        logger.info(f"  - 回测周期: {self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}")
        logger.info(f"  - 放量周期: {self.volume_period} 天")
        logger.info(f"  - 持仓天数: {self.hold_days} 天")
        logger.info(f"  - 选股频率: 每隔 {self.hold_days} 个交易日选一次")
        logger.info(f"  - 涨跌幅区间: [{self.min_price_change_pct}%, {self.max_price_change_pct}%]")
        logger.info(f"  - 量比范围: [{self.min_volume_ratio}x, {self.max_volume_ratio}x]")
        logger.info(f"  - 输出目录: {self.data_dir}")
    
    def get_stock_data(self, stock_code: str) -> pd.DataFrame:
        """
        获取股票K线数据（带内存缓存）
        
        Args:
            stock_code: 股票代码（6位数字，不含市场前缀）
        
        Returns:
            DataFrame 或 None（如果数据为空或读取失败）
        """
        # 检查缓存
        if stock_code in self.data_cache:
            return self.data_cache[stock_code]
        
        # 首次读取，从磁盘加载
        try:
            df = self.reader.daily(symbol=stock_code)
            
            if df is None or df.empty:
                self.data_cache[stock_code] = None  # 标记为空数据
                return None
            
            # 数据处理：转换索引并排序
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # 存入缓存
            self.data_cache[stock_code] = df
            return df
            
        except Exception as e:
            logger.debug(f"[CACHE] 读取 {stock_code} 数据失败: {e}")
            self.data_cache[stock_code] = None  # 标记为失败
            return None
    
    def load_whitelist_stocks(self):
        """加载白名单股票（复用backtest_engine的逻辑）"""
        # 优先级1: 使用配置中指定的文件
        if self.whitelist_file and Path(self.whitelist_file).exists():
            try:
                with open(self.whitelist_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self.whitelist.add(line)
                logger.info(f"[LOAD] 从指定文件加载白名单: {self.whitelist_file}")
                logger.info(f"[INFO] 共加载 {len(self.whitelist)} 只股票")
                return
            except Exception as e:
                logger.warning(f"[WARN] 加载指定白名单文件失败: {e}，尝试自动查找...")
        
        # 优先级2: 自动查找data目录下的白名单文件
        if not self.data_dir.exists():
            raise ValueError(f"数据目录不存在: {self.data_dir}")
        
        # 尝试加载当天的白名单
        today_str = datetime.now().strftime('%Y%m%d')
        today_file = self.data_dir / f"whitelist_{today_str}.txt"
        
        if today_file.exists():
            try:
                with open(today_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            self.whitelist.add(line)
                logger.info(f"[LOAD] 自动加载当天白名单: {today_file.name}")
                logger.info(f"[INFO] 共加载 {len(self.whitelist)} 只股票")
                return
            except Exception as e:
                logger.warning(f"[WARN] 加载当天白名单失败: {e}，尝试查找最新文件...")
        
        # 优先级3: 查找data目录下最新的白名单文件
        logger.info("[SEARCH] 正在查找最新的白名单文件...")
        whitelist_files = list(self.data_dir.glob("whitelist_*.txt"))
        
        if not whitelist_files:
            raise ValueError(
                f"未找到任何白名单文件！\n"
                f"请在 data/ 目录下生成白名单文件，运行命令:\n"
                f"  python local/manage_stock_list.py --update"
            )
        
        # 按文件名排序，取最新的
        latest_file = sorted(whitelist_files)[-1]
        
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.whitelist.add(line)
            logger.info(f"[LOAD] 自动加载最新白名单: {latest_file.name}")
            logger.info(f"[INFO] 共加载 {len(self.whitelist)} 只股票")
            
            if latest_file.name != f"whitelist_{today_str}.txt":
                logger.info(f"[TIP] 注意：使用的是 {latest_file.name}，而非当天的白名单")
            
        except Exception as e:
            raise ValueError(f"加载白名单文件失败: {e}")
        
        if not self.whitelist:
            raise ValueError("白名单为空，请先生成白名单文件")
    
    def get_trading_days(self) -> List[datetime]:
        """
        获取回测期间的所有交易日（自动过滤周末和法定节假日）
        
        Returns:
            List[datetime]: 交易日列表
        """
        try:
            import akshare as ak
            
            logger.info("[INFO] 正在从 akshare 获取A股交易日历...")
            
            # 获取中国A股交易日历
            # 注意：akshare 的 stock_trade_date_hist_em 返回的是所有历史交易日
            trade_dates_df = ak.tool_trade_date_hist_sina()
            
            if trade_dates_df is None or trade_dates_df.empty:
                logger.warning("[WARN] 无法从 akshare 获取交易日历，降级为仅过滤周末")
                return self._get_trading_days_fallback()
            
            # 转换为 datetime 对象
            trade_dates = pd.to_datetime(trade_dates_df['trade_date']).tolist()
            
            # 筛选指定日期范围内的交易日
            trading_days = []
            for date in trade_dates:
                if self.start_date <= date <= self.end_date:
                    trading_days.append(date)
            
            # 按日期排序
            trading_days.sort()
            
            logger.info(f"[OK] 成功获取 {len(trading_days)} 个交易日（已自动过滤周末和法定节假日）")
            return trading_days
            
        except Exception as e:
            logger.warning(f"[WARN] 获取交易日历失败: {e}，降级为仅过滤周末")
            return self._get_trading_days_fallback()
    
    def _get_trading_days_fallback(self) -> List[datetime]:
        """
        降级方案：仅过滤周末（不处理法定节假日）
        
        Returns:
            List[datetime]: 工作日列表
        """
        trading_days = []
        current = self.start_date
        while current <= self.end_date:
            if current.weekday() < 5:  # 周一到周五
                trading_days.append(current)
            current += timedelta(days=1)
        
        logger.info(f"[FALLBACK] 使用降级方案，共 {len(trading_days)} 个工作日（未过滤节假日）")
        return trading_days
    
    def check_volume_condition(self, stock_code: str, check_date: datetime) -> bool:
        """
        检查股票在指定日期是否满足：放量 + 价格上涨 + 均线多头 + 位置合理
        
        Args:
            stock_code: 股票代码（不含市场前缀）
            check_date: 检查日期
        
        Returns:
            bool: 是否满足条件
        """
        try:
            # 使用缓存获取数据（首次读取会加载到缓存，后续直接返回）
            df = self.get_stock_data(stock_code)
            
            if df is None or df.empty:
                return False
            
            # 找到check_date之前的数据
            df_before = df[df.index <= check_date]
            
            # 需要更多数据用于均线计算 (至少20天用于MA20)
            if len(df_before) < self.volume_period + 20:
                return False
            
            # === 条件1：成交量连续递增（核心逻辑）===
            volumes = df_before['volume'].iloc[-self.volume_period-1:].values
            for i in range(1, self.volume_period + 1):
                if volumes[-i] <= volumes[-i-1]:
                    return False
            
            # === 条件2：价格整体呈上升趋势（优化：从"60%天数上涨"改为"整体上涨"）===
            closes = df_before['close'].iloc[-self.volume_period:].values
            opens = df_before['open'].iloc[-self.volume_period:].values
            
            # 最后一天收盘价 > 第一天开盘价，表示整体上涨
            if closes[-1] < opens[0]:
                return False
            
            # === 条件3：股价站上20日均线（保持不变）===
            ma20 = df_before['close'].rolling(20).mean().iloc[-1]
            latest_close = df_before['close'].iloc[-1]
            if latest_close < ma20:
                return False
            
            # === 条件4：近期涨幅适中，避免追高（使用配置化参数）===
            recent_return = (closes[-1] - closes[0]) / closes[0] * 100
            if recent_return > self.max_price_change_pct:
                return False
            if recent_return < self.min_price_change_pct:
                return False
            
            # === 条件5：成交量放大倍数合理（使用配置化参数）===
            vol_ma20 = df_before['volume'].rolling(20).mean().iloc[-1]
            latest_vol = df_before['volume'].iloc[-1]
            vol_ratio = latest_vol / vol_ma20 if vol_ma20 > 0 else 1
            
            if vol_ratio < self.min_volume_ratio:
                return False
            if vol_ratio > self.max_volume_ratio:
                return False
            
            return True
            
        except Exception as e:
            return False
    
    def save_stockpool(self, date: datetime, selected_stocks: Set[str]):
        """
        保存股票池到文件
        
        Args:
            date: 日期
            selected_stocks: 选中的股票代码集合
        """
        if not selected_stocks:
            logger.debug(f"[SKIP] {date.strftime('%Y-%m-%d')}: 无选中股票，跳过保存")
            return
        
        date_str = date.strftime('%Y%m%d')
        filename = f"stockpool_{date_str}.txt"
        filepath = self.data_dir / filename
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # 写入表头注释
                f.write(f"# 选股结果 - {date.strftime('%Y-%m-%d')}\n")
                f.write(f"# 格式: 股票代码\n")
                f.write(f"# 总数: {len(selected_stocks)} 只\n")
                f.write("-" * 30 + "\n")
                
                # 写入股票代码（排序）
                for code in sorted(selected_stocks):
                    f.write(f"{code}\n")
            
            logger.info(f"[SAVE] {date.strftime('%Y-%m-%d')}: 保存 {len(selected_stocks)} 只股票 -> {filename}")
            
        except Exception as e:
            logger.error(f"[ERROR] 保存股票池失败: {e}")
    
    def generate_daily_stockpools(self):
        """
        生成每日选股股票池
        
        选股策略：
        - 每个交易日都选股（不再间隔）
        - 后续回测时可根据需要选择如何使用股票池文件
        - 这样可以保留完整的每日选股数据
        """
        logger.info("=" * 80)
        logger.info("[START] 开始生成每日选股股票池")
        logger.info(f"[STRATEGY] 选股频率: 每个交易日都选股")
        logger.info("=" * 80)
        
        # 1. 加载白名单
        logger.info("\n[STEP 1] 加载白名单股票...")
        self.load_whitelist_stocks()
        
        # 2. 获取交易日列表
        logger.info("\n[STEP 2] 获取交易日列表...")
        trading_days = self.get_trading_days()
        
        # 3. 每个交易日都选股
        logger.info(f"\n[STEP 3] 开始选股（每个交易日都选）...\n")
        total_selected = 0
        selection_count = 0
        
        for idx, current_date in enumerate(trading_days):
            # 每个交易日都选股
            should_select = True
            
            if not should_select:
                logger.debug(f"[SKIP] {current_date.strftime('%Y-%m-%d')}: 非选股日，跳过")
                continue
            
            if (selection_count + 1) % 10 == 0:
                progress = (idx + 1) / len(trading_days) * 100
                logger.info(f"[PROGRESS] 进度: {idx + 1}/{len(trading_days)} ({progress:.1f}%) - 已选股 {selection_count + 1} 次")
            
            # 检查每只股票是否满足放量条件
            selected_stocks = set()
            for stock_code in self.whitelist:
                if self.check_volume_condition(stock_code, current_date):
                    selected_stocks.add(stock_code)
            
            # 保存股票池（不做数量限制，留给评分阶段处理）
            self.save_stockpool(current_date, selected_stocks)
            total_selected += len(selected_stocks)
            selection_count += 1
        
        logger.info(f"\n[DONE] 股票池生成完成")
        logger.info(f"  - 总交易日数: {len(trading_days)}")
        logger.info(f"  - 选股次数: {selection_count} 次")
        logger.info(f"  - 累计选中次数: {total_selected}")
        logger.info(f"  - 平均每次选中: {total_selected / selection_count if selection_count > 0 else 0:.1f} 只")
        logger.info(f"  - 输出目录: {self.data_dir}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="生成每日选股股票池",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
选股策略说明:
  - 每隔 hold_days 个交易日选股一次（默认3天）
  - 例如：周一选股 -> 周二买入 -> 周四卖出
  - 周四再次选股 -> 周五买入 -> 下周二卖出
  - 这样可以避免重复选股和资金分散

使用示例:
  python backtest/generate_stockpool.py --start-date 2024-01-01 --end-date 2026-01-01
  python backtest/generate_stockpool.py --hold-days 5  # 每5天选一次
        """
    )
    parser.add_argument('--start-date', type=str, default=None,
                       help='起始日期 (YYYY-MM-DD)，默认: 从配置文件读取')
    parser.add_argument('--end-date', type=str, default=None,
                       help='结束日期 (YYYY-MM-DD)，默认: 从配置文件读取')
    parser.add_argument('--volume-period', type=int, default=None,
                       help='连续放量天数，默认: 从配置文件读取')
    parser.add_argument('--hold-days', type=int, default=None,
                       help='持仓天数/选股频率（每隔N天选一次），默认: 从配置文件读取')
    parser.add_argument('--whitelist', type=str, default=None,
                       help='白名单文件路径')
    parser.add_argument('--tdx-dir', type=str, default=None,
                       help='通达信安装目录，默认: 从配置文件读取')
    
    args = parser.parse_args()
    
    # 从配置文件读取默认值
    try:
        import yaml
        config_file = project_root / "config.yaml"
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                backtest_config = yaml_config.get('backtest', {})
                
                # 配置文件中的默认值
                default_start_date = backtest_config.get('start_date', '2024-01-01')
                default_end_date = backtest_config.get('end_date', '2026-01-01')
                default_hold_days = backtest_config.get('hold_days', 3)
                default_volume_period = backtest_config.get('volume_period', 3)
                
                # 粗筛参数配置（新增）
                default_min_price_change = backtest_config.get('min_price_change_pct', -5.0)
                default_max_price_change = backtest_config.get('max_price_change_pct', 25.0)
                default_min_volume_ratio = backtest_config.get('min_volume_ratio', 1.3)
                default_max_volume_ratio = backtest_config.get('max_volume_ratio', 8.0)
                
                logger.info(f"[CONFIG] 从配置文件读取默认值:")
                logger.info(f"  - start_date: {default_start_date}")
                logger.info(f"  - end_date: {default_end_date}")
                logger.info(f"  - hold_days: {default_hold_days}")
                logger.info(f"  - volume_period: {default_volume_period}")
                logger.info(f"  - 涨跌幅区间: [{default_min_price_change}%, {default_max_price_change}%]")
                logger.info(f"  - 量比范围: [{default_min_volume_ratio}x, {default_max_volume_ratio}x]")
            
            tdx_dir_from_config = yaml_config.get('TDX_DIR', r"D:\Install\zd_zxzq_gm")
        else:
            logger.warning("[WARN] 配置文件不存在，使用硬编码默认值")
            default_start_date = '2024-01-01'
            default_end_date = '2026-01-01'
            default_hold_days = 3
            default_volume_period = 3
            default_min_price_change = -5.0
            default_max_price_change = 25.0
            default_min_volume_ratio = 1.3
            default_max_volume_ratio = 8.0
            tdx_dir_from_config = r"D:\Install\zd_zxzq_gm"
    except Exception as e:
        logger.warning(f"[WARN] 读取配置文件失败: {e}，使用硬编码默认值")
        default_start_date = '2024-01-01'
        default_end_date = '2026-01-01'
        default_hold_days = 3
        default_volume_period = 3
        default_min_price_change = -5.0
        default_max_price_change = 25.0
        default_min_volume_ratio = 1.3
        default_max_volume_ratio = 8.0
        tdx_dir_from_config = r"D:\Install\zd_zxzq_gm"
    
    # 构建配置（命令行参数优先，否则使用配置文件默认值）
    config = {
        'start_date': datetime.strptime(args.start_date if args.start_date else default_start_date, '%Y-%m-%d'),
        'end_date': datetime.strptime(args.end_date if args.end_date else default_end_date, '%Y-%m-%d'),
        'volume_period': args.volume_period if args.volume_period is not None else default_volume_period,
        'hold_days': args.hold_days if args.hold_days is not None else default_hold_days,
        'whitelist_file': args.whitelist,
        'tdx_dir': args.tdx_dir if args.tdx_dir else tdx_dir_from_config,
        # 粗筛参数配置
        'min_price_change_pct': default_min_price_change,
        'max_price_change_pct': default_max_price_change,
        'min_volume_ratio': default_min_volume_ratio,
        'max_volume_ratio': default_max_volume_ratio
    }
    
    generator = StockPoolGenerator(config)
    generator.generate_daily_stockpools()
    
    logger.info("\n" + "=" * 80)
    logger.info("[DONE] 股票池生成完成！")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
选股策略回测引擎

功能：
1. 对 select_daysvol.py 的持续放量选股策略进行历史回测
2. 模拟真实交易过程（次日开盘买入，3个交易日后收盘卖出）
3. 计算各项统计指标并与沪深300对比
4. 生成详细的回测报告

使用方法:
    python backtest/run_backtest.py --start-date 2024-01-01 --end-date 2026-01-01
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Set
import pandas as pd
import numpy as np
import yaml
from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from local.utils import load_whitelist, get_stock_name
from mootdx.reader import Reader


class TradeRecord:
    """交易记录"""
    def __init__(self, stock_code: str, stock_name: str, 
                 buy_date: datetime, buy_price: float,
                 sell_date: datetime, sell_price: float,
                 return_pct: float, hold_days: int):
        self.stock_code = stock_code
        self.stock_name = stock_name
        self.buy_date = buy_date
        self.buy_price = buy_price
        self.sell_date = sell_date
        self.sell_price = sell_price
        self.return_pct = return_pct
        self.hold_days = hold_days
    
    def to_dict(self) -> dict:
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'buy_date': self.buy_date.strftime('%Y-%m-%d'),
            'buy_price': self.buy_price,
            'sell_date': self.sell_date.strftime('%Y-%m-%d'),
            'sell_price': self.sell_price,
            'return_pct': self.return_pct,
            'hold_days': self.hold_days
        }


class TradingCycle:
    """交易周期（严格隔离）"""
    def __init__(self, cycle_index: int, select_date: datetime):
        self.cycle_index = cycle_index
        self.select_date = select_date  # 选股日
        self.buy_date = None            # 买入日
        self.sell_date = None           # 卖出日
        self.stocks: List[TradeRecord] = []
        self.initial_capital = 0.0
        self.final_capital = 0.0
        self.return_pct = 0.0


def load_config():
    """加载配置文件"""
    config_path = project_root / 'config.yaml'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.warning(f"⚠️  加载配置文件失败: {e}，使用默认配置")
        return {}


class BacktestEngine:
    """回测引擎"""
    
    def __init__(self, config: dict):
        """
        初始化回测引擎
        
        Args:
            config: 配置字典，包含以下键：
                - start_date: 回测起始日期 (datetime)
                - end_date: 回测结束日期 (datetime)
                - volume_period: 连续放量天数 (int)
                - hold_days: 持仓天数 (int)
                - whitelist_file: 白名单文件路径 (str)
                - tdx_dir: 通达信安装目录 (str)
                - min_score: 最小评分阈值 (float)
        """
        self.config = config
        self.start_date = config['start_date']
        self.end_date = config['end_date']
        self.volume_period = config.get('volume_period', 5)
        self.hold_days = config.get('hold_days', 3)
        self.whitelist_file = config.get('whitelist_file')
        self.tdx_dir = config.get('tdx_dir', r"D:\Install\zd_zxzq_gm")
        self.min_score = config.get('min_score', 0.5)  # 最小评分阈值
        
        # 数据缓存
        self.whitelist = set()
        self.trades: List[TradeRecord] = []
        self.trading_cycles: List[TradingCycle] = []  # 交易周期列表
        
        # 从 config.yaml 读取初始资金（与 calc_backtest_rate.py 保持一致）
        yaml_config = load_config()
        backtest_config = yaml_config.get('backtest', {})
        self.initial_capital = config.get('initial_capital', backtest_config.get('initial_capital', 1000000.0))
        
        # 数据目录
        self.data_dir = project_root / "data"
        
        # 初始化Reader
        self.reader = Reader.factory(market='std', tdxdir=self.tdx_dir)
        
        logger.info(f"[INIT] 回测引擎初始化完成")
        logger.info(f"  - 回测周期: {self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}")
        logger.info(f"  - 放量周期: {self.volume_period} 天")
        logger.info(f"  - 持仓天数: {self.hold_days} 天")
        logger.info(f"  - 初始资金: {self.initial_capital:,.2f} 元")
        logger.info(f"  - 最小评分: {self.min_score}")
    
    def load_whitelist_stocks(self):
        """
        加载白名单股票
        
        加载优先级：
        1. 如果配置了whitelist_file且存在，直接使用该文件
        2. 否则尝试加载当天的白名单文件 data/whitelist_YYYYMMDD.txt
        3. 如果当天文件不存在，查找data目录下最新的白名单文件
        4. 如果都找不到，抛出异常提示用户生成白名单
        """
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
        data_dir = project_root / "data"
        
        if not data_dir.exists():
            raise ValueError(f"数据目录不存在: {data_dir}，请先生成白名单文件")
        
        # 尝试加载当天的白名单
        today_str = datetime.now().strftime('%Y%m%d')
        today_file = data_dir / f"whitelist_{today_str}.txt"
        
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
        whitelist_files = list(data_dir.glob("whitelist_*.txt"))
        
        if not whitelist_files:
            raise ValueError(
                f"未找到任何白名单文件！\n"
                f"请在 data/ 目录下生成白名单文件，运行命令:\n"
                f"  python local/manage_stock_list.py --update"
            )
        
        # 按文件名排序（日期格式保证字典序即时间序），取最新的
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
        
        # 最终检查
        if not self.whitelist:
            raise ValueError(
                f"白名单为空！\n"
                f"请确保白名单文件包含有效的股票代码，运行命令:\n"
                f"  python local/manage_stock_list.py --update"
            )
    
    def load_daily_stockpool(self, date: datetime) -> Dict[str, float]:
        """
        加载指定日期的股票池（含评分）
        
        Args:
            date: 日期
        
        Returns:
            Dict[str, float]: {股票代码: 评分} 字典
        """
        date_str = date.strftime('%Y%m%d')
        stockpool_file = self.data_dir / f"stockpool_{date_str}.txt"
        
        if not stockpool_file.exists():
            return {}
        
        try:
            stocks = {}
            with open(stockpool_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释和空行
                    if not line or line.startswith('#') or line.startswith('-'):
                        continue
                    
                    # 解析格式: 股票代码,评分
                    if ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            code = parts[0].strip()
                            try:
                                score = float(parts[1].strip())
                            except ValueError:
                                # 如果评分解析失败，视为0分
                                score = 0.0
                            stocks[code] = score
                        else:
                            # 只有代码没有评分，视为0分
                            stocks[line] = 0.0
                    else:
                        # 纯股票代码，没有评分，视为0分
                        stocks[line] = 0.0
            
            logger.debug(f"[LOAD] {date.strftime('%Y-%m-%d')}: 加载股票池 {len(stocks)} 只")
            return stocks
            
        except Exception as e:
            logger.error(f"[ERROR] 加载股票池失败: {e}")
            return {}
    
    def get_trading_days(self) -> List[datetime]:
        """
        获取回测期间的所有交易日
        
        Returns:
            List[datetime]: 交易日列表
        """
        # 简化实现：假设周一至周五为交易日（实际应使用交易日历）
        trading_days = []
        current = self.start_date
        while current <= self.end_date:
            if current.weekday() < 5:  # 周一到周五
                trading_days.append(current)
            current += timedelta(days=1)
        
        logger.info(f"[INFO] 回测期间共 {len(trading_days)} 个交易日")
        return trading_days
    
    def check_volume_condition(self, stock_code: str, check_date: datetime) -> bool:
        """
        检查股票在指定日期是否满足持续放量条件
        
        Args:
            stock_code: 股票代码（不含市场前缀）
            check_date: 检查日期
        
        Returns:
            bool: 是否满足条件
        """
        try:
            # 读取日线数据
            df = self.reader.daily(symbol=stock_code)
            
            if df is None or df.empty:
                return False
            
            # 确保索引是datetime类型
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # 找到check_date之前的数据
            df_before = df[df.index <= check_date]
            
            if len(df_before) < self.volume_period + 1:
                return False
            
            # 提取最近 volume_period+1 天的成交量
            volumes = df_before['volume'].iloc[-self.volume_period-1:].values
            
            # 检查是否连续 volume_period 天递增
            for i in range(1, self.volume_period + 1):
                if volumes[-i] <= volumes[-i-1]:
                    return False
            
            return True
            
        except Exception as e:
            # logger.debug(f"  [DEBUG] {stock_code} 检查失败: {e}")
            return False
    
    def get_next_day_open_price(self, stock_code: str, signal_date: datetime) -> Optional[float]:
        """
        获取信号日次日的开盘价
        
        Args:
            stock_code: 股票代码
            signal_date: 信号产生日期
        
        Returns:
            float: 开盘价，失败返回None
        """
        try:
            df = self.reader.daily(symbol=stock_code)
            if df is None or df.empty:
                return None
            
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # 找到signal_date之后的第一个交易日
            df_after = df[df.index > signal_date]
            if df_after.empty:
                return None
            
            next_day_data = df_after.iloc[0]
            return float(next_day_data['open'])
            
        except Exception as e:
            logger.debug(f"  [DEBUG] 获取 {stock_code} 次日开盘价失败: {e}")
            return None
    
    def get_sell_close_price(self, stock_code: str, buy_date: datetime, hold_days: int) -> Optional[Tuple[datetime, float]]:
        """
        获取持有N个交易日后的收盘价
        
        持仓天数计算规则：
        - hold_days = 3 表示：买入日(T)算第1天，T+1算第2天，T+2算第3天 → T+2收盘卖出
        - 即：卖出日期 = 买入日后的第 (hold_days - 1) 个交易日
        
        Args:
            stock_code: 股票代码
            buy_date: 买入日期
            hold_days: 持仓天数
        
        Returns:
            Tuple[datetime, float]: (卖出日期, 收盘价)，失败返回None
        """
        try:
            df = self.reader.daily(symbol=stock_code)
            if df is None or df.empty:
                return None
            
            df.index = pd.to_datetime(df.index)
            df = df.sort_index()
            
            # 找到buy_date之后的数据（不包含买入日当天）
            df_after = df[df.index > buy_date]
            
            # 需要至少 hold_days - 1 个交易日才能完成持仓
            # 例如：hold_days=3，需要在买入后找到2个交易日（T+1和T+2）
            required_days = hold_days - 1
            if len(df_after) < required_days:
                return None
            
            # 第 (hold_days - 1) 个交易日的收盘价即为卖出价
            # 例如：hold_days=3，取 iloc[1] 即 T+2
            sell_data = df_after.iloc[required_days - 1]
            sell_date = sell_data.name
            sell_price = float(sell_data['close'])
            
            return (sell_date, sell_price)
            
        except Exception as e:
            logger.debug(f"  [DEBUG] 获取 {stock_code} 卖出价格失败: {e}")
            return None
    
    def is_suspended(self, stock_code: str, check_date: datetime) -> bool:
        """
        检查股票在指定日期是否停牌
        
        Args:
            stock_code: 股票代码
            check_date: 检查日期
        
        Returns:
            bool: 是否停牌
        """
        try:
            df = self.reader.daily(symbol=stock_code)
            if df is None or df.empty:
                return True
            
            df.index = pd.to_datetime(df.index)
            
            # 检查check_date附近是否有数据
            date_range = pd.date_range(check_date - timedelta(days=5), check_date + timedelta(days=5))
            available_dates = df.index.intersection(date_range)
            
            if len(available_dates) == 0:
                return True
            
            return False
            
        except Exception:
            return True
    
    def _get_close_price_at_date(self, stock_code: str, target_date: datetime) -> Optional[float]:
        """
        获取指定日期的收盘价
        
        Args:
            stock_code: 股票代码
            target_date: 目标日期
        
        Returns:
            float: 收盘价，失败返回None
        """
        try:
            df = self.reader.daily(symbol=stock_code)
            if df is None or df.empty:
                return None
            
            df.index = pd.to_datetime(df.index)
            
            if target_date not in df.index:
                return None
            
            return float(df.loc[target_date]['close'])
        except Exception as e:
            logger.debug(f"[DEBUG] 获取 {stock_code} {target_date} 收盘价失败: {e}")
            return None
    
    def calculate_cycle_return(self, cycle: TradingCycle) -> float:
        """
        计算单个交易周期的收益率（完全对齐 calc_backtest_rate.py 的区间收益率逻辑）
        
        规则：
        1. 期初资金平均分配到每只股票
        2. 每只股票：股数 = (int(分配资金/开盘价) // 100) * 100
        3. 如果股数 < 100，跳过该股票
        4. 实际投入 = 股数 × 开盘价
        5. 期末市值 = 股数 × 收盘价
        6. 周期收益率 = (总期末市值 - 总实际投入) / 总实际投入 * 100%
        
        Args:
            cycle: 交易周期对象
        
        Returns:
            float: 周期收益率（百分比）
        """
        num_stocks = len(cycle.stocks)
        if num_stocks == 0:
            return 0.0
        
        capital_per_stock = cycle.initial_capital / num_stocks
        total_investment = 0.0
        total_final_value = 0.0
        
        for trade in cycle.stocks:
            # 计算股数（100的整数倍）
            raw_shares = int(capital_per_stock / trade.buy_price)
            actual_shares = (raw_shares // 100) * 100
            
            if actual_shares < 100:
                continue  # 跳过不足100股的股票
            
            investment = actual_shares * trade.buy_price
            final_value = actual_shares * trade.sell_price
            
            total_investment += investment
            total_final_value += final_value
        
        if total_investment == 0:
            return 0.0
        
        return (total_final_value - total_investment) / total_investment * 100
    
    def _calculate_cycle_final_capital(self, cycle: TradingCycle) -> float:
        """
        计算交易周期的期末资金
        
        规则：
        1. 统计有效股票数量（能买入至少100股的）
        2. 期初资金 / 有效股票数 = 每股分配资金
        3. 每只股票：实际投入 = 股数 × 买入价
        4. 每只股票：期末价值 = 实际投入 × (1 + 收益率)
        5. 周期期末资金 = 所有股票期末价值之和
        
        Args:
            cycle: 交易周期对象
        
        Returns:
            float: 周期期末资金
        """
        num_valid_stocks = len([t for t in cycle.stocks 
                               if int((cycle.initial_capital / len(cycle.stocks)) / t.buy_price) // 100 * 100 >= 100])
        
        if num_valid_stocks == 0:
            return cycle.initial_capital
        
        capital_per_stock = cycle.initial_capital / num_valid_stocks
        cycle_final_capital = 0.0
        
        for trade in cycle.stocks:
            raw_shares = int(capital_per_stock / trade.buy_price)
            actual_shares = (raw_shares // 100) * 100
            
            if actual_shares >= 100:
                investment = actual_shares * trade.buy_price
                final_value = investment * (1 + trade.return_pct / 100)
                cycle_final_capital += final_value
        
        return cycle_final_capital
    
    def get_benchmark_data(self) -> pd.DataFrame:
        """
        获取沪深300指数数据作为基准
        
        优先级：
        1. 本地CSV文件（data/hs300_eastmoney.csv）- 最完整的历史数据
        2. 腾讯财经API - 实时数据（最多320天）
        
        Returns:
            DataFrame: 包含日期和收盘价的DataFrame
        """
        # 尝试1: 从本地CSV文件读取
        try:
            df = self._load_hs300_from_csv()
            if not df.empty:
                logger.info("[OK] 从本地CSV文件加载沪深300数据成功")
                return df
        except Exception as e:
            logger.warning(f"[WARN] 从本地CSV文件加载失败: {e}")
        
        # 尝试2: 从腾讯财经API获取
        try:
            logger.info("[DATA] 正在从腾讯财经获取沪深300指数数据...")
            
            # 计算需要的天数
            days_span = (self.end_date - self.start_date).days
            
            if days_span <= 320:
                # 如果回测周期在320天内，一次性获取
                return self._fetch_hs300_from_tencent(days=320)
            else:
                # 如果超过320天，需要分段获取或尝试其他方法
                logger.warning(f"[WARN] 回测周期 {days_span} 天超过320天限制，尝试获取最近320天数据...")
                df = self._fetch_hs300_from_tencent(days=320)
                
                # 检查是否覆盖了回测周期
                if not df.empty and len(df) > 0:
                    actual_start = df.iloc[0]['date']
                    actual_end = df.iloc[-1]['date']
                    
                    if actual_start > self.start_date:
                        logger.warning(f"[WARN] 数据起始日期 {actual_start.strftime('%Y-%m-%d')} 晚于回测起始日期 {self.start_date.strftime('%Y-%m-%d')}")
                        logger.warning(f"[WARN] 建议缩短回测周期或使用其他数据源获取完整历史数据")
                
                return df
                
        except Exception as e:
            logger.error(f"[ERROR] 获取沪深300数据失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            # 返回空DataFrame
            return pd.DataFrame(columns=['date', 'close'])
    
    def _load_hs300_from_csv(self) -> pd.DataFrame:
        """
        从本地CSV文件加载沪深300数据
        
        Returns:
            DataFrame: 包含日期和收盘价的DataFrame
        """
        from pathlib import Path
        
        # 使用项目根目录的 data 文件夹
        project_root = Path(__file__).parent.parent
        csv_file = project_root / "data" / "hs300_eastmoney.csv"
        
        if not csv_file.exists():
            raise FileNotFoundError(f"CSV文件不存在: {csv_file}")
        
        logger.info(f"[DATA] 正在从本地CSV文件加载沪深300数据: {csv_file}")
        
        # 读取CSV文件
        df = pd.read_csv(csv_file, parse_dates=['date'])
        
        # 过滤回测周期内的数据
        df = df[(df['date'] >= self.start_date) & (df['date'] <= self.end_date)]
        
        if df.empty:
            raise ValueError(f"CSV文件中没有回测周期内的数据: {self.start_date} 至 {self.end_date}")
        
        # 只保留需要的列
        df = df[['date', 'close']].sort_values('date').reset_index(drop=True)
        
        logger.info(f"[OK] 从CSV文件加载成功，共 {len(df)} 个交易日")
        logger.info(f"     日期范围: {df.iloc[0]['date'].strftime('%Y-%m-%d')} 至 {df.iloc[-1]['date'].strftime('%Y-%m-%d')}")
        
        return df
    
    def _fetch_hs300_from_tencent(self, days: int = 320) -> pd.DataFrame:
        """
        从腾讯财经获取沪深300数据
        
        Args:
            days: 获取的天数，最大320
        
        Returns:
            DataFrame: 包含日期和收盘价的DataFrame
        """
        try:
            import requests
            
            # 沪深300代码: sh000300 (腾讯财经格式)
            # 注意：不带起止日期参数，让API返回最近N天数据
            url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                "param": f"sh000300,day,,,{days},qfq"
            }
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # 检查返回码
            if data.get('code') != 0:
                raise Exception(f"API返回错误: {data.get('msg', '未知错误')}")
            
            # 解析数据结构
            stock_data = data.get('data', {}).get('sh000300', {})
            
            if not isinstance(stock_data, dict):
                raise Exception("返回数据结构异常")
            
            # 尝试多种可能的字段名
            klines = None
            for key in ['qfqday', 'day']:
                if key in stock_data:
                    klines = stock_data[key]
                    logger.debug(f"[DEBUG] 使用K线字段: {key}")
                    break
            
            if not klines:
                raise Exception("无K线数据")
            
            # 解析K线数据
            # K线格式: [日期, 开盘, 收盘, 最高, 最低, 成交量]
            # 注意：收盘价在索引2的位置
            records = []
            for item in klines:
                if isinstance(item, list) and len(item) >= 3:
                    date_str = item[0]
                    close_price = float(item[2])  # 收盘价在第3列（索引2）
                    
                    trade_date = pd.to_datetime(date_str)
                    
                    # 过滤回测周期内的数据
                    if self.start_date <= trade_date <= self.end_date:
                        records.append({
                            'date': trade_date,
                            'close': close_price
                        })
            
            df = pd.DataFrame(records)
            
            if df.empty:
                logger.warning(f"[WARN] 过滤后无数据，回测周期: {self.start_date.strftime('%Y-%m-%d')} 至 {self.end_date.strftime('%Y-%m-%d')}")
                return pd.DataFrame(columns=['date', 'close'])
            
            df = df.sort_values('date').reset_index(drop=True)
            
            logger.info(f"[OK] 获取沪深300数据成功，共 {len(df)} 个交易日")
            logger.info(f"     日期范围: {df.iloc[0]['date'].strftime('%Y-%m-%d')} 至 {df.iloc[-1]['date'].strftime('%Y-%m-%d')}")
            
            return df
            
        except Exception as e:
            logger.error(f"[ERROR] 从腾讯财经获取沪深300数据失败: {e}")
            raise
    
    def run_backtest(self):
        """
        执行回测（严格交易周期模式）
        
        核心原则：
        1. 选股日 = 卖出日（同一天完成卖出和选股）
        2. 买入日 = 选股日 + 1个交易日
        3. 卖出日 = 买入日 + (hold_days - 1)个交易日
        4. 下一个周期的选股日 = 当前周期的卖出日
        5. 周期之间绝不重叠
        """
        logger.info("=" * 80)
        logger.info("[START] 开始执行回测")
        logger.info("[MODE] 严格交易周期模式")
        logger.info("=" * 80)
        
        # 1. 加载白名单
        logger.info("\n[STEP 1] 加载白名单股票...")
        self.load_whitelist_stocks()
        
        # 2. 获取交易日列表
        logger.info("\n[STEP 2] 获取交易日列表...")
        trading_days = self.get_trading_days()
        
        # 3. 严格按交易周期执行
        logger.info("\n[STEP 3] 开始按交易周期回测...")
        
        cycles = []  # 存储所有交易周期
        current_capital = self.initial_capital
        cycle_index = 1
        
        i = 0
        while i < len(trading_days):
            current_date = trading_days[i]
            
            # 3.1 选股：从股票池文件读取
            stock_scores = self.load_daily_stockpool(current_date)
            if not stock_scores:
                i += 1
                continue
            
            # 过滤评分低于阈值的股票
            selected_codes = [
                code for code, score in stock_scores.items() 
                if score >= self.min_score
            ]
            
            if not selected_codes:
                i += 1
                continue
            
            logger.info(f"[CYCLE {cycle_index}] {current_date.strftime('%Y-%m-%d')}: 选中 {len(selected_codes)} 只股票")
            
            # 创建新交易周期
            cycle = TradingCycle(cycle_index, current_date)
            cycle.initial_capital = current_capital
            
            # 3.2 次日买入
            buy_date_idx = i + 1
            if buy_date_idx >= len(trading_days):
                logger.warning(f"[CYCLE {cycle_index}] 买入日超出回测周期，跳过该周期")
                i += 1
                continue
            
            buy_date = trading_days[buy_date_idx]
            cycle.buy_date = buy_date
            
            # 为每只股票创建交易记录
            for code in selected_codes:
                # 获取买入价格
                buy_price = self.get_next_day_open_price(code, current_date)
                if buy_price is None:
                    logger.warning(f"  [SKIP] {code}: 买入日无数据，跳过")
                    continue
                
                # 计算卖出日期
                sell_date_idx = buy_date_idx + (self.hold_days - 1)
                if sell_date_idx >= len(trading_days):
                    logger.warning(f"  [SKIP] {code}: 卖出日超出回测周期，跳过")
                    continue
                
                sell_date = trading_days[sell_date_idx]
                
                # 获取卖出价格
                sell_price = self._get_close_price_at_date(code, sell_date)
                if sell_price is None:
                    logger.warning(f"  [SKIP] {code}: 卖出日无数据，跳过")
                    continue
                
                # 计算收益率
                return_pct = (sell_price - buy_price) / buy_price * 100
                
                # 创建交易记录
                trade = TradeRecord(
                    stock_code=code,
                    stock_name=get_stock_name(code),
                    buy_date=buy_date,
                    buy_price=buy_price,
                    sell_date=sell_date,
                    sell_price=sell_price,
                    return_pct=return_pct,
                    hold_days=self.hold_days
                )
                
                cycle.stocks.append(trade)
            
            if not cycle.stocks:
                logger.warning(f"[CYCLE {cycle_index}] 所有股票均被跳过，该周期无有效交易")
                i += 1
                continue
            
            # 设置卖出日期
            cycle.sell_date = cycle.stocks[0].sell_date
            
            # 3.3 计算周期收益率（对齐 calc_backtest_rate.py 的逻辑）
            cycle.return_pct = self.calculate_cycle_return(cycle)
            
            # 3.4 计算周期期末资金
            cycle_final_capital = self._calculate_cycle_final_capital(cycle)
            cycle.final_capital = cycle_final_capital
            current_capital = cycle_final_capital  # 复利到下一周期
            
            # 3.5 记录交易记录到总列表
            self.trades.extend(cycle.stocks)
            
            logger.info(
                f"[CYCLE {cycle_index}] 完成: {len(cycle.stocks)} 只股票, "
                f"收益率: {cycle.return_pct:+.2f}%, "
                f"期初资金: {cycle.initial_capital:,.2f}, "
                f"期末资金: {cycle_final_capital:,.2f}"
            )
            
            # 添加到周期列表
            cycles.append(cycle)
            cycle_index += 1
            
            # 跳到卖出日的下一个交易日（准备新周期）
            i = sell_date_idx + 1
        
        # 保存所有交易周期
        self.trading_cycles = cycles
        
        logger.info(f"\n[RESULT] 回测完成")
        logger.info(f"  - 总交易周期: {len(cycles)} 个")
        logger.info(f"  - 总交易次数: {len(self.trades)} 次")
        logger.info(f"  - 初始资金: {self.initial_capital:,.2f} 元")
        logger.info(f"  - 最终资金: {current_capital:,.2f} 元")
        if self.initial_capital > 0:
            total_return = (current_capital - self.initial_capital) / self.initial_capital * 100
            logger.info(f"  - 总收益率: {total_return:+.2f}%")
        
        # ========== 输出前几个周期的详细信息 ==========
        if cycles:
            logger.info("\n" + "="*80)
            logger.info("📊 【交易周期汇总】")
            logger.info("="*80)
            logger.info(f"{'周期':<6} {'选股日':<12} {'买入日':<12} {'卖出日':<12} {'股票数':<6} {'期初资金':<15} {'期末资金':<15} {'周期收益':<10}")
            logger.info("-"*80)
            
            for cycle in cycles[:5]:  # 只显示前5个
                logger.info(
                    f"{cycle.cycle_index:<6} "
                    f"{cycle.select_date.strftime('%Y-%m-%d'):<12} "
                    f"{cycle.buy_date.strftime('%Y-%m-%d'):<12} "
                    f"{cycle.sell_date.strftime('%Y-%m-%d'):<12} "
                    f"{len(cycle.stocks):<6} "
                    f"{cycle.initial_capital:<15,.2f} "
                    f"{cycle.final_capital:<15,.2f} "
                    f"{cycle.return_pct:<10.2f}%"
                )
            
            if len(cycles) > 5:
                logger.info(f"... 还有 {len(cycles) - 5} 个周期")
            
            logger.info("="*80 + "\n")
    
    # ========== 已废弃：该方法不再需要，交易周期逻辑已在 run_backtest 中实现 ==========
    # def _calculate_daily_portfolio_value(self, current_date: datetime, pending_trades: list = None) -> float:
    #     """
    #     计算当日组合总价值（基于交易周期概念）- 已废弃
    #     
    #     资金管理策略（交易周期模式）：
    #     1. 定义交易周期：选股日 → 次日买入 → 持有N天卖出
    #     2. 每个周期的期初资金 = 上一周期的期末资金
    #     3. 在周期内，将期初资金平均分配到所有选中的股票
    #     4. 买入限制：每只股票的买入股数必须是100的整数倍
    #     5. 持仓N天后卖出，得到该周期的期末资金
    #     6. 下一个周期以上一周期期末资金作为期初资金
    #     
    #     Args:
    #         current_date: 当前日期
    #         pending_trades: 待卖出交易列表（保留参数以兼容旧代码）
    #     
    #     Returns:
    #         float: 组合总价值
    #     """
    #     # 获取截至当前日期已完成的交易
    #     completed_trades = [trade for trade in self.trades if trade.sell_date <= current_date]
    #     
    #     if not completed_trades:
    #         return self.initial_capital
    #     
    #     # 按交易周期分组（同一买入日期的为同一周期）
    #     from collections import defaultdict
    #     cycle_groups = defaultdict(list)
    #     for trade in completed_trades:
    #         cycle_groups[trade.buy_date].append(trade)
    #     
    #     # 按期初资金顺序处理每个交易周期
    #     current_capital = self.initial_capital
    #     
    #     # 按时间顺序处理每个交易周期
    #     for buy_date in sorted(cycle_groups.keys()):
    #         cycle_trades = cycle_groups[buy_date]
    #         num_stocks = len(cycle_trades)
    #         
    #         if num_stocks == 0:
    #             continue
    #         
    #         # ========== 该交易周期的计算 ==========
    #         # 期初资金 = current_capital（上一周期期末资金）
    #         cycle_initial_capital = current_capital
    #         
    #         # 每只股票理论分配的资金
    #         capital_per_stock_theoretical = cycle_initial_capital / num_stocks
    #         
    #         # 计算该周期的期末资金
    #         cycle_final_capital = 0
    #         
    #         for trade in cycle_trades:
    #             buy_price = trade.buy_price
    #             
    #             # 步骤1: 计算理论可买股数
    #             theoretical_shares = int(capital_per_stock_theoretical / buy_price)
    #             
    #             # 步骤2: 向下取整到100的倍数（A股最小交易单位）
    #             actual_shares = (theoretical_shares // 100) * 100
    #             
    #             # 步骤3: 如果不足100股，则无法买入（实际投入为0）
    #             if actual_shares < 100:
    #                 actual_investment = 0
    #             else:
    #                 # 实际投入金额 = 实际股数 × 买入价格
    #                 actual_investment = actual_shares * buy_price
    #             
    #             # 步骤4: 每只股票的最终价值 = 实际投入 × (1 + 收益率)
    #             stock_final_value = actual_investment * (1 + trade.return_pct / 100)
    #             cycle_final_capital += stock_final_value
    #         
    #         # 该周期的期末资金 = 下一周期的期初资金
    #         current_capital = cycle_final_capital
    #     
    #     return current_capital
    
    def calculate_cycle_metrics(self) -> List[dict]:
        """
        计算每个交易周期的详细指标（已简化，直接使用 trading_cycles）
        
        Returns:
            List[dict]: 每个交易周期的指标列表
        """
        if not self.trading_cycles:
            return []
        
        cycle_metrics = []
        
        logger.info("\n" + "="*80)
        logger.info("📊 【交易周期明细】")
        logger.info("="*80)
        logger.info(f"{'周期':<6} {'选股日':<12} {'买入日':<12} {'卖出日':<12} {'股票数':<6} {'期初资金':<15} {'期末资金':<15} {'周期收益':<10}")
        logger.info("-"*80)
        
        for cycle in self.trading_cycles:
            # 记录周期指标
            cycle_info = {
                'cycle_index': cycle.cycle_index,
                'cycle_start_date': cycle.select_date,
                'cycle_end_date': cycle.sell_date,
                'num_stocks': len(cycle.stocks),
                'initial_capital': cycle.initial_capital,
                'final_capital': cycle.final_capital,
                'cycle_return': cycle.return_pct,
                'cumulative_return': (cycle.final_capital - self.initial_capital) / self.initial_capital * 100,
                'trades': [t.to_dict() for t in cycle.stocks]
            }
            
            cycle_metrics.append(cycle_info)
            
            # 输出周期汇总信息
            logger.info(
                f"{cycle.cycle_index:<6} "
                f"{cycle.select_date.strftime('%Y-%m-%d'):<12} "
                f"{cycle.buy_date.strftime('%Y-%m-%d'):<12} "
                f"{cycle.sell_date.strftime('%Y-%m-%d'):<12} "
                f"{len(cycle.stocks):<6} "
                f"{cycle.initial_capital:<15,.2f} "
                f"{cycle.final_capital:<15,.2f} "
                f"{cycle.return_pct:<10.2f}%"
            )
        
        logger.info("="*80)
        logger.info(f"✅ 共完成 {len(cycle_metrics)} 个交易周期")
        logger.info("="*80 + "\n")
        
        return cycle_metrics
    
    def calculate_metrics(self) -> dict:
        """
        计算统计指标（基于交易周期）
        
        Returns:
            dict: 包含所有统计指标的字典
        """
        if not self.trading_cycles:
            logger.warning("[WARN] 没有交易周期，无法计算指标")
            return {}
        
        metrics = {}
        
        # 从所有交易中提取收益率数组
        returns = np.array([trade.return_pct for trade in self.trades])
        
        # 1. 基础指标
        metrics['total_trades'] = len(self.trades)
        metrics['winning_trades'] = int(np.sum(returns > 0))
        metrics['losing_trades'] = int(np.sum(returns < 0))
        metrics['win_rate'] = metrics['winning_trades'] / metrics['total_trades'] * 100
        
        # 2. 总收益率（直接从最后一个周期的期末资金计算）
        final_capital = self.trading_cycles[-1].final_capital
        total_return = (final_capital - self.initial_capital) / self.initial_capital * 100
        
        metrics['total_return'] = total_return
        metrics['initial_capital'] = self.initial_capital
        metrics['final_capital'] = final_capital
        
        logger.info(f"[CALC] 总收益率计算:")
        logger.info(f"       期初资金: {self.initial_capital:,.2f} 元")
        logger.info(f"       期末资金: {final_capital:,.2f} 元")
        logger.info(f"       总收益率: {total_return:.2f}%")
        logger.info(f"       交易周期数: {len(self.trading_cycles)}")
        
        # 年化收益率
        days_span = (self.end_date - self.start_date).days
        years = days_span / 365.25
        if years > 0:
            cumulative_return = total_return / 100
            metrics['annualized_return'] = ((1 + cumulative_return) ** (1/years) - 1) * 100
        else:
            metrics['annualized_return'] = 0
        
        # 3. 进阶指标
        # 平均收益
        metrics['avg_return'] = np.mean(returns)
        
        # 最大单笔收益和亏损
        metrics['max_single_return'] = np.max(returns)
        metrics['min_single_return'] = np.min(returns)
        
        # 盈亏比
        avg_win = np.mean(returns[returns > 0]) if np.any(returns > 0) else 0
        avg_loss = abs(np.mean(returns[returns < 0])) if np.any(returns < 0) else 1
        metrics['profit_loss_ratio'] = avg_win / avg_loss if avg_loss > 0 else 0
        
        # 夏普比率（假设无风险利率为3%）
        risk_free_rate = 3.0
        excess_returns = returns - risk_free_rate / 252  # 日化无风险利率
        if len(excess_returns) > 1 and np.std(excess_returns) > 0:
            metrics['sharpe_ratio'] = np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)
        else:
            metrics['sharpe_ratio'] = 0
        
        # 4. 最大回撤（基于交易周期资金曲线）
        cycle_capitals = [self.initial_capital] + [c.final_capital for c in self.trading_cycles]
        
        if len(cycle_capitals) > 1:
            capital_array = np.array(cycle_capitals)
            
            # 计算累计收益率序列
            cumulative_values = capital_array / capital_array[0]
            
            # 计算回撤
            peak = np.maximum.accumulate(cumulative_values)
            drawdown = (cumulative_values - peak) / peak
            metrics['max_drawdown'] = np.min(drawdown) * 100
            
            logger.info(f"[CALC] 最大回撤计算: 基于{len(cycle_capitals)}个交易周期的资金曲线")
        else:
            metrics['max_drawdown'] = 0
            logger.warning("[WARN] 交易周期数据不足，无法计算最大回撤")
        
        # 5. 基准对比
        benchmark_df = self.get_benchmark_data()
        if not benchmark_df.empty:
            benchmark_start_price = benchmark_df.iloc[0]['close']
            benchmark_end_price = benchmark_df.iloc[-1]['close']
            benchmark_return = (benchmark_end_price - benchmark_start_price) / benchmark_start_price * 100
            
            metrics['benchmark_total_return'] = benchmark_return
            metrics['excess_return'] = metrics['total_return'] - benchmark_return
            
            # 基准年化收益
            if years > 0:
                metrics['benchmark_annualized_return'] = ((1 + benchmark_return/100) ** (1/years) - 1) * 100
            else:
                metrics['benchmark_annualized_return'] = 0
        else:
            metrics['benchmark_total_return'] = None
            metrics['excess_return'] = None
            metrics['benchmark_annualized_return'] = None
        
        return metrics
    
    def generate_report(self, output_dir: str = None):
        """
        生成回测报告
        
        Args:
            output_dir: 输出目录，默认为项目根目录下的data文件夹
        """
        from backtest.backtest_reporter import BacktestReporter
        
        if output_dir is None:
            output_dir = str(project_root / "data")
        
        # 先计算指标
        metrics = self.calculate_metrics()
        
        # 创建报告生成器，传入预计算的指标
        reporter = BacktestReporter(self.trades, self.config, output_dir, metrics)
        reporter.generate_full_report()


def main():
    """主函数"""
    import argparse
    import yaml
    
    parser = argparse.ArgumentParser(description="选股策略回测工具")
    parser.add_argument('--start-date', type=str, default='2024-01-01',
                       help='回测起始日期 (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default='2026-01-01',
                       help='回测结束日期 (YYYY-MM-DD)')
    parser.add_argument('--volume-period', type=int, default=5,
                       help='连续放量天数')
    parser.add_argument('--hold-days', type=int, default=3,
                       help='持仓天数')
    parser.add_argument('--whitelist', type=str, default=None,
                       help='白名单文件路径')
    parser.add_argument('--tdx-dir', type=str, default=r"D:\Install\zd_zxzq_gm",
                       help='通达信安装目录')
    parser.add_argument('--min-score', type=float, default=None,
                       help='最小评分阈值（覆盖配置文件）')
    
    args = parser.parse_args()
    
    # 从配置文件读取默认值
    config_path = project_root / "config.yaml"
    min_score = 0.5  # 默认值
    
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config and 'backtest' in yaml_config:
                    min_score = yaml_config['backtest'].get('backtest_minscore', 0.5)
        except Exception as e:
            logger.warning(f"[WARN] 读取配置文件失败: {e}，使用默认值 0.5")
    
    # 命令行参数优先于配置文件
    if args.min_score is not None:
        min_score = args.min_score
    
    # 构建配置
    config = {
        'start_date': datetime.strptime(args.start_date, '%Y-%m-%d'),
        'end_date': datetime.strptime(args.end_date, '%Y-%m-%d'),
        'volume_period': args.volume_period,
        'hold_days': args.hold_days,
        'whitelist_file': args.whitelist,
        'tdx_dir': args.tdx_dir,
        'min_score': min_score
    }
    
    # 创建并运行回测引擎
    engine = BacktestEngine(config)
    engine.run_backtest()
    
    # 计算指标
    metrics = engine.calculate_metrics()
    
    # 生成报告
    engine.generate_report()
    
    logger.info("\n" + "=" * 80)
    logger.info("[DONE] 回测完成！")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()

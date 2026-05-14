# -*- coding: utf-8 -*-
"""配置加载模块"""
import os
from pathlib import Path
from typing import List, Dict, Any
import yaml
from pydantic import BaseModel
from loguru import logger


class SymbolConfig(BaseModel):
    """股票配置"""
    code: str
    name: str
    enabled: bool = True
    # 可选的个性化策略参数（如果不设置则使用全局默认值）
    add_drop_threshold: float = None  # 加仓跌幅阈值
    take_profit_threshold: float = None  # 止盈涨幅阈值
    max_add_positions: int = None  # 最大加仓次数
    initial_position_pct: float = None  # 初始建仓比例
    
    # 可选的个性化价格监控参数（如果不设置则使用全局默认值）
    price_monitor_enabled: bool = None  # 是否启用价格监控
    sell_trigger_rise_pct: float = None  # 卖出监控触发涨幅阈值（%）
    sell_pullback_pct: float = None  # 卖出监控回落幅度阈值（%）
    buy_trigger_drop_pct: float = None  # 买入监控触发跌幅阈值（%）
    buy_rebound_pct: float = None  # 买入监控反弹幅度阈值（%）


class BrokerConfig(BaseModel):
    """券商配置"""
    type: str = "simulate"
    account: str = ""
    password: str = ""
    token: str = ""


class StrategyConfig(BaseModel):
    """策略配置"""
    initial_position_pct: float = 10
    max_add_positions: int = 4
    add_position_multiplier: float = 2
    add_drop_threshold: float = 8
    take_profit_threshold: float = 6
    max_position_pct: float = 80


class RiskControlConfig(BaseModel):
    """风控配置"""
    daily_loss_limit: float = 5
    single_loss_limit: float = 10
    total_loss_limit: float = 20


class MarketFilterConfig(BaseModel):
    """大盘过滤配置"""
    enabled: bool = True
    sh_index_min: int = 2800
    sh_index_max: int = 4500


class TrendFilterConfig(BaseModel):
    """趋势过滤配置"""
    enabled: bool = True
    ema_periods: List[int] = [20, 60]
    require_uptrend: bool = True


class VolumeFilterConfig(BaseModel):
    """量价过滤配置"""
    enabled: bool = True
    volume_ma5_multiplier: float = 1.2


class CapitalFilterConfig(BaseModel):
    """资金流向过滤配置"""
    enabled: bool = True
    require_positive_capital: bool = True


class TimeFilterConfig(BaseModel):
    """时间窗口过滤配置"""
    enabled: bool = True
    avoid_hours: List[int] = [9, 10, 14]


class FiltersConfig(BaseModel):
    """过滤器配置"""
    market_filter: MarketFilterConfig = MarketFilterConfig()
    trend_filter: TrendFilterConfig = TrendFilterConfig()
    volume_filter: VolumeFilterConfig = VolumeFilterConfig()
    capital_filter: CapitalFilterConfig = CapitalFilterConfig()
    time_filter: TimeFilterConfig = TimeFilterConfig()


class DataSourceConfig(BaseModel):
    """数据源配置"""
    akshare: Dict[str, Any] = {"enabled": True}
    tushare: Dict[str, Any] = {"enabled": False, "token": ""}


class APIConfig(BaseModel):
    """API 配置"""
    host: str = "0.0.0.0"
    port: int = 8080


class DatabaseConfig(BaseModel):
    """数据库配置"""
    type: str = "sqlite"
    path: str = "data/trading.db"


class TradingSessionConfig(BaseModel):
    """单个交易时段配置"""
    start_time: str = "09:30"  # 开始时间
    end_time: str = "11:30"    # 结束时间


class TradingHoursConfig(BaseModel):
    """交易时间配置"""
    trading_days: List[int] = [1, 2, 3, 4, 5]  # 周一到周五
    sessions: List[TradingSessionConfig] = [   # 交易时间段列表
        TradingSessionConfig(start_time="09:30", end_time="11:30"),  # 上午
        TradingSessionConfig(start_time="13:00", end_time="15:00")   # 下午
    ]


class StockPoolItem(BaseModel):
    """股票池单项配置"""
    code: str  # 股票代码（格式：sh.600000 或 sz.000001）
    name: str  # 股票名称
    index: str = ""  # 中文序号（一、二、三...）


class NewsSourceConfig(BaseModel):
    """资讯来源配置"""
    enabled: bool = True  # 是否启用
    url_template: str = ""  # URL模板


class NewsSourcesConfig(BaseModel):
    """资讯来源总配置"""
    individual_news: NewsSourceConfig = NewsSourceConfig(
        enabled=True,
        url_template="https://so.eastmoney.com/news/s?keyword={symbol}"
    )
    financial_reports: NewsSourceConfig = NewsSourceConfig(
        enabled=True,
        url_template="https://data.eastmoney.com/notices/stock/{symbol}.html"
    )


class ScheduleConfig(BaseModel):
    """定时任务调度配置"""
    hour: int = 21  # 执行小时（24小时制）
    minute: int = 0  # 执行分钟
    second: int = 0  # 执行秒数


class StockNewsMonitorConfig(BaseModel):
    """股票资讯监控配置"""
    enabled: bool = True  # 是否启用资讯监控
    stock_pool: List[StockPoolItem] = []  # 股票池
    news_sources: NewsSourcesConfig = NewsSourcesConfig()  # 资讯来源
    schedule: ScheduleConfig = ScheduleConfig()  # 定时任务配置


class BuyOrderSchedulerConfig(BaseModel):
    """买入委托定时任务配置"""
    enabled: bool = True  # 是否启用买入委托定时任务
    hour: int = 9  # 执行小时（24小时制）
    minute: int = 26  # 执行分钟
    min_score: float = 1.0  # 最低综合评分阈值


class FeishuNotificationConfig(BaseModel):
    """飞书通知配置"""
    enabled: bool = False  # 是否启用飞书通知
    webhook_url: str = ""  # 飞书机器人 Webhook URL
    notify_signals: List[str] = ["BUY", "SELL", "ADD", "STOP"]  # 需要通知的信号类型


class NotificationConfig(BaseModel):
    """通知配置"""
    feishu: FeishuNotificationConfig = FeishuNotificationConfig()


class SellMonitorConfig(BaseModel):
    """卖出监控配置"""
    trigger_rise_pct: float = 3.0      # 触发监控的上涨幅度阈值（%）
    pullback_pct: float = 0.5          # 从最高点回落幅度阈值（%）


class BuyMonitorConfig(BaseModel):
    """买入监控配置"""
    trigger_drop_pct: float = 3.5      # 触发监控的下跌幅度阈值（%）
    rebound_pct: float = 0.5           # 从最低点反弹幅度阈值（%）


class PriceMonitorConfig(BaseModel):
    """价格极值追踪监控配置"""
    enabled: bool = True  # 是否启用价格监控
    sell_monitor: SellMonitorConfig = SellMonitorConfig()  # 卖出监控参数
    buy_monitor: BuyMonitorConfig = BuyMonitorConfig()  # 买入监控参数


class SchedulerConfig(BaseModel):
    """定时任务配置"""
    signal_check_interval: int = 5  # 信号检查间隔（分钟）- 兼容旧配置
    trading_check_interval: float = 1.0  # 交易时间检查间隔（分钟），支持小数
    non_trading_check_interval: float = 10.0  # 非交易时间检查间隔（分钟），支持小数
    run_immediately_on_start: bool = True  # 启动时立即执行
    enabled: bool = True  # 是否启用定时任务
    trading_hours: TradingHoursConfig = TradingHoursConfig()  # 交易时间配置
    price_monitor: PriceMonitorConfig = PriceMonitorConfig()  # 价格监控配置


class AppConfig(BaseModel):
    """应用配置"""
    symbols: List[SymbolConfig]
    initial_capital: float = 500000
    strategy: StrategyConfig = StrategyConfig()
    risk_control: RiskControlConfig = RiskControlConfig()
    filters: FiltersConfig = FiltersConfig()
    data_source: DataSourceConfig = DataSourceConfig()
    api: APIConfig = APIConfig()
    scheduler: SchedulerConfig = SchedulerConfig()
    notification: NotificationConfig = NotificationConfig()
    stock_news_monitor: StockNewsMonitorConfig = StockNewsMonitorConfig()
    buy_order_scheduler: BuyOrderSchedulerConfig = BuyOrderSchedulerConfig()
    database: DatabaseConfig = DatabaseConfig()


_config: AppConfig = None


def load_config(config_path: str = None) -> AppConfig:
    """加载配置文件"""
    global _config
    
    if _config is not None:
        return _config
    
    if config_path is None:
        # 默认查找当前目录或上级目录的config.yaml
        possible_paths = [
            "config.yaml",
            "../config.yaml",
            Path(__file__).parent.parent / "config.yaml"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                config_path = path
                break
    
    if config_path is None or not os.path.exists(config_path):
        logger.warning("未找到配置文件，使用默认配置")
        _config = AppConfig(
            symbols=[
                SymbolConfig(code="600938", name="中国海油", enabled=True),
                SymbolConfig(code="000792", name="盐湖股份", enabled=True)
            ]
        )
        return _config
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = yaml.safe_load(f)
    
    _config = AppConfig(**config_dict)
    logger.info(f"配置文件加载成功: {config_path}")
    return _config


def get_config() -> AppConfig:
    """获取配置单例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config

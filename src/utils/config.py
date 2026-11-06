# -*- coding: utf-8 -*-
"""配置加载模块"""
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
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


class EtfSelectionConfig(BaseModel):
    """从候选 ETF 池中选 N 只的规则（2026-11-05 新增；2026-11-06 加过热降权）

    排序（三层）：① 距 drawdown_window_days 日高点回撤 ≤ 该只 deep_drop_thresholds 值、
                     或收盘价 ≤ 该只 deep_drop_prices 值（跌透）者排最前
                  ② 近 5 日涨幅 ≥ overheat_mom5_threshold 的「过热」标的排到跌透组之后
                  ③ 其余按近 momentum_lookback_days 日涨幅降序
    仓位：仍均分，不按信号加权
    """
    enabled: bool = True  # 关闭则直接买候选池前 count 只（等同旧的固定列表行为）
    count: int = 6  # 每次买入几只
    momentum_lookback_days: int = 3  # 动量回看窗口（近 N 日涨幅）
    drawdown_window_days: int = 250  # 回撤基准窗口（距 N 日高点）
    # 每只各自的"跌透"阈值（距 N 日高点回撤，单位 %，负值）
    # 未列出的标的不参与回撤型跌透判定（只按涨幅排序）
    deep_drop_thresholds: Dict[str, float] = {
        "515650": -20.0,   # 消费50
        "516310": -15.0,   # 银行
        "518880": -30.0,   # 黄金
        "513850": -15.0,   # 美国50
        "561360": -25.0,   # 石油ETF国泰
    }
    # 每只的"价格跌透"阈值（绝对收盘价，跌破即优先买）
    # 与 deep_drop_thresholds 是**并列关系**：任一条件满足即视为跌透
    deep_drop_prices: Dict[str, float] = {
        "588080": 1.200,   # 科创50
        "513050": 0.950,   # 中概互联
        "513120": 1.000,   # 港股创新药
    }
    # 过热降权阈值（%）：近 5 日涨幅 ≥ 此值时，买入优先级降到最后（不排除，仅排序靠后）
    # None 或 ≤0 = 关闭该规则
    #
    # 数据依据（2026-11-06，8 只 ETF / 2024-01~2026-11 / 5376 行 / 84 个交易日模拟）：
    #   · 近5日涨幅≥8% 时未来2日收益：全期 -0.415pp、前半 -0.511pp、后半 -0.285pp（三段同向）
    #   · 留一检验：去掉任一标的后差值仍为负（-0.169 ~ -0.769pp）⇒ 稳健
    #   · 选基模拟：现行 +0.168%/t=1.23 → 加降权 +0.231%/t=1.74，
    #              剔top3 +0.056%→+0.121%，胜率 57%→61%
    #   ⚠️ 配对 t=+1.65 未达 2.0 采纳线 ⇒ 标为「待观察规则」，需月度复核
    #   ⚠️ 为何不用 6%：6% 表面配对 t=+2.47 更高，但个股层面不成立
    #      （前半反向 -0.015pp、留一检验去掉 3 只后转负）⇒ 属过拟合
    #   ⚠️ 为何不用逐只阈值/豁免名单：配对 t 分别仅 +0.86 / +1.32，均劣于统一 8%
    overheat_mom5_threshold: Optional[float] = 8.0


class BuyOrderSchedulerConfig(BaseModel):
    """买入委托定时任务配置"""
    enabled: bool = True  # 是否启用买入委托定时任务
    hour: int = 9  # 执行小时（24小时制）
    minute: int = 26  # 执行分钟
    min_score: float = 1.0  # 最低综合评分阈值
    # 大盘评分<阈值时买入的 ETF **候选池**（2026-11-05 起为 8 只，每次按 etf_selection 规则选 6 只）
    # 2026-11-02 起：516130 消费龙头因受限买不了 → 515650 消费50ETF富国
    # 2026-11-05 起：162411 华宝油气波动过大 → 561360 石油ETF国泰；并把 588080/513050 加回候选池
    defensive_etfs: List[str] = ["513120", "515650", "516310", "518880", "513850", "561360", "513050", "588080"]  # 须与 config.yaml 保持一致
    # 从候选池选 N 只的规则（2026-11-05 新增）
    etf_selection: EtfSelectionConfig = EtfSelectionConfig()
    # 进攻股票列表（评分≥阈值时从中随机选 offensive_random_count 个）
    offensive_stks: List[str] = ["600206", "600397", "002056", "002156", "002636",
                                 "002674", "003043", "300649", "688141"]
    # 进攻模式从 offensive_stks 随机抽取的数量
    offensive_random_count: int = 7
    # 评分≥阈值时选股方式：0=读股票池文件（默认），1=按offensive_stks生成
    use_offensive_stocks: int = 0


class FeishuNotificationConfig(BaseModel):
    """飞书通知配置"""
    enabled: bool = False  # 是否启用飞书通知
    webhook_url: str = ""  # 飞书机器人 Webhook URL
    # 自建应用凭证（仅「发送图片」需要）：webhook 无法携带图片，图片须先经应用上传换取 img_key。
    # 留空 = 跳过图片、只发文字卡片；也可用环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET 覆盖。
    app_id: str = ""
    app_secret: str = ""
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

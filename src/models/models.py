# -*- coding: utf-8 -*-
"""数据模型"""
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class SignalType(str, Enum):
    """信号类型"""
    BUY = "BUY"       # 买入
    ADD = "ADD"       # 加仓
    SELL = "SELL"     # 卖出
    STOP = "STOP"     # 止损
    WAIT = "WAIT"     # 观望


class PositionStatus(str, Enum):
    """持仓状态"""
    NONE = "NONE"           # 无持仓
    INIT = "INIT"           # 初始建仓
    ADDING = "ADDING"       # 加仓中
    FULL = "FULL"           # 满仓
    CLOSED = "CLOSED"       # 已平仓


class Signal(BaseModel):
    """交易信号"""
    symbol: str
    name: str
    signal_type: SignalType
    price: float  # 实时报价
    change_pct: float = 0.0  # 实时涨跌幅 (%)
    reason: str
    timestamp: datetime = datetime.now()
    position_count: int = 0      # 当前持仓次数 (0=未建仓，1=初始建仓，2=一次加仓...)
    avg_cost: float = 0           # 平均成本
    position_value: float = 0    # 持仓市值
    target_shares: int = 0       # 目标股数
    next_add_price: Optional[float] = None  # 下次加仓价格
    next_sell_price: Optional[float] = None  # 下次止盈价格
    
    # BOLL布林带三轨完整价差信息（百分比）
    boll_up_diff_pct: Optional[float] = None      # 价格与BOLL上轨的价差百分比
    boll_middle_diff_pct: Optional[float] = None  # 价格与BOLL中轨的价差百分比
    boll_down_diff_pct: Optional[float] = None    # 价格与BOLL下轨的价差百分比
    
    # RSI指标
    rsi: Optional[float] = None  # RSI值


class Position(BaseModel):
    """持仓信息"""
    symbol: str
    name: str
    status: PositionStatus
    init_price: float           # 初始建仓价格
    avg_cost: float             # 平均成本
    total_shares: int           # 总股数
    position_value: float       # 持仓市值
    add_count: int              # 加仓次数
    open_date: datetime         # 建仓日期
    last_update: datetime       # 最后更新


class MarketData(BaseModel):
    """市场数据"""
    symbol: str
    name: str
    current_price: float
    open_price: float
    high_price: float
    low_price: float
    volume: float
    amount: float
    change_pct: float
    timestamp: datetime
    
    # 指标数据
    ema_20: Optional[float] = None
    ema_60: Optional[float] = None
    ma_5: Optional[float] = None
    volume_ma5: Optional[float] = None
    rsi: Optional[float] = None
    capital_flow: Optional[float] = None
    
    # BOLL布林带指标
    boll_up: Optional[float] = None      # BOLL上轨
    boll_middle: Optional[float] = None  # BOLL中轨
    boll_down: Optional[float] = None    # BOLL下轨


class OrderRecord(BaseModel):
    """订单记录"""
    id: int
    symbol: str
    name: str
    signal_type: SignalType
    price: float
    shares: int
    amount: float
    timestamp: datetime
    status: str = "PENDING"


# 数据库模型
class DBPosition(Base):
    """持仓数据库模型"""
    __tablename__ = "positions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    name = Column(String(50))
    status = Column(String(20), default=PositionStatus.NONE.value)
    init_price = Column(Float, default=0)
    avg_cost = Column(Float, default=0)
    total_shares = Column(Integer, default=0)
    position_value = Column(Float, default=0)
    add_count = Column(Integer, default=0)
    open_date = Column(DateTime)
    last_update = Column(DateTime, default=datetime.now)


class DBSignal(Base):
    """信号记录数据库模型"""
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    name = Column(String(50))
    signal_type = Column(String(20), nullable=False)
    price = Column(Float)
    reason = Column(Text)
    timestamp = Column(DateTime, default=datetime.now)
    position_count = Column(Integer, default=0)
    avg_cost = Column(Float, default=0)


class DBOrder(Base):
    """订单记录数据库模型"""
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False)
    name = Column(String(50))
    signal_type = Column(String(20), nullable=False)
    price = Column(Float)
    shares = Column(Integer)
    amount = Column(Float)
    timestamp = Column(DateTime, default=datetime.now)
    status = Column(String(20), default="PENDING")


def get_engine(db_path: str = "data/trading.db"):
    """获取数据库引擎"""
    return create_engine(f"sqlite:///{db_path}")


def init_db(db_path: str = "data/trading.db"):
    """初始化数据库"""
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)
    return engine


def get_session(db_path: str = "data/trading.db"):
    """获取数据库会话"""
    engine = get_engine(db_path)
    Session = sessionmaker(bind=engine)
    return Session()
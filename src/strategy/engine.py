# -*- coding: utf-8 -*-
"""马丁格尔策略引擎 - T+0 ETF优化版"""
from datetime import datetime
from typing import Optional, List, Dict
from loguru import logger

from src.models.models import (
    Signal, SignalType, Position, PositionStatus, MarketData
)
from src.utils.config import get_config, StrategyConfig
from src.market.data_provider import get_market_data, get_sh_index, get_capital_flow


class MartingaleEngine:
    """马丁格尔策略引擎（T+0 ETF优化版）"""
    
    def __init__(self):
        self.config = get_config()
        self.global_strategy_config = self.config.strategy
        self.filters_config = self.config.filters
        self.risk_config = self.config.risk_control
        
        # 持仓状态字典 {symbol: Position}
        self.positions: Dict[str, Position] = {}
        
        # 初始化持仓状态
        for symbol_cfg in self.config.symbols:
            if symbol_cfg.enabled:
                self.positions[symbol_cfg.code] = Position(
                    symbol=symbol_cfg.code,
                    name=symbol_cfg.name,
                    status=PositionStatus.NONE,
                    init_price=0,
                    avg_cost=0,
                    total_shares=0,
                    position_value=0,
                    add_count=0,
                    open_date=datetime.now(),
                    last_update=datetime.now()
                )
    
    def _get_symbol_strategy_config(self, symbol: str) -> StrategyConfig:
        """获取指定标的的策略配置（优先使用个性化配置，否则使用全局默认值）"""
        # 查找该symbol的配置
        symbol_cfg = None
        for cfg in self.config.symbols:
            if cfg.code == symbol:
                symbol_cfg = cfg
                break
        
        if not symbol_cfg:
            # 如果找不到配置，返回全局默认配置
            return self.global_strategy_config
        
        # 创建一个新的StrategyConfig，使用个性化参数或全局默认值
        return StrategyConfig(
            initial_position_pct=symbol_cfg.initial_position_pct if symbol_cfg.initial_position_pct is not None else self.global_strategy_config.initial_position_pct,
            max_add_positions=symbol_cfg.max_add_positions if symbol_cfg.max_add_positions is not None else self.global_strategy_config.max_add_positions,
            add_position_multiplier=self.global_strategy_config.add_position_multiplier,  # 这个保持全局统一
            add_drop_threshold=symbol_cfg.add_drop_threshold if symbol_cfg.add_drop_threshold is not None else self.global_strategy_config.add_drop_threshold,
            take_profit_threshold=symbol_cfg.take_profit_threshold if symbol_cfg.take_profit_threshold is not None else self.global_strategy_config.take_profit_threshold,
            max_position_pct=self.global_strategy_config.max_position_pct  # 这个保持全局统一
        )

    def analyze(self, symbol: str) -> Signal:
        """分析ETF并生成信号"""
        
        # 获取该symbol的策略配置（支持个性化配置）
        strategy_config = self._get_symbol_strategy_config(symbol)
        
        # 获取市场数据（确保使用最新实时数据）
        market_data = get_market_data(symbol)
        if not market_data:
            return Signal(
                symbol=symbol,
                name=symbol,
                signal_type=SignalType.WAIT,
                price=0,
                change_pct=0.0,
                reason="获取市场数据失败"
            )
        
        # 获取持仓状态
        position = self.positions.get(symbol)
        if not position:
            position = Position(
                symbol=symbol,
                name=market_data.name,
                status=PositionStatus.NONE,
                init_price=0,
                avg_cost=0,
                total_shares=0,
                position_value=0,
                add_count=0,
                open_date=datetime.now(),
                last_update=datetime.now()
            )
            self.positions[symbol] = position
        
        # 应用过滤器
        filter_result = self._apply_filters(market_data)
        if not filter_result["passed"]:
            position.status = PositionStatus.NONE
            return Signal(
                symbol=symbol,
                name=market_data.name,
                signal_type=SignalType.WAIT,
                price=market_data.current_price,
                change_pct=market_data.change_pct,
                reason=filter_result["reason"],
                position_count=position.add_count,
                avg_cost=position.avg_cost,
                position_value=position.position_value,
                rsi=market_data.rsi
            )
        
        # 根据持仓状态生成信号（传入个性化策略配置）
        return self._generate_signal(position, market_data, strategy_config)
    
    def get_all_signals(self) -> List[Signal]:
        """获取所有配置ETF的交易信号"""
        signals = []
        
        for symbol_cfg in self.config.symbols:
            if symbol_cfg.enabled:
                signal = self.analyze(symbol_cfg.code)
                signals.append(signal)
            else:
                signals.append(Signal(
                    symbol=symbol_cfg.code,
                    name=symbol_cfg.name,
                    signal_type=SignalType.WAIT,
                    price=0,
                    change_pct=0.0,
                    reason="标的未启用"
                ))
        
        return signals
    
    def get_all_positions(self) -> List[Position]:
        """获取所有持仓信息"""
        return list(self.positions.values())
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取指定标的的持仓信息"""
        return self.positions.get(symbol)
    
    def reset_position(self, symbol: str):
        """重置指定标的的持仓状态"""
        if symbol in self.positions:
            pos = self.positions[symbol]
            pos.status = PositionStatus.NONE
            pos.init_price = 0
            pos.avg_cost = 0
            pos.total_shares = 0
            pos.position_value = 0
            pos.add_count = 0
            pos.last_update = datetime.now()
            logger.info(f"已重置 {symbol} 的持仓状态")
    
    def _apply_filters(self, market_data: MarketData) -> Dict:
        """应用过滤条件"""
        # 这里可以添加各种过滤逻辑
        # 暂时简化，直接通过
        return {"passed": True, "reason": ""}
    
    def _generate_signal(self, position: Position, market_data: MarketData, strategy_config: StrategyConfig = None) -> Signal:
        """生成交易信号"""
        # 如果没有传入策略配置，使用全局默认配置（向后兼容）
        if strategy_config is None:
            strategy_config = self.global_strategy_config
            
        current_price = market_data.current_price
        
        # 无持仓 - 初始建仓
        if position.status == PositionStatus.NONE:
            # 检查是否满足建仓条件
            if self._check_buy_conditions(position, market_data):
                return self._create_buy_signal(position, market_data, strategy_config)
            else:
                # 计算首次建仓后的目标价格
                first_add_price = current_price * (1 - strategy_config.add_drop_threshold / 100)
                sell_price = current_price * (1 + strategy_config.take_profit_threshold / 100)
                
                return Signal(
                    symbol=position.symbol,
                    name=market_data.name,
                    signal_type=SignalType.WAIT,
                    price=current_price,
                    change_pct=market_data.change_pct,
                    reason="等待建仓时机",
                    position_count=position.add_count,
                    avg_cost=position.avg_cost,
                    position_value=position.position_value,
                    next_add_price=first_add_price,
                    next_sell_price=sell_price,
                    rsi=market_data.rsi
                )
        
        # 有持仓 - 检查是否需要加仓或止盈
        elif position.status in [PositionStatus.INIT, PositionStatus.ADDING]:
            return self._check_add_or_sell(position, market_data, strategy_config)
        
        # 满仓 - 只检查止盈
        elif position.status == PositionStatus.FULL:
            return self._check_profit_taking(position, market_data, strategy_config)
        
        # 已平仓 - 重新建仓
        elif position.status == PositionStatus.CLOSED:
            if self._check_buy_conditions(position, market_data):
                # 重置持仓状态
                position.status = PositionStatus.NONE
                position.add_count = 0
                return self._create_buy_signal(position, market_data, strategy_config)
            else:
                # 计算首次建仓价格（假设当前价格为基准）
                first_add_price = current_price * (1 - strategy_config.add_drop_threshold / 100)
                sell_price = current_price * (1 + strategy_config.take_profit_threshold / 100)
                
                return Signal(
                    symbol=position.symbol,
                    name=market_data.name,
                    signal_type=SignalType.WAIT,
                    price=current_price,
                    change_pct=market_data.change_pct,
                    reason="等待重新建仓时机",
                    position_count=0,
                    avg_cost=0,
                    position_value=0,
                    next_add_price=first_add_price,
                    next_sell_price=sell_price,
                    rsi=market_data.rsi
                )
    
    def _check_buy_conditions(self, position: Position, market_data: MarketData) -> bool:
        """检查是否满足买入条件（T+0优化）"""
        # T+0可以更加灵活，主要关注价格位置和RSI
        
        # 检查RSI是否处于低位（超卖反弹机会）
        if market_data.rsi:
            if market_data.rsi < 40:  # T+0可以放宽到40
                return True
        
        # 检查价格是否在支撑位
        if market_data.low_price and market_data.current_price:
            price_range = market_data.high_price - market_data.low_price
            if price_range > 0:
                position_ratio = (market_data.current_price - market_data.low_price) / price_range
                if position_ratio < 0.4:  # T+0可以放宽到40%
                    return True
        
        # 如果涨跌幅较大，可能是好的入场点
        if abs(market_data.change_pct) > 2:
            return True
        
        # 默认允许建仓（T+0更灵活）
        return True
    
    def _check_add_or_sell(self, position: Position, market_data: MarketData, strategy_config: StrategyConfig = None) -> Signal:
        """检查加仓或止盈（T+0优化）"""
        # 如果没有传入策略配置，使用全局默认配置
        if strategy_config is None:
            strategy_config = self.global_strategy_config
            
        current_price = market_data.current_price
        avg_cost = position.avg_cost
        init_price = position.init_price
        
        # 计算当前跌幅（基于初始建仓价格，确保加仓间隔一致）
        drop_pct = (init_price - current_price) / init_price * 100 if init_price > 0 else 0
        profit_pct = (current_price - avg_cost) / avg_cost * 100
        
        # 1. 检查是否触发止盈（T+0可以快速止盈）
        if current_price >= avg_cost * (1 + strategy_config.take_profit_threshold / 100):
            return self._create_sell_signal(position, market_data, f"止盈卖出（盈利{profit_pct:.2f}%）")
        
        # 2. 检查是否触发加仓
        if position.add_count < strategy_config.max_add_positions:
            # 每次加仓需要的跌幅阈值（累计，基于初始价格）
            # add_count=0时，第一次加仓需要跌3.5%；add_count=1时，第二次加仓需要跌7.0%
            required_drop = strategy_config.add_drop_threshold * (position.add_count + 1)
            
            if drop_pct >= required_drop:
                return self._create_add_signal(position, market_data, drop_pct, strategy_config)
        
        # 3. 检查是否触发止损（基于初始价格的最大亏损）
        max_loss = strategy_config.add_drop_threshold * (strategy_config.max_add_positions + 1)
        if drop_pct >= max_loss:
            return self._create_stop_signal(position, market_data, f"触发最大亏损（亏损{drop_pct:.2f}%），止损")
        
        # 继续持有 - 计算下一次目标价格
        next_add_price = None
        next_sell_price = None
        
        # 计算下一次加仓价格（基于初始建仓价格，而非平均成本）
        if position.add_count < strategy_config.max_add_positions:
            next_required_drop = strategy_config.add_drop_threshold * (position.add_count + 1)
            next_add_price = position.init_price * (1 - next_required_drop / 100)
        
        # 计算止盈价格（基于平均成本）
        next_sell_price = avg_cost * (1 + strategy_config.take_profit_threshold / 100)
        
        # 继续持有
        return Signal(
            symbol=position.symbol,
            name=market_data.name,
            signal_type=SignalType.WAIT,
            price=current_price,
            change_pct=market_data.change_pct,
            reason=f"持有中，当前{'下跌' if drop_pct > 0 else '上涨'}{abs(drop_pct):.2f}%",
            position_count=position.add_count,
            avg_cost=position.avg_cost,
            position_value=position.total_shares * current_price,
            next_add_price=next_add_price,
            next_sell_price=next_sell_price,
            rsi=market_data.rsi
        )
    
    def _check_profit_taking(self, position: Position, market_data: MarketData, strategy_config: StrategyConfig = None) -> Signal:
        """检查止盈（T+0优化）"""
        # 如果没有传入策略配置，使用全局默认配置
        if strategy_config is None:
            strategy_config = self.global_strategy_config
            
        current_price = market_data.current_price
        avg_cost = position.avg_cost
        init_price = position.init_price
        
        # 检查止盈
        if current_price >= avg_cost * (1 + strategy_config.take_profit_threshold / 100):
            profit_pct = (current_price - avg_cost) / avg_cost * 100
            return self._create_sell_signal(position, market_data, f"达到止盈目标（盈利{profit_pct:.2f}%）")
        
        # 检查是否需要止损（基于初始价格）
        drop_pct = (init_price - current_price) / init_price * 100 if init_price > 0 else 0
        max_loss = strategy_config.add_drop_threshold * (strategy_config.max_add_positions + 1)
        if drop_pct >= max_loss:
            return self._create_stop_signal(position, market_data, f"触发最大亏损（亏损{drop_pct:.2f}%），止损")
        
        # 继续持有 - 计算目标价格
        next_sell_price = avg_cost * (1 + strategy_config.take_profit_threshold / 100)
        
        # 继续持有
        return Signal(
            symbol=position.symbol,
            name=market_data.name,
            signal_type=SignalType.WAIT,
            price=current_price,
            change_pct=market_data.change_pct,
            reason=f"满仓持有，等待止盈",
            position_count=position.add_count,
            avg_cost=position.avg_cost,
            position_value=position.position_value,
            next_sell_price=next_sell_price,
            rsi=market_data.rsi
        )
    
    def _create_buy_signal(self, position: Position, market_data: MarketData, strategy_config: StrategyConfig = None) -> Signal:
        """创建买入信号"""
        # 如果没有传入策略配置，使用全局默认配置
        if strategy_config is None:
            strategy_config = self.global_strategy_config
            
        price = market_data.current_price
        
        # 计算买入金额（初始仓位的百分比）
        init_amount = self.config.initial_capital * (strategy_config.initial_position_pct / 100)
        
        # 计算份额（按100份整数倍，ETF以份为单位）
        shares = int(init_amount / price / 100) * 100
        
        if shares < 100:
            shares = 100  # 最少100份
        
        position.status = PositionStatus.INIT
        position.init_price = price
        position.avg_cost = price
        position.total_shares = shares
        position.position_value = shares * price
        position.add_count = 0  # 初始建仓，尚未加仓
        position.last_update = datetime.now()
        
        # 计算下次加仓价（基于初始建仓价格）
        next_required_drop = strategy_config.add_drop_threshold * (position.add_count + 1)
        next_add_price = price * (1 - next_required_drop / 100)
        
        # 计算止盈卖出价（基于平均成本）
        next_sell_price = price * (1 + strategy_config.take_profit_threshold / 100)
        
        # 计算价格与BOLL三轨的价差百分比（统一公式：(价格 - 轨道价) / 价格 * 100%）
        boll_up_diff_pct = None
        boll_middle_diff_pct = None
        boll_down_diff_pct = None
        
        if price > 0:
            # 与上轨的价差：(价格 - 上轨) / 价格 * 100%
            if market_data.boll_up and market_data.boll_up > 0:
                boll_up_diff_pct = ((price - market_data.boll_up) / price) * 100
            
            # 与中轨的价差：(价格 - 中轨) / 价格 * 100%
            if market_data.boll_middle and market_data.boll_middle > 0:
                boll_middle_diff_pct = ((price - market_data.boll_middle) / price) * 100
            
            # 与下轨的价差：(价格 - 下轨) / 价格 * 100%
            if market_data.boll_down and market_data.boll_down > 0:
                boll_down_diff_pct = ((price - market_data.boll_down) / price) * 100
        
        return Signal(
            symbol=position.symbol,
            name=market_data.name,
            signal_type=SignalType.BUY,
            price=price,
            change_pct=market_data.change_pct,
            reason=f"初始建仓：买入{shares}份，成本{price:.3f}元/份",
            position_count=position.add_count,
            avg_cost=position.avg_cost,
            position_value=position.position_value,
            target_shares=shares,
            next_add_price=next_add_price,
            next_sell_price=next_sell_price,
            boll_up_diff_pct=boll_up_diff_pct,
            boll_middle_diff_pct=boll_middle_diff_pct,
            boll_down_diff_pct=boll_down_diff_pct,
            rsi=market_data.rsi
        )
    
    def _create_add_signal(self, position: Position, market_data: MarketData, drop_pct: float, strategy_config: StrategyConfig = None) -> Signal:
        """创建加仓信号"""
        # 如果没有传入策略配置，使用全局默认配置
        if strategy_config is None:
            strategy_config = self.global_strategy_config
            
        price = market_data.current_price
        
        # 计算加仓金额（按倍数递增）
        base_amount = self.config.initial_capital * (strategy_config.initial_position_pct / 100)
        add_amount = base_amount * (strategy_config.add_position_multiplier ** position.add_count)
        
        # 计算份额
        shares = int(add_amount / price / 100) * 100
        
        if shares < 100:
            shares = 100  # 最少100份
        
        # 更新持仓
        old_shares = position.total_shares
        old_cost = position.avg_cost * old_shares
        
        new_shares = old_shares + shares
        new_cost = old_cost + (shares * price)
        
        position.avg_cost = new_cost / new_shares
        position.total_shares = new_shares
        position.position_value = new_shares * price
        position.add_count += 1
        
        # 判断是否已达到最大加仓次数
        if position.add_count >= strategy_config.max_add_positions:
            position.status = PositionStatus.FULL
        else:
            position.status = PositionStatus.ADDING
        
        position.last_update = datetime.now()
        
        # 计算下次加仓价（基于初始建仓价格）
        next_add_price = None
        next_sell_price = None
        
        if position.add_count < strategy_config.max_add_positions:
            next_required_drop = strategy_config.add_drop_threshold * (position.add_count + 1)
            next_add_price = position.init_price * (1 - next_required_drop / 100)
        
        # 计算止盈卖出价（基于平均成本）
        next_sell_price = position.avg_cost * (1 + strategy_config.take_profit_threshold / 100)

    def _create_sell_signal(self, position: Position, market_data: MarketData, reason: str) -> Signal:
        """创建卖出信号"""
        price = market_data.current_price
        
        # 计算收益（正确公式：当前市值 - 总成本）
        # 注意：必须使用当前卖出价格计算市值，而不是position_value（可能是旧值）
        current_market_value = position.total_shares * price
        total_cost = position.total_shares * position.avg_cost
        profit = current_market_value - total_cost
        profit_pct = (profit / total_cost) * 100 if total_cost > 0 else 0
        
        # 重置持仓状态
        position.status = PositionStatus.CLOSED
        position.init_price = 0
        position.avg_cost = 0
        position.total_shares = 0
        position.position_value = 0
        position.add_count = 0
        position.last_update = datetime.now()
        
        # 计算价格与BOLL三轨的价差百分比（统一公式：(价格 - 轨道价) / 价格 * 100%）
        boll_up_diff_pct = None
        boll_middle_diff_pct = None
        boll_down_diff_pct = None
        
        if price > 0:
            # 与上轨的价差：(价格 - 上轨) / 价格 * 100%
            if market_data.boll_up and market_data.boll_up > 0:
                boll_up_diff_pct = ((price - market_data.boll_up) / price) * 100
            
            # 与中轨的价差：(价格 - 中轨) / 价格 * 100%
            if market_data.boll_middle and market_data.boll_middle > 0:
                boll_middle_diff_pct = ((price - market_data.boll_middle) / price) * 100
            
            # 与下轨的价差：(价格 - 下轨) / 价格 * 100%
            if market_data.boll_down and market_data.boll_down > 0:
                boll_down_diff_pct = ((price - market_data.boll_down) / price) * 100
        
        return Signal(
            symbol=position.symbol,
            name=market_data.name,
            signal_type=SignalType.SELL,
            price=price,
            change_pct=market_data.change_pct,
            reason=f"{reason}，总收益{profit:.2f}元 ({profit_pct:+.2f}%)",
            position_count=position.add_count,
            avg_cost=position.avg_cost,
            position_value=current_market_value,  # 使用当前市值
            boll_up_diff_pct=boll_up_diff_pct,
            boll_middle_diff_pct=boll_middle_diff_pct,
            boll_down_diff_pct=boll_down_diff_pct,
            rsi=market_data.rsi
        )
    
    def _create_stop_signal(self, position: Position, market_data: MarketData, reason: str) -> Signal:
        """创建止损信号"""
        price = market_data.current_price
        
        # 计算损失（正确公式：总成本 - 当前市值）
        # 注意：必须使用当前卖出价格计算市值，而不是position_value（可能是旧值）
        current_market_value = position.total_shares * price
        total_cost = position.total_shares * position.avg_cost
        loss = total_cost - current_market_value
        loss_pct = (loss / total_cost) * 100 if total_cost > 0 else 0
        
        # 重置持仓状态
        position.status = PositionStatus.CLOSED
        position.init_price = 0
        position.avg_cost = 0
        position.total_shares = 0
        position.position_value = 0
        position.add_count = 0
        position.last_update = datetime.now()
        
        # 计算价格与BOLL三轨的价差百分比（统一公式：(价格 - 轨道价) / 价格 * 100%）
        boll_up_diff_pct = None
        boll_middle_diff_pct = None
        boll_down_diff_pct = None
        
        if price > 0:
            # 与上轨的价差：(价格 - 上轨) / 价格 * 100%
            if market_data.boll_up and market_data.boll_up > 0:
                boll_up_diff_pct = ((price - market_data.boll_up) / price) * 100
            
            # 与中轨的价差：(价格 - 中轨) / 价格 * 100%
            if market_data.boll_middle and market_data.boll_middle > 0:
                boll_middle_diff_pct = ((price - market_data.boll_middle) / price) * 100
            
            # 与下轨的价差：(价格 - 下轨) / 价格 * 100%
            if market_data.boll_down and market_data.boll_down > 0:
                boll_down_diff_pct = ((price - market_data.boll_down) / price) * 100
        
        return Signal(
            symbol=position.symbol,
            name=market_data.name,
            signal_type=SignalType.STOP,
            price=price,
            change_pct=market_data.change_pct,
            reason=f"{reason}，总损失{loss:.2f}元 ({loss_pct:+.2f}%)",
            position_count=position.add_count,
            avg_cost=position.avg_cost,
            position_value=current_market_value,  # 使用当前市值
            boll_up_diff_pct=boll_up_diff_pct,
            boll_middle_diff_pct=boll_middle_diff_pct,
            boll_down_diff_pct=boll_down_diff_pct,
            rsi=market_data.rsi
        )


# 全局策略引擎实例
_engine = None


def get_strategy_engine() -> MartingaleEngine:
    """获取策略引擎单例"""
    global _engine
    if _engine is None:
        _engine = MartingaleEngine()
    return _engine

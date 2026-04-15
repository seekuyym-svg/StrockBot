# -*- coding: utf-8 -*-
"""主程序入口 - ETF链接基金T+0马丁格尔量化交易系统"""
import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from loguru import logger

from src.utils.config import load_config, get_config
from src.strategy.engine import get_strategy_engine
from src.market.data_provider import get_market_data, get_sh_index
from src.models.models import SignalType
from src.utils.signal_storage import save_signal_to_file, save_all_signals_to_file
from src.utils.scheduler import start_signal_scheduler, stop_signal_scheduler

# 配置日志
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)

# 加载配置
config = load_config()

# 创建FastAPI应用
app = FastAPI(
    title="ETF链接基金T+0马丁格尔量化交易系统",
    description="基于马丁格尔算法的ETF T+0交易信号生成系统",
    version="2.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== API路由 ==============

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "ETF链接基金T+0马丁格尔量化交易系统",
        "version": "2.0.0",
        "status": "running",
        "description": "支持sh.513120(港股创新药ETF)和sh.513050(中概互联网ETF)的T+0交易"
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/signals")
async def get_all_signals():
    """获取所有ETF信号"""
    engine = get_strategy_engine()
    signals = engine.get_all_signals()
    
    # 转换为字典列表
    signals_data = [signal.model_dump() for signal in signals]
    
    # 持久化保存所有信号数据
    try:
        saved_path = save_all_signals_to_file(signals_data)
        if saved_path:
            logger.info(f"信号数据已持久化: {saved_path}")
    except Exception as e:
        logger.error(f"信号数据持久化失败: {e}")
    
    return {
        "code": 0,
        "message": "success",
        "data": signals_data,
        "storage": {
            "saved": True if saved_path else False,
            "path": saved_path
        }
    }


@app.get("/api/signal/{symbol}")
async def get_signal(symbol: str):
    """获取指定ETF信号"""
    engine = get_strategy_engine()
    signal = engine.analyze(symbol)
    
    # 转换为字典
    signal_data = signal.model_dump()
    
    # 持久化保存单个信号数据
    try:
        saved_path = save_signal_to_file(symbol, signal_data)
        if saved_path:
            logger.info(f"信号数据已持久化 [{symbol}]: {saved_path}")
    except Exception as e:
        logger.error(f"信号数据持久化失败 [{symbol}]: {e}")
    
    return {
        "code": 0,
        "message": "success",
        "data": signal_data,
        "storage": {
            "saved": True if saved_path else False,
            "path": saved_path
        }
    }


@app.get("/api/positions")
async def get_positions():
    """获取所有持仓"""
    engine = get_strategy_engine()
    positions = engine.get_all_positions()
    
    return {
        "code": 0,
        "message": "success",
        "data": [p.model_dump() for p in positions]
    }


@app.get("/api/position/{symbol}")
async def get_position(symbol: str):
    """获取指定ETF持仓"""
    engine = get_strategy_engine()
    position = engine.get_position(symbol)
    
    if not position:
        raise HTTPException(status_code=404, detail="Position not found")
    
    return {
        "code": 0,
        "message": "success",
        "data": position.model_dump()
    }


@app.post("/api/position/{symbol}/reset")
async def reset_position(symbol: str):
    """重置持仓状态"""
    engine = get_strategy_engine()
    engine.reset_position(symbol)
    
    return {
        "code": 0,
        "message": f"Position {symbol} has been reset"
    }


@app.get("/api/market/{symbol}")
async def get_market(symbol: str):
    """获取市场数据"""
    market_data = get_market_data(symbol)
    
    if not market_data:
        raise HTTPException(status_code=404, detail="Market data not found")
    
    return {
        "code": 0,
        "message": "success",
        "data": market_data.model_dump()
    }


@app.get("/api/market/index/sh")
async def get_sh_index_data():
    """获取上证指数"""
    index = get_sh_index()
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "index": index,
            "timestamp": datetime.now().isoformat()
        }
    }


@app.get("/api/config")
async def get_config_info():
    """获取配置信息"""
    config = get_config()
    
    # 隐藏敏感信息
    return {
        "code": 0,
        "message": "success",
        "data": {
            "symbols": [s.model_dump() for s in config.symbols],
            "initial_capital": config.initial_capital,
            "strategy": config.strategy.model_dump(),
            "filters": config.filters.model_dump()
        }
    }


@app.get("/api/signals/history")
async def get_signal_history(days: int = 7):
    """获取历史信号记录"""
    from src.utils.signal_storage import get_signal_storage
    
    storage = get_signal_storage()
    files = storage.get_signal_history(days)
    
    history = []
    for filepath in files:
        try:
            data = storage.load_signal_file(filepath)
            history.append({
                "file": str(filepath),
                "filename": filepath.name,
                "date": filepath.parent.name,
                "data": data
            })
        except Exception as e:
            logger.warning(f"加载历史信号文件失败 {filepath}: {e}")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "count": len(history),
            "days": days,
            "records": history
        }
    }


@app.get("/api/signals/today")
async def get_today_signals():
    """获取今天的信号记录"""
    from src.utils.signal_storage import get_signal_storage
    
    storage = get_signal_storage()
    files = storage.get_today_signals()
    
    today_data = []
    for filepath in files:
        try:
            data = storage.load_signal_file(filepath)
            today_data.append({
                "file": str(filepath),
                "filename": filepath.name,
                "data": data
            })
        except Exception as e:
            logger.warning(f"加载今日信号文件失败 {filepath}: {e}")
    
    return {
        "code": 0,
        "message": "success",
        "data": {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "count": len(today_data),
            "records": today_data
        }
    }

# ============== 主程序 ==============

def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("ETF链接基金T+0马丁格尔量化交易系统启动")
    logger.info("=" * 60)
    
    # 显示配置
    config = get_config()
    enabled_symbols = [s for s in config.symbols if s.enabled]
    logger.info(f"交易标的: {[f'{s.name}({s.code})' for s in enabled_symbols]}")
    logger.info(f"初始资金: {config.initial_capital}元")
    logger.info(f"\n全局默认策略配置:")
    logger.info(f"  加仓次数: {config.strategy.max_add_positions}")
    logger.info(f"  加仓倍数: {config.strategy.add_position_multiplier}")
    logger.info(f"  加仓阈值: {config.strategy.add_drop_threshold}%")
    logger.info(f"  止盈阈值: {config.strategy.take_profit_threshold}%")
    
    # 显示每个ETF的个性化配置
    logger.info(f"\n各ETF个性化配置:")
    for symbol_cfg in enabled_symbols:
        add_drop = symbol_cfg.add_drop_threshold if symbol_cfg.add_drop_threshold is not None else config.strategy.add_drop_threshold
        take_profit = symbol_cfg.take_profit_threshold if symbol_cfg.take_profit_threshold is not None else config.strategy.take_profit_threshold
        max_add = symbol_cfg.max_add_positions if symbol_cfg.max_add_positions is not None else config.strategy.max_add_positions
        init_pct = symbol_cfg.initial_position_pct if symbol_cfg.initial_position_pct is not None else config.strategy.initial_position_pct
        
        personalized = "✓" if (symbol_cfg.add_drop_threshold is not None or symbol_cfg.take_profit_threshold is not None) else "○"
        logger.info(f"  {personalized} {symbol_cfg.name}({symbol_cfg.code}):")
        logger.info(f"     加仓阈值: {add_drop}% | 止盈阈值: {take_profit}% | 最大加仓: {max_add}次 | 初始仓位: {init_pct}%")
    
    logger.info(f"\nT+0交易模式: 已启用")
    
    # 启动定时任务调度器（从配置文件读取间隔时间）
    logger.info("\n" + "=" * 60)
    logger.info("启动定时信号检查任务...")
    logger.info("=" * 60)
    
    scheduler_config = config.scheduler
    if scheduler_config.enabled:
        try:
            # 使用新的动态间隔配置，不传递interval_minutes参数
            scheduler = start_signal_scheduler()  # 不传参数，从配置读取动态间隔
            logger.info(f"✅ 定时任务调度器启动成功")
            logger.info(f"   交易时间检查间隔: {scheduler_config.trading_check_interval}分钟")
            logger.info(f"   非交易时间检查间隔: {scheduler_config.non_trading_check_interval}分钟")
            if scheduler_config.run_immediately_on_start:
                logger.info("🚀 已执行首次信号检查\n")
        except Exception as e:
            logger.error(f"❌ 定时任务调度器启动失败: {e}")
            logger.warning("⚠️ 系统将继续运行，但不会自动检查信号\n")
    else:
        logger.info("⏸️ 定时任务已禁用（根据配置）\n")

    # 启动API服务
    logger.info(f"启动API服务: http://{config.api.host}:{config.api.port}")
    logger.info(f"API文档: http://{config.api.host}:{config.api.port}/docs")
    
    try:
        uvicorn.run(
            app,
            host=config.api.host,
            port=config.api.port,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("\n🛑 接收到停止信号...")
    finally:
        # 停止定时任务
        stop_signal_scheduler()
        logger.info("👋 系统已退出")


if __name__ == "__main__":
    main()
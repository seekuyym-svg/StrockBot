# -*- coding: utf-8 -*-
"""信号数据持久化模块"""
import os
import json
from pathlib import Path
from datetime import datetime, date
from typing import List, Dict, Any
from loguru import logger


class DateTimeEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理datetime对象"""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


class SignalStorage:
    """信号数据存储管理器"""
    
    def __init__(self, base_dir: str = "signal"):
        """
        初始化信号存储器
        
        Args:
            base_dir: 基础目录，默认为"signal"
        """
        self.base_dir = Path(base_dir)
        # 确保目录存在
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"信号存储目录已就绪: {self.base_dir.absolute()}")
    
    def _get_today_dir(self) -> Path:
        """获取今天的日期目录"""
        today = datetime.now().strftime("%Y-%m-%d")
        today_dir = self.base_dir / today
        today_dir.mkdir(parents=True, exist_ok=True)
        return today_dir
    
    def save_signal(self, symbol: str, signal_data: Dict[str, Any]) -> str:
        """
        保存单个信号数据
        
        Args:
            symbol: ETF代码，如 sh.513120
            signal_data: 信号数据字典
            
        Returns:
            保存的文件路径
        """
        try:
            today_dir = self._get_today_dir()
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"{symbol.replace('.', '_')}_{timestamp}.json"
            filepath = today_dir / filename
            
            # 添加时间戳到数据中
            signal_data['saved_at'] = datetime.now().isoformat()
            
            # 写入JSON文件（使用自定义编码器）
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(signal_data, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
            
            logger.debug(f"信号已保存: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"保存信号数据失败: {e}")
            return ""
    
    def save_all_signals(self, signals_data: List[Dict[str, Any]]) -> str:
        """
        保存所有信号数据到一个文件
        
        Args:
            signals_data: 信号数据列表
            
        Returns:
            保存的文件路径
        """
        try:
            today_dir = self._get_today_dir()
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"all_signals_{timestamp}.json"
            filepath = today_dir / filename
            
            # 构建完整的数据结构
            storage_data = {
                "saved_at": datetime.now().isoformat(),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "count": len(signals_data),
                "signals": signals_data
            }
            
            # 写入JSON文件（使用自定义编码器）
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(storage_data, f, ensure_ascii=False, indent=2, cls=DateTimeEncoder)
            
            logger.info(f"所有信号已保存到: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"保存所有信号数据失败: {e}")
            return ""

    def get_today_signals(self) -> List[Path]:
        """
        获取今天的所有信号文件
        
        Returns:
            信号文件路径列表
        """
        today_dir = self._get_today_dir()
        if not today_dir.exists():
            return []
        
        return sorted(today_dir.glob("*.json"))
    
    def get_signal_history(self, days: int = 7) -> List[Path]:
        """
        获取历史信号文件
        
        Args:
            days: 获取最近几天的数据
            
        Returns:
            信号文件路径列表
        """
        from datetime import timedelta
        
        files = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            date_dir = self.base_dir / date_str
            
            if date_dir.exists():
                files.extend(sorted(date_dir.glob("*.json")))
        
        return files
    
    def load_signal_file(self, filepath: Path) -> Dict[str, Any]:
        """
        加载信号文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            信号数据字典
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载信号文件失败 {filepath}: {e}")
            return {}


# 全局信号存储器实例
_signal_storage = None


def get_signal_storage() -> SignalStorage:
    """获取信号存储器单例"""
    global _signal_storage
    if _signal_storage is None:
        _signal_storage = SignalStorage()
    return _signal_storage


def save_signal_to_file(symbol: str, signal_data: Dict[str, Any]) -> str:
    """便捷函数：保存单个信号"""
    storage = get_signal_storage()
    return storage.save_signal(symbol, signal_data)


def save_all_signals_to_file(signals_data: List[Dict[str, Any]]) -> str:
    """便捷函数：保存所有信号"""
    storage = get_signal_storage()
    return storage.save_all_signals(signals_data)

# -*- coding: utf-8 -*-
"""定时任务调度器 - 自动获取ETF信号"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, time
import sys
from pathlib import Path
from loguru import logger

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.strategy.engine import get_strategy_engine
from src.utils.signal_storage import save_signal_to_file
from src.models.models import SignalType
from src.market.data_provider import get_sh_index
from src.utils.config import get_config
from src.utils.notification import send_signal_notification


class SignalScheduler:
    """信号定时获取调度器"""
    
    def __init__(self, interval_minutes=5):
        """
        初始化调度器
        
        Args:
            interval_minutes: 检查间隔（分钟），默认5分钟
        """
        self.interval_minutes = interval_minutes
        self.scheduler = BackgroundScheduler()
        self.engine = get_strategy_engine()
        self.config = get_config()
        
        # ETF标的列表
        self.symbols = ["sh.513120", "sh.513050"]
        
        # 交易时间配置
        trading_hours = self.config.scheduler.trading_hours
        self.trading_days = trading_hours.trading_days
        self.sessions = self._parse_sessions(trading_hours.sessions)
        
        logger.info(f"信号调度器已初始化，检查间隔: {interval_minutes}分钟")
        logger.info(f"交易时间配置: 周{self.trading_days}")
        for i, session in enumerate(self.sessions, 1):
            logger.info(f"  时段{i}: {session['start'].strftime('%H:%M')} - {session['end'].strftime('%H:%M')}")
    
    def _parse_sessions(self, sessions_config):
        """
        解析交易时间段配置
        
        Args:
            sessions_config: 配置中的时间段列表
            
        Returns:
            解析后的时间段列表，每个元素包含start和end时间对象
        """
        parsed_sessions = []
        for session in sessions_config:
            start_parts = session.start_time.split(":")
            end_parts = session.end_time.split(":")
            
            start_time = time(hour=int(start_parts[0]), minute=int(start_parts[1]))
            end_time = time(hour=int(end_parts[0]), minute=int(end_parts[1]))
            
            parsed_sessions.append({
                'start': start_time,
                'end': end_time
            })
        
        return parsed_sessions
    
    def is_trading_time(self):
        """
        判断当前是否为交易时间
        
        Returns:
            bool: True表示交易时间，False表示非交易时间
        """
        now = datetime.now()
        
        # 检查是否为交易日
        # Python中weekday(): 0=周一, 1=周二, ..., 6=周日
        # 配置中: 1=周一, 2=周二, ..., 7=周日
        python_weekday = now.weekday() + 1  # 转换为1-7格式
        if python_weekday not in self.trading_days:
            return False
        
        # 检查是否在任何一个交易时间段内
        current_time = now.time()
        for session in self.sessions:
            if session['start'] <= current_time <= session['end']:
                return True
        
        return False
    
    def _check_single_signal(self, symbol):
        """
        检查单个ETF的信号
        
        Args:
            symbol: ETF代码
        """
        try:
            # 获取信号
            signal = self.engine.analyze(symbol)
            
            if not signal:
                logger.warning(f"⚠️ 未获取到 {symbol} 的信号")
                return
            
            # 格式化时间
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # 根据信号类型处理
            if signal.signal_type in [SignalType.BUY, SignalType.ADD, SignalType.SELL]:
                # 重要信号：打印 + 持久化
                self._log_important_signal(signal, current_time)
                self._save_signal(signal)
                
            elif signal.signal_type == SignalType.WAIT:
                # 等待信号：仅打印
                self._log_wait_signal(signal, current_time)
                
            else:
                # 其他信号（如STOP）：打印 + 持久化
                logger.info(f"🔔 [{current_time}] {signal.name}({symbol}): {signal.signal_type.value}")
                logger.info(f"   价格: ¥{signal.price:.3f}, 涨跌幅: {signal.change_pct:+.2f}%")
                if signal.reason:
                    logger.info(f"   原因: {signal.reason}")
                self._save_signal(signal)
                
                # 发送飞书通知
                self._send_feishu_notification(signal)
                
        except Exception as e:
            logger.error(f"❌ 检查 {symbol} 信号时出错: {e}")
    
    def _log_important_signal(self, signal, current_time):
        """记录重要信号（BUY/ADD/SELL）"""
        # 使用醒目的emoji和格式
        emoji_map = {
            SignalType.BUY: "🟢",
            SignalType.ADD: "🔵",
            SignalType.SELL: "🔴"
        }
        
        emoji = emoji_map.get(signal.signal_type, "📊")
        
        logger.success(f"\n{'='*60}")
        logger.success(f"{emoji} 【重要信号】{current_time}")
        logger.success(f"{'='*60}")
        logger.success(f"标的: {signal.name} ({signal.symbol})")
        logger.success(f"信号: {signal.signal_type.value}")
        logger.success(f"价格: ¥{signal.price:.3f}")
        logger.success(f"涨跌幅: {signal.change_pct:+.2f}%")
        
        if signal.target_shares > 0:
            logger.success(f"目标份额: {signal.target_shares:,}")
        
        if signal.avg_cost > 0:
            logger.success(f"平均成本: ¥{signal.avg_cost:.3f}")
        
        # 显示BOLL布林带价差信息（绝对值和百分比）
        if signal.signal_type in [SignalType.BUY, SignalType.ADD]:
            if signal.boll_down_diff_pct is not None:
                # 计算价差绝对值：买入价格 - BOLL下轨
                boll_down_diff_abs = signal.price * signal.boll_down_diff_pct / 100
                boll_position = "上方" if signal.boll_down_diff_pct > 0 else "下方"
                logger.success(f"📊 BOLL下轨价差: ¥{abs(boll_down_diff_abs):.3f} ({abs(signal.boll_down_diff_pct):.2f}%, {boll_position})")
        elif signal.signal_type == SignalType.SELL:
            if signal.boll_up_diff_pct is not None:
                # 计算价差绝对值：BOLL上轨 - 卖出价格
                boll_up_diff_abs = signal.price * signal.boll_up_diff_pct / 100
                boll_position = "上方" if signal.boll_up_diff_pct > 0 else "下方"
                logger.success(f"📊 BOLL上轨价差: ¥{abs(boll_up_diff_abs):.3f} ({abs(signal.boll_up_diff_pct):.2f}%, {boll_position})")
        
        if signal.reason:
            logger.success(f"原因: {signal.reason}")
        
        logger.success(f"{'='*60}\n")
        
        # 发送飞书通知
        self._send_feishu_notification(signal)
    
    def _log_wait_signal(self, signal, current_time):
        """记录等待信号（仅打印，不持久化）"""
        logger.info(f"⏸️  [{current_time}] {signal.name}({signal.symbol}): WAIT")
        logger.info(f"   当前价格: ¥{signal.price:.3f}, 涨跌幅: {signal.change_pct:+.2f}%")
        
        # 显示目标价格信息
        if signal.next_add_price and signal.next_add_price > 0:
            add_drop_pct = (signal.price - signal.next_add_price) / signal.price * 100
            logger.info(f"   📈 下次加仓价: ¥{signal.next_add_price:.3f} (还需下跌 {add_drop_pct:.2f}%)")
        
        if signal.next_sell_price and signal.next_sell_price > 0:
            sell_profit_pct = (signal.next_sell_price - signal.price) / signal.price * 100
            logger.info(f"   📉 止盈卖出价: ¥{signal.next_sell_price:.3f} (需上涨 {sell_profit_pct:.2f}%)")
        
        if signal.reason:
            logger.debug(f"   原因: {signal.reason}")
    
    def _save_signal(self, signal):
        """保存信号到文件"""
        try:
            signal_data = signal.model_dump()
            saved_path = save_signal_to_file(signal.symbol, signal_data)
            if saved_path:
                logger.debug(f"💾 信号已保存: {saved_path}")
        except Exception as e:
            logger.error(f"保存信号失败: {e}")
    
    def _send_feishu_notification(self, signal):
        """
        发送飞书通知
        
        Args:
            signal: 信号对象
        """
        try:
            signal_data = signal.model_dump()
            success = send_signal_notification(signal_data)
            if success:
                logger.debug(f"📱 飞书通知已发送")
            else:
                logger.debug(f"⚠️ 飞书通知发送失败（可能未启用或配置错误）")
        except Exception as e:
            logger.error(f"发送飞书通知异常: {e}")
    
    def check_all_signals(self):
        """检查所有ETF信号（仅在交易时间执行）"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 判断是否为交易时间
        if self.is_trading_time():
            logger.info(f"\n{'='*60}")
            logger.info(f"🔄 【交易时间】开始信号检查...")
            logger.info(f"{'='*60}")
            
            for symbol in self.symbols:
                self._check_single_signal(symbol)
            
            logger.info(f"✅ 本轮信号检查完成\n")
        else:
            # 非交易时间：只输出上证指数
            self._log_non_trading_time(current_time)
    
    def _log_non_trading_time(self, current_time):
        """非交易时间：输出上证指数信息"""
        try:
            # 获取上证指数
            sh_index = get_sh_index()
            
            if sh_index and sh_index > 0:
                logger.info(f"⏰ [{current_time}] 非交易时间 | 上证指数: {sh_index:.2f}")
            else:
                logger.warning(f"⏰ [{current_time}] 非交易时间 | 上证指数: 获取失败")
        except Exception as e:
            logger.warning(f"⏰ [{current_time}] 非交易时间 | 上证指数: 获取异常 ({e})")
    
    def start(self):
        """启动定时任务"""
        # 添加定时任务
        self.scheduler.add_job(
            func=self.check_all_signals,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id='signal_check_job',
            name=f'每{self.interval_minutes}分钟检查ETF信号',
            replace_existing=True
        )
        
        # 立即执行一次
        logger.info("🚀 立即执行首次信号检查...")
        self.check_all_signals()
        
        # 启动调度器
        self.scheduler.start()
        logger.info(f"✅ 定时任务已启动，每{self.interval_minutes}分钟自动检查")
        logger.info(f"📅 下次检查时间: {self._get_next_run_time()}")
    
    def stop(self):
        """停止定时任务"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("⏹️ 定时任务已停止")
    
    def _get_next_run_time(self):
        """获取下次运行时间"""
        try:
            job = self.scheduler.get_job('signal_check_job')
            if job and job.next_run_time:
                return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
        except:
            pass
        return "未知"


# 全局调度器实例
_scheduler = None


def get_signal_scheduler(interval_minutes=5):
    """获取信号调度器单例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = SignalScheduler(interval_minutes)
    return _scheduler


def start_signal_scheduler(interval_minutes=5):
    """启动信号调度器"""
    scheduler = get_signal_scheduler(interval_minutes)
    scheduler.start()
    return scheduler


def stop_signal_scheduler():
    """停止信号调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None

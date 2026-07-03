# -*- coding: utf-8 -*-
"""
买入委托定时任务调度器

功能：
1. 每周一至周五上午9:26自动执行买入委托计算
2. 读取前一日的选股结果文件
3. 生成交易委托明细并保存
4. 通过飞书推送委托明细通知
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import requests
import time
from src.utils.notification import get_feishu_notifier

# 全局调度器实例
_buy_order_scheduler = None


def check_stockpool_file() -> bool:
    """
    检查是否存在前一日的选股结果文件
    
    Returns:
        bool: 文件是否存在
    """
    try:
        # 计算前一天的日期
        yesterday = datetime.now() - timedelta(days=1)
        
        # 如果是周一，前一日是周日，需要追溯到周五
        if yesterday.weekday() == 6:  # 周日
            yesterday = yesterday - timedelta(days=2)
        elif yesterday.weekday() == 5:  # 周六
            yesterday = yesterday - timedelta(days=1)
        
        date_str = yesterday.strftime('%Y%m%d')
        filename = f"stockpool_{date_str}.txt"
        filepath = project_root / "data" / filename
        
        if filepath.exists():
            logger.info(f"[OK] 找到选股结果文件: {filepath}")
            return True
        else:
            logger.warning(f"[WARN] 选股结果文件不存在: {filepath}")
            return False
            
    except Exception as e:
        logger.error(f"[ERROR] 检查选股结果文件失败: {e}")
        return False


def execute_buy_calculation():
    """
    执行买入委托计算并发送飞书通知
    """
    logger.info("=" * 80)
    logger.info(f"[START] 开始执行买入委托计算任务")
    logger.info(f"[TIME] 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    # 0. 检查是否为交易日（剔除法定节假日）
    try:
        import akshare as ak
        today_str = datetime.now().strftime('%Y-%m-%d')
        df = ak.tool_trade_date_hist_sina()
        if not df.empty:
            # 取最近一年交易日，判断今天是否在其中
            latest = df.tail(365)
            is_trading = today_str in latest['trade_date'].astype(str).values
            if not is_trading:
                logger.warning(f"[SKIP] 今日({today_str})非交易日（法定节假日），跳过本次执行")
                return
    except Exception as e:
        logger.warning(f"[CALENDAR] 获取交易日历失败({e})，降级为仅过滤周末")

    # 1. 检查选股结果文件
    logger.info("\n[STEP 1] 检查选股结果文件...")
    if not check_stockpool_file():
        logger.warning("[SKIP] 未找到前一日的选股结果文件，跳过本次执行")
        logger.info("[TIP] 提示：请确保已运行 select_stocks_volume.py 生成选股结果")
        return
    
    # 2. 导入并执行买入计算模块
    logger.info("\n[STEP 2] 执行买入委托计算...")
    try:
        # 动态导入 tool_calc_buynum_simple 模块
        import tool_calc_buynum_simple as buy_module
        
        # 执行买入计算
        buy_module.calculate_buy_orders()
        
        logger.success("[OK] 买入委托计算完成")
        
    except ImportError as e:
        logger.error(f"[ERROR] 导入买入计算模块失败: {e}")
        logger.error("[TIP] 提示：请确保 tool_calc_buynum_simple.py 文件存在于项目根目录")
        return
    except Exception as e:
        logger.error(f"[ERROR] 执行买入计算失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return
    
    # 3. 发送国际市场早盘概览
    logger.info("\n[STEP 3] 发送国际市场早盘概览...")
    try:
        send_index_snapshot()
    except Exception as e:
        logger.error(f"[STEP 3] 国际市场早盘概览发送异常: {e}")
    
    # 4. 读取交易报告文件并发送飞书通知
    logger.info("\n[STEP 4] 发送买入委托通知...")
    try:
        send_trade_notification()
    except Exception as e:
        logger.error(f"[STEP 4] 买入委托通知发送异常: {e}")


def send_index_snapshot():
    """
    获取三大外盘指数数据并通过飞书发送早盘概览
    """
    logger.info("[INDEX] 获取国际市场指数数据...")

    # ── 1. 纳斯达克（腾讯kline接口，隔夜收盘数据）──
    nasdaq_data = None
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(
            'http://web.ifzq.gtimg.cn/appstock/app/kline/kline',
            params={'p': 1, 'param': f'usIXIC,day,{(datetime.now()-timedelta(days=20)).strftime("%Y-%m-%d")},{datetime.now().strftime("%Y-%m-%d")},25'},
            headers=headers, timeout=10
        )
        data = resp.json()
        klines = data['data']['us.IXIC']['day']
        if len(klines) >= 2:
            last = klines[-1]
            prev = klines[-2]
            close_price = float(last[2])
            prev_close = float(prev[2])
            change_pct = (close_price - prev_close) / prev_close * 100
            nasdaq_data = {
                'name': '纳斯达克',
                'price': f"{close_price:.2f}",
                'change_pct': f"{change_pct:+.2f}%",
                'flag': '🇺🇸',
            }
    except Exception as e:
        logger.warning(f"[INDEX] 纳斯达克获取失败: {e}")

    # ── 2. 日经225（东方财富接口，实时数据，价格÷100）──
    nikkei_data = None
    headers_em = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                  'Referer': 'https://quote.eastmoney.com/'}
    for attempt in range(2):  # 重试1次，提高实时数据获取率
        try:
            resp = requests.get(
                'http://push2.eastmoney.com/api/qt/stock/get',
                params={'secid': '100.N225', 'fields': 'f43,f44,f46,f170,f171'},
                headers=headers_em, timeout=10
            )
            try:
                data = resp.json() if resp.text and resp.text.strip() else {}
            except Exception:
                data = {}
            if data.get('data'):
                d = data['data']
                price = d.get('f43', 0) / 100.0
                prev_close = d.get('f44', 0) / 100.0
                if price and prev_close and prev_close > 0:
                    change_pct = (price - prev_close) / prev_close * 100
                    nikkei_data = {
                        'name': '日经225',
                        'price': f"{price:.2f}",
                        'change_pct': f"{change_pct:+.2f}%",
                        'flag': '🇯🇵',
                    }
                    break  # 成功则跳出重试
            if nikkei_data is None and attempt == 0:
                time.sleep(1)  # 重试前等1秒
        except Exception:
            if attempt == 0:
                time.sleep(1)

    # ── 2b. 日经225降级方案：东方财富失败时走新浪历史K线取开盘价 ──
    if nikkei_data is None:
        try:
            import akshare as ak
            df = ak.index_global_hist_sina(symbol="日经225指数")
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                today = datetime.now().date()  # datetime.date类型，与新浪date列一致
                # 找今天或最近一个交易日
                row = df[df['date'] == today]
                if row.empty:
                    row = df.tail(1)
                row = row.iloc[-1]
                open_price = float(row['open'])
                prev_close = float(row['close'])  # 用前一日close近似
                # 从倒数第二行取前一日收盘价
                if len(df) >= 2:
                    prev_close = float(df.iloc[-2]['close'])
                change_pct = (open_price - prev_close) / prev_close * 100
                nikkei_data = {
                    'name': '日经225',
                    'price': f"{open_price:.2f}",
                    'change_pct': f"{change_pct:+.2f}%",
                    'flag': '🇯🇵',
                }
                logger.info("[INDEX] 日经225(新浪降级)获取成功")
        except Exception as e2:
            logger.warning(f"[INDEX] 日经225新浪降级也失败: {e2}")

    # ── 3. KOSPI（东方财富接口，实时数据，价格÷100）──
    kospi_data = None
    for attempt in range(2):  # 重试1次，提高实时数据获取率
        try:
            resp = requests.get(
                'http://push2.eastmoney.com/api/qt/stock/get',
                params={'secid': '100.KS11', 'fields': 'f43,f44,f46,f170,f171'},
                headers=headers_em, timeout=10
            )
            try:
                data = resp.json() if resp.text and resp.text.strip() else {}
            except Exception:
                data = {}
            if data.get('data'):
                d = data['data']
                price = d.get('f43', 0) / 100.0
                prev_close = d.get('f44', 0) / 100.0
                if price and prev_close and prev_close > 0:
                    change_pct = (price - prev_close) / prev_close * 100
                    kospi_data = {
                        'name': 'KOSPI',
                        'price': f"{price:.2f}",
                        'change_pct': f"{change_pct:+.2f}%",
                        'flag': '🇰🇷',
                    }
                    break  # 成功则跳出重试
            if kospi_data is None and attempt == 0:
                time.sleep(1)
        except Exception:
            if attempt == 0:
                time.sleep(1)

    # ── 3b. KOSPI降级方案：东方财富失败时走新浪历史K线取开盘价 ──
    if kospi_data is None:
        try:
            import akshare as ak
            df = ak.index_global_hist_sina(symbol="首尔综合指数")
            if df is not None and not df.empty:
                today = datetime.now().date()  # datetime.date类型，与新浪date列一致
                row = df[df['date'] == today]
                if row.empty:
                    row = df.tail(1)
                row = row.iloc[-1]
                open_price = float(row['open'])
                if len(df) >= 2:
                    prev_close = float(df.iloc[-2]['close'])
                else:
                    prev_close = float(row['close'])
                change_pct = (open_price - prev_close) / prev_close * 100
                kospi_data = {
                    'name': 'KOSPI',
                    'price': f"{open_price:.2f}",
                    'change_pct': f"{change_pct:+.2f}%",
                    'flag': '🇰🇷',
                }
                logger.info("[INDEX] KOSPI(新浪降级)获取成功")
        except Exception as e2:
            logger.warning(f"[INDEX] KOSPI新浪降级也失败: {e2}")

    # ── 4. 计算综合评分（量比+科创50+KOSPI）──
    buy_score = None
    score_detail = ""

    # 4a. 前日量比（腾讯上证成交量）
    vol_ratio = None
    try:
        resp = requests.get(
            'http://web.ifzq.gtimg.cn/appstock/app/kline/kline',
            params={'p': 1, 'param': f'sh000001,day,{(datetime.now()-timedelta(days=20)).strftime("%Y-%m-%d")},{datetime.now().strftime("%Y-%m-%d")},20'},
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=10
        )
        data = resp.json()
        klines = data['data']['sh000001']['day']
        if len(klines) >= 6:
            y_vol = float(klines[-1][5])  # 昨日成交量（腾讯kline只返回已收盘日K线）
            recent = [float(k[5]) for k in klines[-6:-1]]  # 前5日均量
            vol_ratio = round(y_vol / (sum(recent) / len(recent)), 2)
            logger.info(f"[SCORE] 前日量比: {vol_ratio}")
    except Exception as e:
        logger.warning(f"[SCORE] 量比获取失败: {e}")

    # 4b. 前日科创50涨跌幅（本地CSV）
    kc_change = None
    try:
        import pandas as pd
        csv_path = Path(__file__).parent.parent.parent / "data" / "index_kc.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, parse_dates=['date'])
            df = df.sort_values('date')
            if len(df) >= 2:
                y_kc = df.iloc[-2]  # 前天
                t_kc = df.iloc[-1]  # 昨天（CSV每日16时更新，9:26时最后一条=昨日）
                # 昨天相对于前天的涨跌幅
                kc_change = (t_kc['close'] - y_kc['close']) / y_kc['close'] * 100
                logger.info(f"[SCORE] 前日科创50涨跌: {kc_change:+.2f}%")
    except Exception as e:
        logger.warning(f"[SCORE] 科创50获取失败: {e}")

    # 4c. 当日KOSPI涨跌幅（已有数据）
    kospi_pct = None
    if kospi_data:
        kospi_str = kospi_data['change_pct']
        try:
            kospi_pct = float(kospi_str.replace('%', ''))
        except:
            pass

    # 4d. 综合评分
    def _score_lb(v):
        return 3 if v is not None and v <= 1.00 else 2 if v is not None and v <= 1.10 else 1 if v is not None and v <= 1.15 else 0
    def _score_kc(v):
        return 3 if v is not None and v >= 2.0 else 2 if v is not None and v >= 0 else 1 if v is not None and v >= -2.0 else 0
    def _score_ks(v):
        return 3 if v is not None and v >= 1.0 else 2 if v is not None and v >= 0 else 1 if v is not None and v >= -1.0 else 0

    s_lb = _score_lb(vol_ratio)
    s_kc = _score_kc(kc_change)
    s_ks = _score_ks(kospi_pct)
    raw_total = s_lb + s_kc + s_ks

    # 排除规则：前日科创50过热阶梯扣分（涨越多扣越多）
    if kc_change is not None:
        if kc_change > 5.0:
            penalty = 3
        elif kc_change > 4.0:
            penalty = 2
        elif kc_change > 3.0:
            penalty = 1
        else:
            penalty = 0
    else:
        penalty = 0
    final_total = raw_total - penalty

    # 转为建议
    if final_total >= 7:
        advice = "✅ 推荐买入"
        advice_color = "green"
    elif final_total >= 5:
        advice = "🟡 可买(控制仓位)"
        advice_color = "yellow"
    elif final_total >= 3:
        advice = "🟠 谨慎"
        advice_color = "orange"
    else:
        advice = "🔴 不买(观望)"
        advice_color = "red"

    # 评分明细（仅显示有数据的项）
    parts_info = []
    if vol_ratio is not None:
        parts_info.append(f"量比{vol_ratio:.2f} ({s_lb}分)")
    else:
        parts_info.append("量比N/A")
    if kc_change is not None:
        parts_info.append(f"科创{kc_change:+.2f}% ({s_kc}分)")
    else:
        parts_info.append("科创N/A")
    if kospi_pct is not None:
        parts_info.append(f"KOSPI{kospi_pct:+.2f}% ({s_ks}分)")
    else:
        parts_info.append("KOSPI N/A")
    score_detail = " | ".join(parts_info)
    if penalty:
        score_detail += " (过热降级-1)"

    # ── 4e. 存入历史记录文件 ──
    try:
        hist_file = Path(__file__).parent.parent.parent / "data" / "buy_decision_history.txt"
        date_str = datetime.now().strftime('%Y-%m-%d')
        vol_str = f"{vol_ratio:.2f}" if vol_ratio is not None else "N/A"
        kc_str = f"{kc_change:+.2f}" if kc_change is not None else "N/A"
        ks_str = f"{kospi_pct:+.2f}" if kospi_pct is not None else "N/A"
        # 格式: 日期,量比,科创50涨跌,KOSPI涨跌,量比分,科创分,KOSPI分,原始总分,降级,最终总分,建议,实际收益(待补)
        # 建议转纯文字（去掉表情符号）
        advice_text = advice.replace('✅ ','').replace('🟡 ','').replace('🟠 ','').replace('🔴 ','')
        record = f"{date_str},{vol_str},{kc_str},{ks_str},{s_lb},{s_kc},{s_ks},{raw_total},{penalty},{final_total},{advice_text},\n"
        # 文件不存在时写入表头
        if not hist_file.exists():
            with open(hist_file, 'w', encoding='utf-8') as f:
                f.write("date,vol_ratio,kc_change,kospi_pct,score_lb,score_kc,score_ks,raw_total,penalty,final_total,advice,actual_return\n")
        with open(hist_file, 'a', encoding='utf-8') as f:
            f.write(record)
        logger.info(f"[HISTORY] 已记录决策到 {hist_file.name}")
    except Exception as e:
        logger.warning(f"[HISTORY] 记录失败: {e}")

    # ── 5. 构建飞书消息 ──
    index_list = [d for d in [nasdaq_data, nikkei_data, kospi_data] if d is not None]
    if not index_list:
        logger.warning("[INDEX] 所有指数数据获取失败，跳过推送")
        return

    notifier = get_feishu_notifier()
    if not notifier.enabled:
        logger.warning("[INDEX] 飞书通知未启用，跳过推送")
        return

    today = datetime.now().strftime('%m/%d')
    content = f"**📡 国际市场早盘概览 — {today}**\n\n"

    for idx in index_list:
        content += f"{idx['flag']} **{idx['name']}**: {idx['price']} ({idx['change_pct']})\n"

    # 方向判断
    up_count = sum(1 for idx in index_list if not idx['change_pct'].startswith('-'))
    dn_count = len(index_list) - up_count
    if up_count > dn_count:
        content += f"\n📈 **三指数方向**: 多数上涨"
    elif dn_count > up_count:
        content += f"\n📉 **三指数方向**: 多数下跌"
    else:
        content += f"\n➖ **三指数方向**: 涨跌不一"

    # 评分和建议
    content += f"\n\n**━━━ 综合评分 ━━━**\n"
    content += f"{score_detail}\n"
    content += f"**总分**: {final_total}/9  **建议**: {advice}"

    content += f"\n\n_数据来源: 腾讯财经 / 东方财富 / 新浪_"

    message = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🌏 国际市场早盘概览"},
                "template": "blue"
            },
            "elements": [
                {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                {"tag": "hr"},
                {"tag": "note", "elements": [
                    {"tag": "plain_text", "content": f"ETF马丁格尔量化交易系统 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"}
                ]}
            ]
        }
    }

    try:
        import json as _json
        headers = {'Content-Type': 'application/json'}
        resp = requests.post(notifier.webhook_url, headers=headers,
                             data=_json.dumps(message, ensure_ascii=False).encode('utf-8'), timeout=10)
        if resp.status_code == 200:
            result = resp.json()
            if result.get('StatusCode') == 0 or result.get('code') == 0:
                logger.success("[INDEX] 国际市场早盘概览推送成功")
            else:
                logger.error(f"[INDEX] 飞书API返回错误: {result.get('msg', '未知')}")
        else:
            logger.error(f"[INDEX] 飞书HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"[INDEX] 推送失败: {e}")


def send_trade_notification():
    """
    读取交易报告文件并通过飞书发送通知
    """
    try:
        # 读取今天的交易报告文件
        date_str = datetime.now().strftime('%Y%m%d')
        filename = f"trade_{date_str}.txt"
        filepath = project_root / "data" / filename
        
        if not filepath.exists():
            logger.warning(f"[WARN] 交易报告文件不存在: {filepath}")
            return
        
        logger.info(f"[FILE] 读取交易报告: {filepath}")
        
        # 解析文件内容
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) < 2:
            logger.warning("[WARN] 交易报告文件格式错误")
            return
        
        # 第一行是可买入股票个数
        stock_count = int(lines[0].strip())
        
        if stock_count == 0:
            logger.info("[INFO] 今日没有可买入的股票")
            return
        
        # 构建飞书消息内容
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        content = f"**今日买入委托明细**\n"
        content += f"**时间**: {current_time}\n"
        content += f"**数量**: {stock_count} 只股票\n\n"
        content += f"**━━━━━━━━━━━━━━━**\n\n"
        
        # 解析每只股票的委托明细
        for i, line in enumerate(lines[2:], 1):  # 从第3行开始（跳过表头）
            line = line.strip()
            if not line:
                continue
            
            parts = line.split(',')
            if len(parts) != 4:
                continue
            
            code = parts[0].strip()
            open_price = float(parts[1].strip())
            shares = int(parts[2].strip())
            amount = float(parts[3].strip())
            
            # 获取股票名称
            stock_name = get_stock_name(code)
            
            # 格式化输出
            content += f"**{i}. {stock_name} ({code})**\n"
            content += f"   开盘价: ¥{open_price:.2f}\n"
            content += f"   股数: {shares:,} 股\n"
            content += f"   金额: ¥{amount:,.2f}\n\n"
        
        content += f"**━━━━━━━━━━━━━━━**\n"
        
        # 获取飞书通知器
        notifier = get_feishu_notifier()
        
        if not notifier.enabled:
            logger.warning("[WARN] 飞书通知未启用，跳过发送")
            return
        
        # 构建飞书消息体
        message = {
            "msg_type": "interactive",
            "card": {
                "config": {
                    "wide_screen_mode": True
                },
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "今日买入委托"
                    },
                    "template": "green"
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": content
                        }
                    },
                    {
                        "tag": "hr"
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": f"ETF马丁格尔量化交易系统 | {current_time}"
                            }
                        ]
                    }
                ]
            }
        }
        
        # 发送飞书通知
        import requests
        import json
        
        headers = {'Content-Type': 'application/json'}
        response = requests.post(
            notifier.webhook_url,
            headers=headers,
            data=json.dumps(message, ensure_ascii=False).encode('utf-8'),
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('StatusCode') == 0 or result.get('code') == 0:
                logger.success(f"[OK] 飞书通知发送成功: {stock_count} 只股票")
            else:
                error_code = result.get('code', 'unknown')
                error_msg = result.get('msg', '未知错误')
                logger.error(f"[ERROR] 飞书API返回错误 (code: {error_code}): {error_msg}")
        else:
            logger.error(f"[ERROR] 飞书通知发送失败，HTTP状态码: {response.status_code}")
        
    except Exception as e:
        logger.error(f"[ERROR] 发送飞书通知失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


def get_stock_name(symbol: str) -> str:
    """
    根据股票代码获取股票名称（使用腾讯财经API）
    
    Args:
        symbol: 股票代码（不含市场前缀），如 '000526'
    
    Returns:
        str: 股票名称，获取失败则返回股票代码本身
    """
    try:
        import requests
        
        # 判断市场前缀
        if symbol.startswith('6') or symbol.startswith('9'):
            market_prefix = 'sh'
        else:
            market_prefix = 'sz'
        
        # 构建完整代码
        full_code = f"{market_prefix}{symbol}"
        
        # 调用腾讯财经API
        url = f"http://qt.gtimg.cn/q={full_code}"
        response = requests.get(url, timeout=5)
        response.encoding = 'gbk'  # 腾讯财经返回GBK编码
        
        if response.status_code == 200:
            data_str = response.text.strip()
            if '=' in data_str:
                content = data_str.split('=')[1].strip('"').strip(';')
                parts = content.split('~')
                if len(parts) >= 2:
                    stock_name = parts[1]
                    if stock_name and stock_name != '':
                        return stock_name
        
        # 获取失败，返回股票代码
        return symbol
        
    except Exception as e:
        logger.warning(f"⚠️  获取股票 {symbol} 名称失败: {e}")
        return symbol


def start_buy_order_scheduler():
    """
    启动买入委托定时任务调度器
    
    Returns:
        BlockingScheduler: 调度器实例
    """
    global _buy_order_scheduler
    
    if _buy_order_scheduler is not None and _buy_order_scheduler.running:
        logger.warning("⚠️  买入委托调度器已在运行")
        return _buy_order_scheduler
    
    # 从配置文件读取配置
    from src.utils.config import get_config
    config = get_config()
    buy_order_config = config.buy_order_scheduler
    
    logger.info("=" * 80)
    logger.info("[TASK] 买入委托定时任务调度器")
    logger.info("=" * 80)
    logger.info(f"[TIME] 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"[SCHEDULE] 定时任务: 周一至周五 {buy_order_config.hour:02d}:{buy_order_config.minute:02d}")
    logger.info(f"[CONFIG] 最低评分要求: {buy_order_config.min_score}")
    logger.info("=" * 80)
    
    # 创建调度器
    _buy_order_scheduler = BlockingScheduler()
    
    # 添加定时任务：从配置文件读取执行时间
    _buy_order_scheduler.add_job(
        func=execute_buy_calculation,
        trigger=CronTrigger(
            day_of_week='mon-fri',
            hour=buy_order_config.hour,
            minute=buy_order_config.minute
        ),
        id='buy_order_task',
        name='买入委托计算任务',
        misfire_grace_time=300,  # 允许5分钟的误差
        coalesce=True  # 合并错过的执行
    )
    
    logger.info("[OK] 定时任务已注册")
    logger.info("[START] 调度器启动中...")
    
    # 在后台线程中启动（非阻塞）
    import threading
    def run_scheduler():
        try:
            _buy_order_scheduler.start()
        except Exception as e:
            logger.error(f"[ERROR] 调度器运行异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    logger.info("[OK] 买入委托调度器已在后台启动")
    return _buy_order_scheduler


def stop_buy_order_scheduler():
    """停止买入委托定时任务调度器"""
    global _buy_order_scheduler
    
    if _buy_order_scheduler is not None:
        try:
            _buy_order_scheduler.shutdown(wait=False)
            logger.info("[STOP] 买入委托调度器已停止")
        except Exception as e:
            logger.error(f"[ERROR] 停止买入委托调度器失败: {e}")
        finally:
            _buy_order_scheduler = None
    else:
        logger.debug("[INFO] 买入委托调度器未运行")


def main():
    """主函数：独立运行时的入口（阻塞模式）"""
    logger.info("=" * 80)
    logger.info("🎯 买入委托定时任务调度器（独立运行模式）")
    logger.info("=" * 80)
    logger.info(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("⏰ 定时任务: 周一至周五 09:26")
    logger.info("=" * 80)
    
    # 创建调度器
    scheduler = BlockingScheduler()
    
    # 添加定时任务：周一至周五上午9:26执行
    scheduler.add_job(
        func=execute_buy_calculation,
        trigger=CronTrigger(day_of_week='mon-fri', hour=9, minute=26),
        id='buy_order_task',
        name='买入委托计算任务',
        misfire_grace_time=300,  # 允许5分钟的误差
        coalesce=True  # 合并错过的执行
    )
    
    logger.info("✅ 定时任务已注册")
    logger.info("🚀 调度器启动中...")
    
    try:
        # 启动调度器（阻塞模式）
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("\n👋 收到中断信号，调度器停止")
    except Exception as e:
        logger.error(f"❌ 调度器运行异常: {e}")
        import traceback
        logger.error(traceback.format_exc())


if __name__ == "__main__":
    main()

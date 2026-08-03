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

# 股票名称缓存（模块级，减少腾讯API重复请求）
_stock_name_cache = {}


def get_previous_trading_day() -> str:
    """
    获取最近一个交易日（YYYYMMDD），使用akshare交易日历

    与 execute_buy_calculation 中的交易日判断保持一致，
    能正确跳过法定节假日（如周三放假，周四回溯到周二）。

    Returns:
        str: 最近交易日 YYYYMMDD
    """
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        if df is not None and not df.empty:
            today = datetime.now().strftime('%Y-%m-%d')
            dates = [str(d)[:10] for d in df['trade_date'].tolist()]
            prev = [d for d in dates if d < today]
            if prev:
                return max(prev).replace('-', '')
    except Exception as e:
        logger.warning(f"[CALENDAR] akshare交易日历失败({e})，降级为周末回溯")

    # 降级：手动周末回溯
    yesterday = datetime.now() - timedelta(days=1)
    if yesterday.weekday() == 6:  # 周日
        yesterday -= timedelta(days=2)
    elif yesterday.weekday() == 5:  # 周六
        yesterday -= timedelta(days=1)
    return yesterday.strftime('%Y%m%d')


def check_stockpool_file() -> bool:
    """
    检查是否存在前一日的选股结果文件（最近交易日）
    
    Returns:
        bool: 文件是否存在
    """
    try:
        date_str = get_previous_trading_day()
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


# 大盘评分<6时使用的防守ETF列表（沪市）
DEFENSIVE_ETFS = ['513850', '513050', '513120', '516310', '515170']

# 大盘综合评分买入阈值（10分制）：≥此分从股票池选股，<此分用防守ETF
SCORE_BUY_THRESHOLD = 6


def _send_alert_notification(title: str, message: str):
    """发送一条简单的飞书告警卡片"""
    try:
        notifier = get_feishu_notifier()
        if not notifier.enabled:
            logger.warning("[ALERT] 飞书通知未启用，告警未发送")
            return
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"tag": "plain_text", "content": title}, "template": "red"},
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": message}},
                    {"tag": "hr"},
                    {"tag": "note", "elements": [
                        {"tag": "plain_text", "content": f"ETF马丁格尔量化交易系统 | {current_time}"}
                    ]}
                ]
            }
        }
        import json as _json
        headers = {'Content-Type': 'application/json'}
        resp = requests.post(notifier.webhook_url, headers=headers,
                             data=_json.dumps(msg, ensure_ascii=False).encode('utf-8'), timeout=10)
        if resp.status_code == 200 and (resp.json().get('StatusCode') == 0 or resp.json().get('code') == 0):
            logger.success(f"[ALERT] 告警已发送: {title}")
        else:
            logger.error(f"[ALERT] 告警发送失败: HTTP {resp.status_code}")
    except Exception as e:
        logger.error(f"[ALERT] 告警发送异常: {e}")


def generate_etf_trade_file() -> bool:
    """
    大盘评分<6时，用防守ETF生成买入委托 trade 文件

    与股票池版生成逻辑一致：INITIAL_CAPITAL 平分给5只ETF，
    每只按开盘价计算100股整数倍的买入数量，保存到 trade_今日.txt。

    Returns:
        bool: True=生成成功，False=全部失败（已推送告警）
    """
    import tool_calc_buynum_simple as buy_module

    logger.info(f"[ETF] 使用防守ETF生成买入委托: {DEFENSIVE_ETFS}")

    watchlist = []
    for code in DEFENSIVE_ETFS:
        # 用本模块 get_stock_name（支持5开头沪市ETF，带缓存）
        name = get_stock_name(code)
        watchlist.append({'code': code, 'market': 'sh', 'name': name, 'score': 0.0})

    results = []
    total_investment = 0
    investment_per_stock = buy_module.INITIAL_CAPITAL / len(watchlist)
    logger.info(f"[ETF] 每只ETF分配资金: {investment_per_stock:,.2f} 元")

    for stock in watchlist:
        code = stock['code']
        realtime = buy_module.get_stock_realtime_data(code, 'sh')
        if realtime is None:
            logger.warning(f"[ETF] {code} 无法获取实时数据，跳过")
            continue
        open_price = realtime['open_price']
        shares = buy_module.calculate_buy_shares(open_price, investment_per_stock)
        actual_investment = shares * open_price
        results.append({
            'code': code,
            'name': stock['name'],
            'score': 0.0,
            'current_price': realtime['current_price'],
            'open_price': open_price,
            'change_pct': realtime['change_pct'],
            'shares': shares,
            'investment': actual_investment,
        })
        total_investment += actual_investment
        logger.info(f"[ETF] {code}({stock['name']}) 开盘{open_price:.3f} 买入{shares}股 金额{actual_investment:,.2f}元")

    if results:
        # ETF价格保留3位小数
        buy_module.save_trade_report(results, total_investment, price_decimals=3)
        logger.info(f"[ETF] trade 文件已生成（{len(results)}只ETF，总投入{total_investment:,.2f}元）")
        return True
    else:
        logger.warning("[ETF] 所有ETF均获取失败，未生成 trade 文件")
        _send_alert_notification(
            "⚠️ 买入委托计算失败",
            "**大盘评分 < 6，本应使用防守ETF生成买入委托，但5只ETF行情全部获取失败。**\n"
            f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"**ETF列表**: {', '.join(DEFENSIVE_ETFS)}"
        )
        return False


def execute_buy_calculation():
    """
    执行买入委托计算并发送飞书通知
    """
    logger.info("=" * 80)
    logger.info(f"[START] 开始执行买入委托计算任务")
    logger.info(f"[TIME] 执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)

    # 提前导入买入计算模块（两个分支共用）
    try:
        import tool_calc_buynum_simple as buy_module
    except ImportError as e:
        logger.error(f"[ERROR] 导入买入计算模块失败: {e}")
        logger.error("[TIP] 提示：请确保 tool_calc_buynum_simple.py 文件存在于项目根目录")
        return

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

    # 1. 先计算大盘综合评分（同时推送国际市场早盘概览）
    final_total = None
    logger.info("\n[STEP 1] 计算大盘综合评分 + 国际市场早盘概览...")
    try:
        final_total = send_index_snapshot()
    except Exception as e:
        logger.error(f"[STEP 1] 大盘评分计算异常: {e}")
    
    # 2. 根据评分决定买入委托生成方式
    #   ≥SCORE_BUY_THRESHOLD：从股票池生成；<阈值：从防守ETF生成
    if final_total is not None and final_total < SCORE_BUY_THRESHOLD:
        logger.info(f"\n[STEP 2] 大盘评分{final_total}<{SCORE_BUY_THRESHOLD}，使用防守ETF生成买入委托...")
        try:
            if not generate_etf_trade_file():
                # 生成失败已推送告警，跳过推送（避免读取残留的旧trade文件）
                return
            logger.success("[OK] 防守ETF买入委托计算完成")

            # 补充生成股票池trade文件（trade_YYYYMMDD_2.txt），保证委托全面性
            logger.info("补充生成股票池买入委托（trade_YYYYMMDD_2.txt）...")
            if check_stockpool_file():
                try:
                    buy_module.calculate_buy_orders(output_suffix="_2")
                    logger.success("[OK] 股票池买入委托已生成（trade_2）")
                except Exception as e:
                    logger.error(f"[ERROR] 补充生成股票池委托失败: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
            else:
                logger.warning("[SKIP] 股票池文件不存在，跳过补充生成")
        except Exception as e:
            logger.error(f"[ERROR] 执行ETF买入计算失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            _send_alert_notification("⚠️ 买入委托计算失败",
                                     f"**大盘评分{final_total}<{SCORE_BUY_THRESHOLD}，改用防守ETF时执行异常**: {e}")
            return
    else:
        logger.info("\n[STEP 2] 检查选股结果文件...")
        if not check_stockpool_file():
            logger.warning("[SKIP] 未找到前一日的选股结果文件，跳过本次执行")
            logger.info("[TIP] 提示：请确保已运行 select_stocks_volume.py 生成选股结果")
            return
        
        logger.info("执行买入委托计算（股票池）...")
        try:
            buy_module.calculate_buy_orders()
            logger.success("[OK] 买入委托计算完成")
        except Exception as e:
            logger.error(f"[ERROR] 执行买入计算失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return
    
    # 3. 读取交易报告文件并发送飞书通知
    logger.info("\n[STEP 3] 发送买入委托通知...")
    try:
        send_trade_notification(final_total_from_index=final_total)
    except Exception as e:
        logger.error(f"[STEP 3] 买入委托通知发送异常: {e}")


def _fetch_global_index(secid: str, sina_symbol: str, name: str, flag: str) -> dict:
    """
    获取全球指数数据：东方财富实时 → push2his日K线 → 新浪日K线（保底）

    Args:
        secid: 东方财富secid，如 '100.N225'（日经225）
        sina_symbol: akshare新浪指数名称，如 '日经225指数'
        name: 显示名称，如 '日经225'
        flag: 国旗emoji

    Returns:
        dict: {name, price, change_pct, flag} 或 None（全部失败）
    """
    headers_em = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                  'Referer': 'https://quote.eastmoney.com/'}

    def _build(price, prev_close):
        if price and prev_close and prev_close > 0:
            change_pct = (price - prev_close) / prev_close * 100
            return {'name': name, 'price': f"{price:.2f}",
                    'change_pct': f"{change_pct:+.2f}%", 'flag': flag}
        return None

    result = None

    # ① 东方财富实时 push2
    try:
        resp = requests.get(
            'http://push2.eastmoney.com/api/qt/stock/get',
            params={'secid': secid, 'fields': 'f43,f60'},
            headers=headers_em, timeout=8
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('data') and data['data'].get('f43'):
                d = data['data']
                result = _build(d['f43'] / 100.0, d['f60'] / 100.0)
    except Exception:
        pass

    # ② push2his 日K线（加日期检查，确保最近3天内）
    if result is None:
        for _attempt in range(2):
            try:
                resp = requests.get('https://push2his.eastmoney.com/api/qt/stock/kline/get',
                    params={'secid': secid, 'fields1': 'f1,f2,f3,f4,f5,f6',
                            'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
                            'klt': '101', 'fqt': '1',
                            'beg': (datetime.now()-timedelta(days=5)).strftime('%Y%m%d'),
                            'end': datetime.now().strftime('%Y%m%d'), 'lmt': '10'},
                    headers=headers_em, timeout=10)
                klines = resp.json()['data']['klines']
                if len(klines) >= 2:
                    last = klines[-1].split(','); prev = klines[-2].split(',')
                    days_off = (datetime.now() - datetime.strptime(last[0], '%Y-%m-%d')).days
                    if days_off <= 3:
                        result = _build(float(last[2]), float(prev[2]))
                        break
                if _attempt == 0:
                    time.sleep(1)
            except Exception:
                if _attempt == 0:
                    time.sleep(1)

    # ③ 新浪日K线（最后保底）
    if result is None:
        try:
            import akshare as ak
            df = ak.index_global_hist_sina(symbol=sina_symbol)
            if df is not None and len(df) >= 2:
                row = df.iloc[-1]; d = row['date']
                d_str = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)
                days_off = (datetime.now() - datetime.strptime(d_str, '%Y-%m-%d')).days
                if days_off <= 3:  # 最多滞后3天（跨周末）
                    result = _build(float(row['close']), float(df.iloc[-2]['close']))
                    logger.info(f"[INDEX] {name}(新浪) {d_str} 涨跌{result['change_pct']}")
                else:
                    logger.warning(f"[INDEX] {name}新浪数据滞后({d_str})，已跳过")
        except Exception as e2:
            logger.warning(f"[INDEX] {name}获取失败: {e2}")

    return result


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
        if len(klines) >= 3:
            today_str = datetime.now().strftime('%Y-%m-%d')
            # 跳过今日不完整K线（如有）
            if klines[-1][0] == today_str:
                last = klines[-2]
                prev = klines[-3]
            else:
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

    # ── 2/3. 日经225、KOSPI（三层获取逻辑已抽公共函数 _fetch_global_index）──
    nikkei_data = _fetch_global_index('100.N225', '日经225指数', '日经225', '🇯🇵')
    kospi_data = _fetch_global_index('100.KS11', '首尔综合指数', 'KOSPI', '🇰🇷')

    # ── 4. 计算综合评分（量比+科创50+KOSPI）──
    buy_score = None
    score_detail = ""

    # 4a-4f. 前日信号数据（signal_history.json 一次性读取）
    # 从最近一条 date <= 昨日 的记录中提取量比/科创/沪深300/情绪评分
    vol_ratio = None
    kc_change = None
    hs300_healthy = None
    emotion_score = 5.0  # 默认中性
    try:
        import json as _json
        signal_file = Path(__file__).parent.parent.parent / "data" / "signal_history.json"
        if signal_file.exists():
            yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            with open(signal_file, 'r', encoding='utf-8') as _f:
                records = _json.load(_f)

            # 找到最近一条 date <= 昨日的记录（自动跳过周末/节假日）
            latest_record = None
            for record in reversed(records):
                if record.get('date') <= yesterday_str:
                    latest_record = record
                    break

            if latest_record is None:
                logger.warning(f"[SCORE] signal_history.json 中未找到 {yesterday_str} 之前的记录")
            else:
                rec_date = latest_record.get('date', '?')
                vol_ratio = latest_record.get('volume_ratio', None)
                logger.info(f"[SCORE] 前日量比({rec_date}): {vol_ratio}")

                # 科创综指涨跌幅
                for idx in latest_record.get('indices', []):
                    if idx.get('name') == '科创综指':
                        kc_change = idx.get('change_pct', None)
                        logger.info(f"[SCORE] 前日科创综指涨跌({rec_date}): {kc_change if kc_change is None else f'{kc_change:+.2f}%'}")
                    elif idx.get('name') == '沪深300':
                        hs300_healthy = idx.get('healthy', None)
                        logger.info(f"[SCORE] 沪深300健康度({rec_date}): {hs300_healthy}")

                # 情绪评分
                emotion_data = latest_record.get('emotion')
                if emotion_data and emotion_data.get('score'):
                    emotion_score = float(emotion_data['score'])
                    logger.info(f"[SCORE] 前日情绪评分({rec_date}): {emotion_score}")
    except Exception as e:
        logger.warning(f"[SCORE] signal_history.json 读取失败: {e}")

    # 4c. 当日KOSPI涨跌幅（已有数据）
    kospi_pct = None
    if kospi_data:
        kospi_str = kospi_data['change_pct']
        try:
            kospi_pct = float(kospi_str.replace('%', ''))
        except:
            pass

    # 4g. 综合评分（10分制：量比+科创50+KOSPI+沪深300健康+情绪加权）
    def _score_lb(v):
        if v is None: return 0
        if 0.85 <= v <= 1.05: return 3     # 健康区间：量能适中
        if v < 0.85: return 2                # 明显缩量（无人气）
        if v <= 1.15: return 2               # 小幅放量
        if v <= 1.30: return 1               # 明显放量
        return 0                              # 极度放量 >1.30
    def _score_kc(v):
        return 3 if v is not None and v >= 2.0 else 2 if v is not None and v >= 0 else 1 if v is not None and v >= -2.0 else 0
    def _score_ks(v):
        return 3 if v is not None and v >= 5.0 else 2 if v is not None and v >= 3.0 else 1 if v is not None and v >= 0 else 0
    def _score_hs(v):
        return 1 if v is True else 0

    s_lb = _score_lb(vol_ratio)
    s_kc = _score_kc(kc_change)
    s_ks = _score_ks(kospi_pct)
    s_hs = _score_hs(hs300_healthy)
    raw_total = s_lb + s_kc + s_ks + s_hs  # 满分10分

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

    # 情绪正加权：前日情绪好（≥7分）且无过热降级时加分，情绪极差（<3分）时减分
    if emotion_score >= 7.0 and penalty == 0:
        emotion_bonus = 1
        logger.info(f"[SCORE] 情绪正加权: emotion_score={emotion_score} ≥7.0 → +1分")
    elif emotion_score < 3.0:
        emotion_bonus = -1
        logger.info(f"[SCORE] 情绪负加权: emotion_score={emotion_score} <3.0 → -1分")
    else:
        emotion_bonus = 0

    final_total = raw_total - penalty + emotion_bonus

    # 转为建议（10分制）
    if final_total >= 8:
        advice = "✅ 推荐买入"
        advice_color = "green"
    elif final_total >= SCORE_BUY_THRESHOLD:
        advice = "🟡 可买(控制仓位)"
        advice_color = "yellow"
    elif final_total >= 4:
        advice = "🟠 谨慎(不建议买入)"
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
    parts_info.append(f"沪深300{'✅' if hs300_healthy else '❌'} ({s_hs}分)")
    parts_info.append(f"情绪{emotion_score:.1f}分")
    score_detail = " | ".join(parts_info)
    if penalty:
        score_detail += f" (过热降级-{penalty})"
    if emotion_bonus != 0:
        score_detail += f" (情绪{'正' if emotion_bonus > 0 else '负'}加权{emotion_bonus:+.0f})"

    # ── 4e. 存入历史记录文件 ──
    try:
        hist_file = Path(__file__).parent.parent.parent / "data" / "buy_decision_history.txt"
        date_str = datetime.now().strftime('%Y-%m-%d')
        vol_str = f"{vol_ratio:.2f}" if vol_ratio is not None else "N/A"
        kc_str = f"{kc_change:+.2f}" if kc_change is not None else "N/A"
        ks_str = f"{kospi_pct:+.2f}" if kospi_pct is not None else "N/A"
        # 日经和纳斯达克涨跌幅（仅存储，不参与评分）
        nikkei_pct_str = ""
        if nikkei_data:
            try: nikkei_pct_str = f"{float(nikkei_data['change_pct'].replace('%','')):+.2f}"
            except: pass
        nasdaq_pct_str = ""
        if nasdaq_data:
            try: nasdaq_pct_str = f"{float(nasdaq_data['change_pct'].replace('%','')):+.2f}"
            except: pass
        # 建议转纯文字（去掉表情符号和括号内容，只保留主词）
        advice_text = advice.replace('✅ ','').replace('🟡 ','').replace('🟠 ','').replace('🔴 ','')
        if '(' in advice_text:
            advice_text = advice_text.split('(')[0]
        # 格式: date,vol_ratio,kc_change,kospi_pct,score_lb,score_kc,score_ks,score_hs,raw_total,penalty,emotion_bonus,final_total,advice,actual_return,nikkei_pct,nasdaq_pct
        record = f"{date_str},{vol_str},{kc_str},{ks_str},{s_lb},{s_kc},{s_ks},{s_hs},{raw_total},{penalty},{emotion_bonus},{final_total},{advice_text},,{nikkei_pct_str},{nasdaq_pct_str}\n"
        # 文件不存在时写入表头
        if not hist_file.exists():
            with open(hist_file, 'w', encoding='utf-8') as f:
                f.write("date,vol_ratio,kc_change,kospi_pct,score_lb,score_kc,score_ks,score_hs,raw_total,penalty,emotion_bonus,final_total,advice,actual_return,nikkei_pct,nasdaq_pct\n")
        with open(hist_file, 'a', encoding='utf-8') as f:
            f.write(record)
        logger.info(f"[HISTORY] 已记录决策到 {hist_file.name}")
    except Exception as e:
        logger.warning(f"[HISTORY] 记录失败: {e}")

    # ── 5. 构建飞书消息 ──
    index_list = [d for d in [nasdaq_data, nikkei_data, kospi_data] if d is not None]
    if not index_list:
        logger.warning("[INDEX] 所有指数数据获取失败，跳过推送")
        return final_total  # 评分已算出，仍返回供Step2使用

    notifier = get_feishu_notifier()
    if not notifier.enabled:
        logger.warning("[INDEX] 飞书通知未启用，跳过推送")
        return final_total  # 评分已算出，仍返回供Step2使用

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
    content += f"**总分**: {final_total}/10  **建议**: {advice}"

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

    return final_total


def send_trade_notification(final_total_from_index=None):
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
        
        # 统一展示委托明细（评分<阈值时为防守ETF委托，≥阈值为股票池委托）
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 标题区分：评分<阈值时是防守ETF
        if final_total_from_index is not None and final_total_from_index < SCORE_BUY_THRESHOLD:
            content = f"**今日买入委托（防守ETF）**\n"
            content += f"**时间**: {current_time}\n"
            content += f"**数量**: {stock_count} 只ETF\n\n"
            content += f"**━━━━━━━━━━━━━━━**\n\n"
            logger.info(f"[TRADE] 评分{final_total_from_index}<{SCORE_BUY_THRESHOLD}，展示防守ETF委托明细")
        else:
            content = f"**今日买入委托明细**\n"
            content += f"**时间**: {current_time}\n"
            content += f"**数量**: {stock_count} 只股票\n\n"
            content += f"**━━━━━━━━━━━━━━━**\n\n"
        
        # 解析委托明细（逐行容错：单行格式异常只跳过该行，不影响整条消息）
        detail_codes = []
        detail_lines = []
        for line in lines[2:]:  # 从第3行开始（跳过表头）
            line = line.strip()
            if not line:
                continue
            parts = line.split(',')
            if len(parts) == 4:
                detail_lines.append(parts)
                detail_codes.append(parts[0].strip())
        # 批量获取名称（一次请求，减少腾讯API调用）
        _batch_fetch_stock_names(detail_codes)

        for i, parts in enumerate(detail_lines, 1):
            code = parts[0].strip()
            try:
                open_price = float(parts[1].strip())
                shares = int(parts[2].strip())
                amount = float(parts[3].strip())
            except (ValueError, TypeError):
                logger.warning(f"[TRADE] 跳过格式异常行: {','.join(parts)}")
                continue
            
            # 获取股票名称（已批量预取，命中缓存）
            stock_name = get_stock_name(code)
            
            # 价格小数位：ETF（5开头）保留3位，个股保留2位
            price_decimals = 3 if code.startswith('5') else 2
            price_fmt = f".{price_decimals}f"
            
            # 格式化输出
            content += f"**{i}. {stock_name} ({code})**\n"
            content += f"   开盘价: ¥{open_price:{price_fmt}}\n"
            content += f"   股数: {shares:,} 股\n"
            content += f"   金额: ¥{amount:,.2f}\n\n"
        
        content += f"**━━━━━━━━━━━━━━━**\n"
        
        # 获取飞书通知器
        notifier = get_feishu_notifier()
        
        if not notifier.enabled:
            logger.warning("[WARN] 飞书通知未启用，跳过发送")
            return
        
        # 卡片颜色随评分动态：<4红、4-阈值橙、≥阈值绿（无评分保持绿色）
        # 语义：低分为防守ETF买入（橙/红提示谨慎），高分为股票池买入（绿）
        if final_total_from_index is not None:
            if final_total_from_index < 4:
                card_template = "red"
            elif final_total_from_index < SCORE_BUY_THRESHOLD:
                card_template = "orange"
            else:
                card_template = "green"
        else:
            card_template = "green"

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
                    "template": card_template
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


def _to_full_code(symbol: str) -> str:
    """
    股票代码转腾讯全代码（如 000526 → sz000526，513850 → sh513850）

    市场判断：
      - 6/9/5 开头 → sh（6=沪主板，9=沪B，5=沪市ETF）
      - 其余（0/1/2/3）→ sz
    """
    if symbol.startswith(('6', '9', '5')):
        return f"sh{symbol}"
    return f"sz{symbol}"


def _batch_fetch_stock_names(codes: list):
    """
    批量获取股票名称（腾讯API支持逗号分隔多只，每批最多50只）

    结果写入模块级 _stock_name_cache，供 get_stock_name 复用。
    """
    if not codes:
        return

    # 过滤已缓存的
    missing = [c for c in codes if c not in _stock_name_cache]
    if not missing:
        return

    try:
        for i in range(0, len(missing), 50):
            batch = missing[i:i + 50]
            full_codes = [_to_full_code(c) for c in batch]
            resp = requests.get(
                f"http://qt.gtimg.cn/q={','.join(full_codes)}",
                timeout=5
            )
            resp.encoding = 'gbk'
            # 响应格式: v_sh600000="1~浦发银行~600000~..."; v_sz000001="1~平安银行~..."
            for seg in resp.text.strip().split(';'):
                seg = seg.strip()
                if not seg or '=' not in seg:
                    continue
                var_part, _, val_part = seg.partition('=')
                # 从变量名提取代码: v_sh600000 → 600000
                raw = var_part.replace('v_', '').lstrip('sh').lstrip('sz')
                if not raw.isdigit():
                    continue
                name_parts = val_part.strip('"').split('~')
                if len(name_parts) >= 2 and name_parts[1]:
                    _stock_name_cache[raw] = name_parts[1]
    except Exception as e:
        logger.debug(f"批量获取股票名称失败: {e}")


def get_stock_name(symbol: str) -> str:
    """
    根据股票代码获取股票名称（使用腾讯财经API，带缓存）
    
    Args:
        symbol: 股票代码（不含市场前缀），如 '000526'
    
    Returns:
        str: 股票名称，获取失败则返回股票代码本身
    """
    # 命中缓存直接返回
    if symbol in _stock_name_cache:
        return _stock_name_cache[symbol]

    try:
        # 调用腾讯财经API
        url = f"http://qt.gtimg.cn/q={_to_full_code(symbol)}"
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
                        _stock_name_cache[symbol] = stock_name
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

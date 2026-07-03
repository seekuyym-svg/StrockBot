# -*- coding: utf-8 -*-
"""
牛股潜质分析工具

功能：
1. 读取指定日期的选股结果（已评分的TOP N只）
2. 计算每只入选股票的乖离率（close/MA20）
3. 统计过去N个交易日在选股池中出现的次数
4. 综合评估"牛股潜质"，按潜质排序输出

使用方法：
    python backtest/analyze_potential.py                          # 分析今天
    python backtest/analyze_potential.py --date 2026-07-01       # 指定日期
    python backtest/analyze_potential.py --top 15                # 显示前15只
    python backtest/analyze_potential.py --history 15            # 回溯过去15天

理论依据：
    通过回测数据发现，大牛股有两个显著特征：
    - 乖离率（close/MA20）在5%~15%之间，处于健康上升通道
    - 反复出现在选股池中（连续3次以上入选=趋势确认）
    这两个特征叠加时，股票后续继续大涨的概率很高。
"""

import sys
import argparse
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

DATA_DIR = project_root / "data"


# ──────────────────────────────────────────────
# 数据加载
# ──────────────────────────────────────────────

def load_raw_stocks(date_compact: str) -> Dict[str, Dict]:
    """
    从 .bak 文件加载原始选股数据（含 close, ma20 等）

    Returns:
        { '600397': { 'close': 16.69, 'ma20': 13.93, 'vol_ratio': 1.36, 'return_pct': 17.04 } }
    """
    # 优先从 .bak 读（包含完整的原始数据）
    bak_file = DATA_DIR / f"stockpool_{date_compact}.txt.bak"
    if not bak_file.exists():
        # 如果 .bak 不存在，尝试主文件（大文件才有原始数据）
        main_file = DATA_DIR / f"stockpool_{date_compact}.txt"
        if main_file.exists() and main_file.stat().st_size > 2000:
            bak_file = main_file
        else:
            return {}

    stocks = {}
    with open(bak_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('-') or line.startswith('code,'):
                continue
            parts = line.split(',')
            if len(parts) >= 4:
                code = parts[0].strip()
                try:
                    stocks[code] = {
                        'close': float(parts[1]),
                        'ma20': float(parts[2]),
                        'vol_ratio': float(parts[3]),
                        'return_pct': float(parts[4]) if len(parts) >= 5 else 0.0,
                    }
                except (ValueError, IndexError):
                    continue
    return stocks


def _find_scored_file(date_compact: str) -> Optional[Path]:
    """查找包含评分数据的 stockpool 文件（尝试多种命名变体）"""
    # 优先尝试标准文件名
    candidates = [
        DATA_DIR / f"stockpool_{date_compact}.txt",
    ]
    # 再尝试带收益率后缀的变体（如 stockpool_20260617.txt+3.75）
    for f in sorted(DATA_DIR.glob(f"stockpool_{date_compact}.txt*")):
        if f.suffix != '.bak':  # 跳过 .bak，它不含评分数据
            candidates.append(f)
    # 去重
    seen = set()
    unique = []
    for p in candidates:
        s = str(p)
        if s not in seen:
            seen.add(s)
            unique.append(p)
    for p in unique:
        if p.exists():
            # 确认文件确实包含评分数据（通过文件大小判断：含评分数据的文件通常较小）
            size = p.stat().st_size
            if size < 2000:  # 只含评分数据的文件通常很小（<2KB）
                return p
    # 如果小文件都不行，尝试最大但包含评分的文件
    for p in unique:
        if p.exists():
            content = p.read_text(encoding='utf-8', errors='ignore')
            if '=== 技术评分数据' in content:
                return p
    return None


def load_scored_list(date_compact: str) -> Dict[str, Dict]:
    """
    从评分后的文件加载已评分的股票列表

    Returns:
        { '600397': { 'score': 67, 'pref_score': 14.0, 'industry': '专用设备' or None } }
    """
    scored_file = _find_scored_file(date_compact)
    if scored_file is None:
        return {}

    scored = {}
    in_score_section = False
    format_has_industry = False

    with open(scored_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 检测格式：有行业列
            if line.startswith('# 格式:') and '所属行业' in line:
                format_has_industry = True
                continue
            if line.startswith('# === 技术评分数据'):
                in_score_section = True
                continue
            if not in_score_section:
                continue
            if line.startswith('#') or line.startswith('-') or line == '':
                continue

            parts = line.split(',')
            if len(parts) >= 3:
                code = parts[0].strip()
                try:
                    industry = parts[4].strip() if format_has_industry and len(parts) >= 5 else None
                    scored[code] = {
                        'score': float(parts[1]),
                        'pref_score': float(parts[2]),
                        'industry': industry,
                    }
                except (ValueError, IndexError):
                    continue

    return scored


# ──────────────────────────────────────────────
# 股票名称 & 行业信息获取
# ──────────────────────────────────────────────

# 缓存（避免重复请求）
_name_cache: Dict[str, str] = {}
_industry_cache: Dict[str, str] = {}


def _fetch_stock_info(code: str) -> Tuple[Optional[str], Optional[str]]:
    """
    通过东方财富公司概况接口获取股票名称(agjc)和行业(sshy)

    一次请求同时返回名称（A股简称）和行业，避免重复调用
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'http://quote.eastmoney.com/'
    }

    name = None
    industry = None
    market_code = 'SZ' if code.startswith(('0', '3')) else 'SH'

    try:
        time.sleep(0.25)  # 防封
        resp = requests.get(
            "http://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax",
            params={"code": f"{market_code}{code}"},
            headers=headers, timeout=10
        )
        data = resp.json()
        jbzl = data.get('jbzl')
        if jbzl:
            name = str(jbzl.get('agjc', '')) or None
            industry = str(jbzl.get('sshy', '')) or None
    except Exception:
        pass

    return name, industry


def get_stock_name(code: str) -> str:
    """获取股票名称（带缓存）"""
    if code in _name_cache:
        return _name_cache[code]
    name, industry = _fetch_stock_info(code)
    _name_cache[code] = name or ''
    if industry:
        _industry_cache[code] = industry
    return _name_cache[code]


def get_industry(code: str) -> str:
    """获取行业（带缓存）"""
    if code in _industry_cache:
        return _industry_cache[code]
    name, industry = _fetch_stock_info(code)
    if name:
        _name_cache[code] = name
    _industry_cache[code] = industry or ''
    return _industry_cache[code]


# ──────────────────────────────────────────────
# 历史出现次数统计
# ──────────────────────────────────────────────

def _get_stockpool_path(date_compact: str) -> Optional[Path]:
    """查找某一天的选股文件（尝试多种命名变体）"""
    # 优先顺序：.bak > 主文件 > 带后缀的变体
    p = DATA_DIR / f"stockpool_{date_compact}.txt.bak"
    if p.exists():
        return p
    p = DATA_DIR / f"stockpool_{date_compact}.txt"
    if p.exists():
        return p
    # 遍历匹配 stockpool_YYYYMMDD.txt* 的文件
    matches = sorted(DATA_DIR.glob(f"stockpool_{date_compact}.txt*"))
    if matches:
        return matches[0]
    return None


def count_historical_appearances(code: str, analysis_date: str, lookback: int = 10) -> int:
    """
    统计股票在历史N个交易日中出现在选股池的次数

    Args:
        code: 6位股票代码
        analysis_date: 分析日期 YYYY-MM-DD
        lookback: 回溯多少个交易日

    Returns:
        出现次数
    """
    count = 0
    check_dt = datetime.strptime(analysis_date, '%Y-%m-%d')
    found_trading_days = 0

    for days_ago in range(1, lookback * 3):  # 预留非交易日
        if found_trading_days >= lookback:
            break

        past_dt = check_dt - timedelta(days=days_ago)
        past_str = past_dt.strftime('%Y%m%d')

        pool_path = _get_stockpool_path(past_str)
        if pool_path is None:
            continue

        found_trading_days += 1

        # 检查代码是否在文件中（精确匹配行首）
        try:
            content = pool_path.read_text(encoding='utf-8', errors='ignore')
            if f'\n{code},' in content or content.startswith(f'{code},'):
                count += 1
        except Exception:
            continue

    return count


# ──────────────────────────────────────────────
# 潜质评分计算
# ──────────────────────────────────────────────

def calc_potential(deviation: float, history_count: int) -> Tuple[float, float, float]:
    """
    计算潜质评分

    Args:
        deviation: 乖离率（%），如 12.5 表示 +12.5%
        history_count: 历史出现次数

    Returns:
        (乖离率得分, 历史次数得分, 总分)
        各满分10分，总分最高20分
    """
    # ── 乖离率评分（0~10分）──
    if 8 <= deviation <= 12:
        dev_score = 10.0    # ✅ 最佳区间：最健康的上升通道
    elif 5 <= deviation < 8:
        dev_score = 8.0     # 刚起步，趋势确认中
    elif 12 < deviation <= 15:
        dev_score = 8.0     # 偏高但仍有空间
    elif 3 <= deviation < 5:
        dev_score = 6.0     # 放宽边界，接近启动
    elif 15 < deviation <= 20:
        dev_score = 4.0     # 偏高，风险增大
    elif 0 <= deviation < 3:
        dev_score = 2.0     # 还没启动
    else:
        dev_score = 0.0     # 跌破MA20或严重过热

    # ── 历史出现次数评分（0~10分）──
    if history_count >= 6:
        hist_score = 10.0
    elif history_count >= 4:
        hist_score = 8.0
    elif history_count >= 3:
        hist_score = 7.0     # 3次=趋势确认，权重提高1分
    elif history_count >= 2:
        hist_score = 4.0
    elif history_count >= 1:
        hist_score = 2.0
    else:
        hist_score = 0.0

    return dev_score, hist_score, dev_score + hist_score


def format_star(total: float) -> str:
    """总分转星级"""
    if total >= 17:
        return '⭐⭐⭐⭐⭐'
    elif total >= 13:
        return '⭐⭐⭐⭐'
    elif total >= 9:
        return '⭐⭐⭐'
    elif total >= 5:
        return '⭐⭐'
    else:
        return '⭐'


# ──────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='牛股潜质分析工具 - 乖离率 + 历史出现次数 综合评估',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python backtest/analyze_potential.py                            # 分析今天
  python backtest/analyze_potential.py --date 2026-07-01         # 指定日期
  python backtest/analyze_potential.py --top 15                  # 显示前15只
  python backtest/analyze_potential.py --history 15              # 回溯过去15天
  python backtest/analyze_potential.py --min-score 65            # 只显示评分>=65的
        """
    )
    parser.add_argument('--date', type=str, help='分析日期 (YYYY-MM-DD)，默认今天')
    parser.add_argument('--top', type=int, default=20, help='最多显示几只（默认20）')
    parser.add_argument('--history', type=int, default=10, help='历史回溯天数（默认10个交易日）')
    parser.add_argument('--min-score', type=float, default=0, help='最低综合评分过滤（默认0=不限）')
    parser.add_argument('--no-fetch', action='store_true', help='不联网获取行业信息（加速）')

    args = parser.parse_args()
    analysis_date = args.date or datetime.now().strftime('%Y-%m-%d')
    date_compact = analysis_date.replace('-', '')
    lookback = args.history
    top_n = args.top
    min_score = args.min_score

    print()
    print("=" * 82)
    print(f"  🐂  牛股潜质分析 — {analysis_date}")
    print(f"     回溯周期: 过去{lookback}个交易日  |  乖离率基准: MA20  |  共展示前{top_n}只")
    print("=" * 82)

    # ── Step 1: 加载原始数据 ──
    raw = load_raw_stocks(date_compact)
    if not raw:
        print(f"\n  ❌ 未找到 {analysis_date} 的原始选股文件 (.bak)")
        print(f"     请先运行选股: python backtest/generate_stockpool.py --date {analysis_date}")
        return
    print(f"\n  📂 原始选股池: {len(raw)} 只")

    # ── Step 2: 加载评分列表 ──
    scored = load_scored_list(date_compact)
    if not scored:
        print(f"  ⚠  未找到评分数据，将分析全部{len(raw)}只股票（数据量较大）")
        # 使用全部原始数据
        work = {}
        for code, info in raw.items():
            work[code] = {
                'close': info['close'],
                'ma20': info['ma20'],
                'score': 0,
                'pref_score': 0,
                'industry': None,
            }
    else:
        # 只分析已评分的股票，并与原始数据合并（获取close, ma20）
        work = {}
        for code, sinfo in scored.items():
            if code in raw:
                rinfo = raw[code]
                work[code] = {
                    'close': rinfo['close'],
                    'ma20': rinfo['ma20'],
                    'score': sinfo['score'],
                    'pref_score': sinfo['pref_score'],
                    'industry': sinfo.get('industry'),
                }
        print(f"  📋 已评分股票: {len(scored)} 只", end='')
        if min_score > 0:
            work = {k: v for k, v in work.items() if v['score'] >= min_score}
            print(f"  (综合评分 ≥ {min_score:.0f} → {len(work)} 只)")
        else:
            print()

    if not work:
        print(f"\n  ❌ 无匹配的股票数据")
        return

    print(f"  {'─' * 80}")

    # ── Step 3: 逐只计算潜质 ──
    results = []
    fetch_count = 0

    for idx, (code, info) in enumerate(work.items(), 1):
        close = info['close']
        ma20 = info['ma20']
        deviation = ((close - ma20) / ma20 * 100) if ma20 > 0 else 0.0
        history_count = count_historical_appearances(code, analysis_date, lookback)
        dev_score, hist_score, total = calc_potential(deviation, history_count)

        # 获取名称和行业（优先从缓存/文件获取，没有则HTTP获取）
        industry = info.get('industry')
        name = '' if args.no_fetch else get_stock_name(code)
        if not industry and not args.no_fetch and fetch_count < 30:
            industry = get_industry(code)
            fetch_count += 1

        results.append({
            'code': code,
            'name': name,
            'close': close,
            'ma20': ma20,
            'deviation': deviation,
            'history_count': history_count,
            'score': info['score'],
            'pref_score': info['pref_score'],
            'dev_score': dev_score,
            'hist_score': hist_score,
            'total': total,
            'industry': industry or '',
        })

        # 进度提示（每50只）
        if idx % 50 == 0:
            cols = 50 * '█' if idx // 50 >= 1 else ''
            print(f"     ⏳ 分析中: {idx}/{len(work)}  {cols}", end='\r')

    print(f"     ✅ 分析完成: {len(results)} 只股票{'  ' * 10}")

    # ── Step 4: 排序输出 ──
    results.sort(key=lambda x: x['total'], reverse=True)
    # 过滤规则：只显示潜质≥13分（4⭐以上）且乖离率3%~20%的健康区间
    display = [r for r in results if r['total'] >= 13 and 3 <= r['deviation'] <= 20]
    if not display:
        print(f"\n  📭 当前无满足条件的股票（潜质≥13分 + 乖离率3~20%）")
        print(f"  {'─' * 84}")
        print()
        print("=" * 82)
        return

    print()
    # 表头
    header = (
        f"  {'排名':>3}  "
        f"{'代码':>6}  "
        f"{'名称':<8}  "
        f"{'综合评分':>6}  "
        f"{'乖离率':>7}  "
        f"{'历史次数':>6}  "
        f"{'潜质':>6}  "
        f"{'评级':<10}  "
        f"{'行业':<12}"
    )
    print(header)
    print(f"  {'─' * 84}")

    for i, r in enumerate(display, 1):
        star = format_star(r['total'])
        score_str = '%s' % (f"{r['score']:.0f}" if r['score'] > 0 else '-')
        name_str = r['name'][:7] if r['name'] else '--'
        industry_str = r['industry'][:10] if r['industry'] else '--'

        line = (
            f"  {i:>3}  "
            f"{r['code']:>6}  "
            f"{name_str:<8}  "
            f"{score_str:>6}  "
            f"{r['deviation']:+6.1f}%  "
            f"{r['history_count']:>4}次  "
            f"{r['total']:>5.1f}  "
            f"{star:<10}  "
            f"{industry_str:<12}"
        )
        print(line)

    print(f"  {'─' * 76}")

    # ── Step 5: 统计汇总（基于当前显示的过滤结果）──
    high = sum(1 for r in display if r['total'] >= 13)   # 4⭐+
    mid = sum(1 for r in display if 9 <= r['total'] < 13)  # 3⭐
    low = sum(1 for r in display if r['total'] < 9)

    print(f"\n  📊 本次展示:  高潜质(4⭐+) {high}只  |  中潜质(3⭐) {mid}只  |  一般 {low}只")
    print(f"     （过滤条件：潜质≥13分 且 乖离率3%~20%，全部已评分{len(results)}只中选出{len(display)}只）")
    if high > 0:
        print(f"\n  💡 以上股票兼具「乖离率健康(5~15%) + 反复入选(趋势确认)」特征")
        print(f"     可考虑在原有2天持有期基础上多拿几天，让利润奔跑")
    print()
    print("=" * 82)
    print()


if __name__ == "__main__":
    main()

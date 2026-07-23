# -*- coding: utf-8 -*-
"""
查看评分后的股票池结果

功能：
1. 读取评分后的股票池文件
2. 显示Top N股票的代码、名称、评分和评级
3. 批量获取股票基本信息

使用方法:
    python backtest/view_scored_results.py --date 2026-04-13
    python backtest/view_scored_results.py --date 2026-04-13 --top 5
"""

import sys
import json
from pathlib import Path
from datetime import datetime
import pandas as pd

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def load_scored_stockpool(date_str: str) -> list:
    """
    加载评分后的股票池文件
    
    Args:
        date_str: 日期字符串 (YYYY-MM-DD 或 YYYYMMDD)
    
    Returns:
        list: [(股票代码, 评分), ...]
    """
    # 标准化日期格式
    if '-' in date_str:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        filename = f"stockpool_{dt.strftime('%Y%m%d')}.txt"
    else:
        filename = f"stockpool_{date_str}.txt"
    
    filepath = project_root / "data" / filename
    
    if not filepath.exists():
        print(f"[ERROR] 文件不存在: {filepath}")
        return []
    
    # 两阶段读取:
    # 阶段1: 收集所有股票代码（评分区前的纯代码行）
    # 阶段2: 从评分区提取有评分的覆盖上去
    all_codes = {}       # code -> score (None 表示无评分)
    in_score_section = False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # 检测评分数据区域
            if line.startswith('# === 技术评分数据'):
                in_score_section = True
                continue
            
            # 跳过注释行和空行
            if not line or line.startswith('#') or line.startswith('-'):
                continue
            
            if not in_score_section:
                # 阶段1: 收集股票代码
                if ',' not in line:
                    # 纯代码行（旧格式单列）
                    all_codes[line] = None
                elif line.startswith('code,'):
                    # CSV 表头行（code,close,ma20,...）跳过
                    continue
                else:
                    # CSV 数据行（000034,29.62,26.84,...）取第一列作为代码
                    code = line.split(',')[0].strip()
                    if code.isdigit() and len(code) == 6:
                        all_codes[code] = None
            else:
                # 阶段2: 评分数据 code,score
                if ',' in line:
                    parts = line.split(',')
                    code = parts[0].strip()
                    try:
                        score = float(parts[1].strip())
                        all_codes[code] = score
                    except ValueError:
                        if code not in all_codes:
                            all_codes[code] = None
    
    # 转为列表
    scored_stocks = [(code, score) for code, score in all_codes.items()]
    # 有评分的按评分降序，无评分的排在最后
    scored_stocks.sort(key=lambda x: (x[1] is None, -(x[1] or 0)), reverse=False)
    
    has_score = sum(1 for _, s in scored_stocks if s is not None)
    print(f"[OK] 加载 {filename}，共 {len(scored_stocks)} 只股票（其中 {has_score} 只有评分）")
    return scored_stocks


# 模块级缓存：同一只股票的东方财富公司概况只请求一次
_company_cache = {}
# 文件级缓存：从 industry_cache.json 读取已有行业数据
_file_cache = None

def _code_to_cache_key(code: str) -> str:
    """6位代码转 industry_cache.json 的 key（如 sz.000034）"""
    market = 'sh' if code.startswith('6') or code.startswith('9') else 'sz'
    return f"{market}.{code}"

def _ensure_file_cache():
    """懒加载 industry_cache.json 到内存"""
    global _file_cache
    if _file_cache is not None:
        return
    _file_cache = {}
    cache_path = project_root / "data" / "industry_cache.json"
    try:
        if cache_path.exists():
            with open(cache_path, 'r', encoding='utf-8') as f:
                _file_cache.update(json.load(f))
    except Exception:
        pass

def _save_file_cache():
    """将新增/更新的行业数据写回 industry_cache.json"""
    # 防写入空/过小数据破坏缓存文件
    if not _file_cache or len(_file_cache) < 10:
        return
    cache_path = project_root / "data" / "industry_cache.json"
    try:
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(_file_cache, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _fetch_company_info(code: str) -> dict:
    """
    从东方财富获取公司基本信息（行业 + 主营业务，带缓存）
    
    优先级：
      行业：industry_cache.json 文件缓存 → 东方财富API → akshare
      主营业务：东方财富API → 新浪财经F10
    
    Args:
        code: 6位股票代码
    
    Returns:
        dict: {'industry': str, 'business': str}
    """
    if code in _company_cache:
        return _company_cache[code]
    
    _ensure_file_cache()
    cache_key = _code_to_cache_key(code)
    
    result = {'industry': '未知', 'business': ''}
    
    # === 方案0：先从行业缓存文件取行业（避免请求）===
    if cache_key in _file_cache:
        result['industry'] = _file_cache[cache_key]
    
    # === 方案1：东方财富HTTP接口（获取行业 + 主营业务）===
    try:
        import time
        import requests as req
        
        market_code = 'SZ' if not code.startswith('6') else 'SH'
        url = "http://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/CompanySurveyAjax"
        params = {"code": f"{market_code}{code}"}
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'http://quote.eastmoney.com/'
        }
        
        time.sleep(0.3)
        response = req.get(url, params=params, headers=headers, timeout=5)
        data = response.json()
        
        if data.get('jbzl'):
            jbzl = data['jbzl']
            if jbzl.get('sshy'):
                result['industry'] = str(jbzl['sshy'])
            # 优先公司简介(gsjj, 最直观了解企业业务)，
            # 降级到经营范围(jyfw, 注册的经营范围)
            if jbzl.get('gsjj'):
                result['business'] = str(jbzl['gsjj']).strip()
            elif jbzl.get('jyfw'):
                result['business'] = str(jbzl['jyfw']).strip()
    except Exception:
        pass
    
    # === 方案2：akshare 降级（仅补行业，无主营业务）===
    if result['industry'] == '未知':
        try:
            import akshare as ak
            info = ak.stock_individual_info_em(symbol=code)
            if info is not None and not info.empty:
                row = info[info['item'] == '行业']
                if not row.empty:
                    result['industry'] = row['value'].iloc[0]
        except Exception:
            pass
    
    # === 方案3：新浪财经F10降级（补主营业务）===
    if not result['business']:
        result['business'] = _fetch_business_via_sina(code)
    
    # 将新获取的行业数据写回文件缓存
    if result['industry'] not in ('未知', '') and cache_key not in _file_cache:
        _file_cache[cache_key] = result['industry']
        _save_file_cache()
    
    _company_cache[code] = result
    return result


def _fetch_business_via_sina(code: str) -> str:
    """
    降级方案：从新浪财经公司概况页获取主营业务描述
    
    解析 https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/{code}.phtml
    页面中的"公司简介"或"主营业务"表格行
    
    Args:
        code: 6位股票代码
    
    Returns:
        str: 主营业务描述，失败返回空字符串
    """
    import re
    
    try:
        import requests as req
        
        url = f"https://vip.stock.finance.sina.com.cn/corp/go.php/vCI_CorpInfo/stockid/{code}.phtml"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        }
        
        resp = req.get(url, headers=headers, timeout=8)
        resp.encoding = 'gbk'
        html = resp.text
        
        # 新浪F10页面典型结构:
        #   <td>主营业务</td><td>IT产品及渠道销售</td>
        #   <td>公司简介：</td><td>...</td>
        patterns = [
            # 主营业务: 后面紧跟的td内容
            r'主营业务[：:]?\s*</td>\s*<td[^>]*>([^<]+)',
            # 公司简介: 后面紧跟的td内容
            r'公司简介[：:]?\s*</td>\s*<td[^>]*>([^<]+)',
            # 宽松版：经营范围 + td
            r'经营范围[^<]*<td[^>]*>([^<]+)',
            # 主营范围 + td
            r'主营范围[^<]*<td[^>]*>([^<]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                text = match.group(1).strip()
                # 清理多余空白
                text = re.sub(r'\s+', '', text)
                if len(text) > 5:
                    return text
    except Exception:
        pass
    
    return ''


def _get_industry(code: str) -> str:
    """获取股票所属行业（基于东方财富公司概况缓存）"""
    return _fetch_company_info(code)['industry']


def _get_business_scope(code: str) -> str:
    """
    获取股票主营业务描述（公司简介/经营范围）
    
    数据源：东方财富公司概况接口 jbzl.gsjj(公司简介) → jbzl.jyfw(经营范围)
    降级：新浪财经F10页面
    
    Args:
        code: 6位股票代码
    
    Returns:
        str: 主营业务描述，获取失败返回空字符串
    """
    return _fetch_company_info(code)['business']


def get_stock_info_batch(scored_stocks: list, top_n: int = None) -> pd.DataFrame:
    """
    批量获取股票基本信息
    
    Args:
        scored_stocks: [(股票代码, 评分), ...]
        top_n: 只显示前N只（用于快速预览）
    
    Returns:
        DataFrame: 包含代码、名称、行业、评分、评级等信息
    """
    try:
        from local.utils import get_stock_name
        
        # 如果指定了top_n，只处理前N只
        if top_n:
            display_stocks = scored_stocks[:top_n]
            print(f"[INFO] 仅显示前 {top_n} 只股票（共 {len(scored_stocks)} 只）\n")
        else:
            display_stocks = scored_stocks
            print(f"[INFO] 显示全部 {len(scored_stocks)} 只股票\n")
        
        results = []
        for idx, (code, score) in enumerate(display_stocks, 1):
            try:
                # 使用腾讯财经API获取名称（比akshare更稳定）
                name = get_stock_name(code)
                if name == code:
                    name = '获取失败'
                
                # 使用东方财富HTTP接口获取行业（多方案降级）
                industry = _get_industry(code)
                
                # 获取主营业务（同一笔API请求，零额外开销）
                business = _get_business_scope(code)
                
                # 计算评级（无评分时显示 --）
                if score is None:
                    display_score = '--'
                    rating = '--'
                elif score >= 80:
                    display_score = score
                    rating = "⭐⭐⭐⭐⭐ 优秀"
                elif score >= 60:
                    display_score = score
                    rating = "⭐⭐⭐⭐ 良好"
                elif score >= 40:
                    display_score = score
                    rating = "⭐⭐⭐ 中等"
                elif score >= 20:
                    display_score = score
                    rating = "⭐⭐ 较差"
                else:
                    display_score = score
                    rating = "⭐ 很差"
                
                results.append({
                    '序号': idx,
                    '代码': code,
                    '名称': name,
                    '行业': industry,
                    '评分': display_score,
                    '评级': rating,
                    '主营业务': business
                })
                
                # 进度提示
                if idx % 10 == 0:
                    print(f"[PROGRESS] 已处理 {idx}/{len(display_stocks)} 只股票...")
                
            except Exception as e:
                display_score = '--' if score is None else score
                results.append({
                    '序号': idx,
                    '代码': code,
                    '名称': '获取失败',
                    '行业': '未知',
                    '评分': display_score,
                    '评级': '获取失败',
                    '主营业务': ''
                })
        
        return pd.DataFrame(results)
        
    except ImportError as e:
        print(f"[ERROR] 导入模块失败: {e}")
        return pd.DataFrame()


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="查看评分后的股票池结果")
    parser.add_argument('--date', type=str, required=True, help='日期 (YYYY-MM-DD 或 YYYYMMDD)')
    parser.add_argument('--top', type=int, default=None, help='只显示前N只股票（用于快速预览）')
    
    args = parser.parse_args()
    
    print("=" * 100)
    print(f"[INFO] 评分结果查看工具")
    print(f"[INFO] 日期: {args.date}")
    print("=" * 100)
    
    # 1. 加载评分后的股票池
    scored_stocks = load_scored_stockpool(args.date)
    
    if not scored_stocks:
        print("[WARN] 未找到评分数据")
        return
    
    # 2. 获取股票信息
    print("\n[STEP 2] 正在获取股票基本信息...\n")
    df = get_stock_info_batch(scored_stocks, top_n=args.top)
    
    if df.empty:
        print("[ERROR] 无法获取股票信息")
        return
    
    # 3. 显示结果
    print("\n" + "=" * 100)
    print("评分结果详情（按评分降序排列）")
    print("=" * 100)
    
    # 设置pandas显示选项
    pd.set_option('display.max_rows', None)
    pd.set_option('display.width', None)
    pd.set_option('display.max_colwidth', 60)
    pd.set_option('display.unicode.ambiguous_as_wide', True)
    pd.set_option('display.unicode.east_asian_width', True)
    
    # 表格中隐藏主营业务列（太长影响阅读，详情统一放在后面）
    display_df = df.copy()
    if '主营业务' in display_df.columns:
        display_df = display_df.drop(columns=['主营业务'])
    
    print(display_df.to_string(index=False))
    
    # 打印主营业务详情（截取最多100字，保持简洁）
    has_business = df['主营业务'].str.len().sum() > 0 if '主营业务' in df.columns else False
    if has_business:
        print("\n📋 主营业务详情：")
        for _, row in df.iterrows():
            biz = row.get('主营业务', '')
            if biz:
                short_biz = biz[:100] + '..' if len(biz) > 100 else biz
                print(f"  [{row['代码']}] {row['名称']}: {short_biz}")
    
    # 4. 统计信息（仅对有评分的数据计算）
    print("\n" + "=" * 100)
    print("统计摘要")
    print("=" * 100)
    
    # 过滤出有评分的行做数值统计
    score_df = df[pd.to_numeric(df['评分'], errors='coerce').notna()]
    score_col = pd.to_numeric(score_df['评分'], errors='coerce')
    
    if not score_col.empty:
        best = score_col.max()
        worst = score_col.min()
        print(f"最高评分: {best:.1f} 分 ({score_df.loc[score_col.idxmax(), '名称']})")
        print(f"最低评分: {worst:.1f} 分 ({score_df.loc[score_col.idxmin(), '名称']})")
        print(f"平均评分: {score_col.mean():.1f} 分")
        print(f"中位数:   {score_col.median():.1f} 分")
    else:
        print("（暂无评分数据）")
    
    # 评级分布（含无评分）
    rating_counts = df['评级'].value_counts()
    print(f"\n评级分布:")
    for rating, count in rating_counts.items():
        print(f"  {rating}: {count} 只")
    print(f"  总计: {len(df)} 只")
    
    print("=" * 100)


if __name__ == "__main__":
    main()

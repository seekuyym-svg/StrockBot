# -*- coding: utf-8 -*-
"""
计算ETF与上证指数相关系数

功能说明：
1. 获取指定ETF的历史K线数据（121天）
2. 获取上证指数的历史K线数据（121天）
3. 计算日对数收益率
4. 计算皮尔逊相关系数（整体和滚动窗口）
5. 输出分析结果

使用方法：
    python calculate_correlation.py
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
from loguru import logger


class CorrelationCalculator:
    """相关系数计算器"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
    
    def get_etf_klines(self, code: str, days: int = 121) -> pd.DataFrame:
        """
        从腾讯财经获取ETF历史K线数据
        
        Args:
            code: ETF代码（如 513120, 513050）
            days: 获取天数
            
        Returns:
            DataFrame包含日期、收盘价等字段
        """
        try:
            url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                "param": f"sh{code},day,,,{days},qfq"
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('code') == 0 and result.get('data'):
                stock_data = result['data'].get(f'sh{code}', {})
                klines = stock_data.get('qfqday', []) or stock_data.get('day', [])
                
                if klines:
                    records = []
                    for line in klines:
                        if len(line) >= 6:
                            records.append({
                                'date': line[0],
                                'close': float(line[2]),  # 收盘价
                                'open': float(line[1]),
                                'high': float(line[3]),
                                'low': float(line[4]),
                                'volume': float(line[5]) * 100,
                            })
                    
                    df = pd.DataFrame(records)
                    if not df.empty:
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.sort_values('date').reset_index(drop=True)
                        logger.info(f"✓ 成功获取 {code} 历史K线：{len(df)}条")
                        return df
            
            logger.error(f"✗ 获取 {code} 数据失败")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"✗ 获取 {code} 数据异常: {e}")
            return pd.DataFrame()
    
    def get_sh_index_klines(self, days: int = 121) -> pd.DataFrame:
        """
        获取上证指数（000001.SS）历史K线数据
        
        Args:
            days: 获取天数
            
        Returns:
            DataFrame包含日期、收盘价等字段
        """
        try:
            # 上证指数代码：1.000001（腾讯财经格式）
            url = "http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            params = {
                "param": f"sh000001,day,,,{days},qfq"
            }
            
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('code') == 0 and result.get('data'):
                index_data = result['data'].get('sh000001', {})
                klines = index_data.get('qfqday', []) or index_data.get('day', [])
                
                if klines:
                    records = []
                    for line in klines:
                        if len(line) >= 6:
                            records.append({
                                'date': line[0],
                                'close': float(line[2]),  # 收盘价
                                'open': float(line[1]),
                                'high': float(line[3]),
                                'low': float(line[4]),
                                'volume': float(line[5]) * 100,
                            })
                    
                    df = pd.DataFrame(records)
                    if not df.empty:
                        df['date'] = pd.to_datetime(df['date'])
                        df = df.sort_values('date').reset_index(drop=True)
                        logger.info(f"✓ 成功获取上证指数历史K线：{len(df)}条")
                        return df
            
            logger.error("✗ 获取上证指数数据失败")
            return pd.DataFrame()
            
        except Exception as e:
            logger.error(f"✗ 获取上证指数数据异常: {e}")
            return pd.DataFrame()
    
    def calculate_log_returns(self, df: pd.DataFrame, price_col: str = 'close') -> pd.Series:
        """
        计算对数收益率
        
        Args:
            df: 包含价格数据的DataFrame
            price_col: 价格列名
            
        Returns:
            对数收益率序列
        """
        returns = np.log(df[price_col] / df[price_col].shift(1))
        return returns
    
    def align_data(self, etf_df: pd.DataFrame, index_df: pd.DataFrame) -> pd.DataFrame:
        """
        对齐ETF和指数的日期
        
        Args:
            etf_df: ETF数据
            index_df: 指数数据
            
        Returns:
            对齐后的合并DataFrame
        """
        # 合并数据，以日期为键
        merged = pd.merge(etf_df[['date', 'close']], 
                         index_df[['date', 'close']], 
                         on='date', 
                         how='inner',
                         suffixes=('_etf', '_index'))
        
        merged = merged.sort_values('date').reset_index(drop=True)
        
        logger.info(f"✓ 对齐后有效交易日：{len(merged)}天")
        
        return merged
    
    def calculate_correlation(self, merged_df: pd.DataFrame, window: int = None) -> dict:
        """
        计算相关系数
        
        Args:
            merged_df: 对齐后的数据
            window: 滚动窗口大小（None表示计算整体相关性）
            
        Returns:
            包含相关系数的字典
        """
        # 计算对数收益率
        merged_df['ret_etf'] = self.calculate_log_returns(merged_df, 'close_etf')
        merged_df['ret_index'] = self.calculate_log_returns(merged_df, 'close_index')
        
        # 删除缺失值（第一天的收益率为NaN）
        merged_df = merged_df.dropna().reset_index(drop=True)
        
        result = {}
        
        if window is None:
            # 计算整体相关性
            corr = merged_df['ret_etf'].corr(merged_df['ret_index'])
            result['overall_correlation'] = corr
            logger.info(f"\n{'='*60}")
            logger.info(f"整体相关系数（全部{len(merged_df)}个交易日）")
            logger.info(f"{'='*60}")
            logger.info(f"相关系数 r = {corr:.4f}")
            self._interpret_correlation(corr)
        else:
            # 计算滚动相关性
            if len(merged_df) < window:
                logger.warning(f"⚠ 数据量不足{window}天，无法计算滚动相关性")
                return result
            
            merged_df[f'corr_{window}d'] = merged_df['ret_etf'].rolling(window).corr(merged_df['ret_index'])
            result['rolling_correlation'] = merged_df[[f'date', f'corr_{window}d']].dropna()
            
            latest_corr = result['rolling_correlation'][f'corr_{window}d'].iloc[-1]
            logger.info(f"\n{'='*60}")
            logger.info(f"{window}日滚动相关系数（最新）")
            logger.info(f"{'='*60}")
            logger.info(f"相关系数 r = {latest_corr:.4f}")
            self._interpret_correlation(latest_corr)
            
            # 统计信息
            rolling_series = result['rolling_correlation'][f'corr_{window}d']
            logger.info(f"\n滚动相关性统计：")
            logger.info(f"  均值: {rolling_series.mean():.4f}")
            logger.info(f"  标准差: {rolling_series.std():.4f}")
            logger.info(f"  最大值: {rolling_series.max():.4f}")
            logger.info(f"  最小值: {rolling_series.min():.4f}")
            logger.info(f"  当前值: {latest_corr:.4f}")
        
        return result
    
    def _interpret_correlation(self, corr: float):
        """解读相关系数"""
        if corr > 0.7:
            interpretation = "高度正相关（强β股，紧密跟随大盘）"
            emoji = "🔴"
        elif corr > 0.3:
            interpretation = "中度正相关（大部分个股的正常水平）"
            emoji = "🟡"
        elif corr > -0.3:
            interpretation = "弱相关或无关（独立走势）"
            emoji = "⚪"
        elif corr > -0.7:
            interpretation = "中度负相关（较少见）"
            emoji = "🔵"
        else:
            interpretation = "高度负相关（罕见）"
            emoji = "🔵"
        
        logger.info(f"解读: {emoji} {interpretation}")
    
    def analyze_etf(self, etf_code: str, etf_name: str, days: int = 121):
        """
        分析单个ETF与上证指数的相关性
        
        Args:
            etf_code: ETF代码（不含市场前缀，如 513120）
            etf_name: ETF名称
            days: 历史天数
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"开始分析: {etf_name} ({etf_code})")
        logger.info(f"{'='*60}")
        
        # 获取数据
        etf_df = self.get_etf_klines(etf_code, days)
        if etf_df.empty:
            logger.error(f"✗ 无法获取 {etf_code} 数据，跳过")
            return None
        
        index_df = self.get_sh_index_klines(days)
        if index_df.empty:
            logger.error("✗ 无法获取上证指数数据，跳过")
            return None
        
        # 对齐数据
        merged_df = self.align_data(etf_df, index_df)
        if merged_df.empty:
            logger.error("✗ 数据对齐失败")
            return None
        
        # 计算整体相关性
        overall_result = self.calculate_correlation(merged_df, window=None)
        
        # 计算滚动相关性（60日、120日）
        rolling_60d = self.calculate_correlation(merged_df.copy(), window=60)
        rolling_120d = self.calculate_correlation(merged_df.copy(), window=120)
        
        # 返回完整结果
        return {
            'etf_code': etf_code,
            'etf_name': etf_name,
            'overall_correlation': overall_result.get('overall_correlation'),
            'rolling_60d': rolling_60d.get('rolling_correlation'),
            'rolling_120d': rolling_120d.get('rolling_correlation'),
            'data_points': len(merged_df),
        }
    
    def generate_report(self, results: list):
        """生成分析报告"""
        logger.info(f"\n\n{'='*60}")
        logger.info(f"📊 相关系数分析报告")
        logger.info(f"{'='*60}\n")
        
        for result in results:
            if result is None:
                continue
            
            etf_name = result['etf_name']
            etf_code = result['etf_code']
            overall_corr = result['overall_correlation']
            
            logger.info(f"📌 {etf_name} ({etf_code})")
            logger.info(f"   数据点数: {result['data_points']}个交易日")
            logger.info(f"   整体相关系数: {overall_corr:.4f}")
            
            # 解读
            if overall_corr > 0.7:
                level = "高度正相关 🔴"
            elif overall_corr > 0.3:
                level = "中度正相关 🟡"
            elif overall_corr > -0.3:
                level = "弱相关 ⚪"
            elif overall_corr > -0.7:
                level = "中度负相关 🔵"
            else:
                level = "高度负相关 🔵"
            
            logger.info(f"   相关程度: {level}")
            
            # 滚动相关性
            if result['rolling_60d'] is not None and not result['rolling_60d'].empty:
                latest_60d = result['rolling_60d']['corr_60d'].iloc[-1]
                logger.info(f"   60日滚动相关: {latest_60d:.4f}")
            
            if result['rolling_120d'] is not None and not result['rolling_120d'].empty:
                latest_120d = result['rolling_120d']['corr_120d'].iloc[-1]
                logger.info(f"   120日滚动相关: {latest_120d:.4f}")
            
            logger.info("")
        
        # 对比总结
        logger.info(f"{'='*60}")
        logger.info(f"💡 对比总结")
        logger.info(f"{'='*60}\n")
        
        valid_results = [r for r in results if r is not None]
        if len(valid_results) >= 2:
            corr_list = [(r['etf_name'], r['overall_correlation']) for r in valid_results]
            corr_list.sort(key=lambda x: x[1], reverse=True)
            
            logger.info("按相关系数从高到低排序：")
            for i, (name, corr) in enumerate(corr_list, 1):
                logger.info(f"  {i}. {name}: {corr:.4f}")
            
            logger.info(f"\n结论:")
            highest = corr_list[0]
            lowest = corr_list[-1]
            logger.info(f"  • {highest[0]} 与上证指数相关性最高（{highest[1]:.4f}）")
            logger.info(f"  • {lowest[0]} 与上证指数相关性最低（{lowest[1]:.4f}）")
            
            if highest[1] > 0.7 and lowest[1] < 0.3:
                logger.info(f"  • 两个ETF的相关性差异较大，适合分散配置")
            elif abs(highest[1] - lowest[1]) < 0.1:
                logger.info(f"  • 两个ETF的相关性接近，分散效果有限")
        
        logger.info(f"\n{'='*60}")


def main():
    """主函数"""
    logger.info("🚀 开始计算ETF与上证指数相关系数")
    logger.info(f"📅 分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建计算器实例
    calculator = CorrelationCalculator()
    
    # 定义要分析的ETF列表
    etfs = [
        {"code": "513120", "name": "港股创新药ETF"},
        {"code": "513050", "name": "中概互联网ETF"},
        {"code": "159949", "name": "创业板50ETF"}      
    ]
    
    # 分析每个ETF
    results = []
    for etf in etfs:
        result = calculator.analyze_etf(
            etf_code=etf["code"],
            etf_name=etf["name"],
            days=121
        )
        results.append(result)
    
    # 生成报告
    calculator.generate_report(results)
    
    logger.info("\n✅ 分析完成！")


if __name__ == "__main__":
    main()

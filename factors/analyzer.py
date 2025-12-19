# -*- coding: utf-8 -*-
"""
因子分析模块
============
负责因子的IC分析、RankIC分析、分组回测等
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple, Union
from scipy import stats
from scipy.stats import spearmanr, pearsonr

from .config import FACTOR_CONFIGS, get_factor_directions, RANKICIR_CONFIG

logger = logging.getLogger(__name__)

# Constants for magic numbers
MIN_SAMPLES_FOR_IC = 10  # Minimum samples required for IC calculation


class FactorAnalyzer:
    """
    因子分析器
    
    提供因子的IC分析、RankIC分析、RankICIR计算、因子权重等功能
    """
    
    def __init__(self):
        """初始化分析器"""
        self.factor_directions = get_factor_directions()
    
    # ========================================================================
    # IC/RankIC 计算
    # ========================================================================
    
    def calc_ic(
        self,
        factor_values: pd.Series,
        returns: pd.Series,
        method: str = 'spearman'
    ) -> Tuple[float, float]:
        """
        计算因子IC值
        
        Args:
            factor_values: 因子值
            returns: 收益率
            method: 计算方法（'spearman' 或 'pearson'）
            
        Returns:
            (IC值, p值)
        """
        # 对齐数据
        valid_mask = factor_values.notna() & returns.notna()
        
        if valid_mask.sum() < MIN_SAMPLES_FOR_IC:
            return np.nan, np.nan
        
        f = factor_values[valid_mask]
        r = returns[valid_mask]
        
        if method == 'spearman':
            ic, pvalue = spearmanr(f, r)
        else:
            ic, pvalue = pearsonr(f, r)
        
        return ic, pvalue
    
    def calc_rank_ic(
        self,
        factor_values: pd.Series,
        returns: pd.Series
    ) -> float:
        """
        计算RankIC（Spearman秩相关系数）
        
        Args:
            factor_values: 因子值
            returns: 收益率
            
        Returns:
            RankIC值
        """
        ic, _ = self.calc_ic(factor_values, returns, method='spearman')
        return ic
    
    def calc_ic_series(
        self,
        df: pd.DataFrame,
        factor_col: str,
        return_col: str,
        date_col: str = 'trade_date',
        method: str = 'spearman'
    ) -> pd.DataFrame:
        """
        计算因子IC时间序列
        
        Args:
            df: 数据DataFrame
            factor_col: 因子列名
            return_col: 收益率列名
            date_col: 日期列名
            method: 计算方法
            
        Returns:
            IC时间序列DataFrame
        """
        results = []
        
        for date, group in df.groupby(date_col):
            ic, pvalue = self.calc_ic(
                group[factor_col], 
                group[return_col],
                method
            )
            results.append({
                'date': date,
                'IC': ic,
                'pvalue': pvalue,
                'count': len(group)
            })
        
        return pd.DataFrame(results)
    
    # ========================================================================
    # RankICIR 计算
    # ========================================================================
    
    def calc_icir(
        self,
        ic_series: pd.Series,
        annualize: bool = True
    ) -> float:
        """
        计算ICIR（IC信息比率）
        
        Args:
            ic_series: IC时间序列
            annualize: 是否年化
            
        Returns:
            ICIR值
        """
        ic_mean = ic_series.mean()
        ic_std = ic_series.std()
        
        if ic_std == 0 or np.isnan(ic_std):
            return np.nan
        
        icir = ic_mean / ic_std
        
        if annualize:
            # 假设月度数据，年化乘以sqrt(12)
            icir = icir * np.sqrt(12)
        
        return icir
    
    def calc_rolling_icir(
        self,
        ic_series: pd.Series,
        window: int = None,
        min_periods: int = None
    ) -> pd.Series:
        """
        计算滚动ICIR
        
        Args:
            ic_series: IC时间序列
            window: 滚动窗口
            min_periods: 最小期数
            
        Returns:
            滚动ICIR序列
        """
        if window is None:
            window = RANKICIR_CONFIG['rolling_window']
        if min_periods is None:
            min_periods = RANKICIR_CONFIG['min_periods']
        
        def calc_icir_window(x):
            if len(x) < min_periods:
                return np.nan
            mean = x.mean()
            std = x.std()
            if std == 0 or np.isnan(std):
                return np.nan
            return mean / std
        
        return ic_series.rolling(window=window, min_periods=min_periods).apply(
            calc_icir_window
        )
    
    # ========================================================================
    # 多因子分析
    # ========================================================================
    
    def calc_all_factors_ic(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        return_col: str,
        date_col: str = 'trade_date'
    ) -> pd.DataFrame:
        """
        计算所有因子的IC时间序列
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            return_col: 收益率列名
            date_col: 日期列名
            
        Returns:
            所有因子的IC时间序列DataFrame
        """
        all_ic = {}
        
        for factor_col in factor_cols:
            if factor_col not in df.columns:
                continue
            
            ic_df = self.calc_ic_series(df, factor_col, return_col, date_col)
            all_ic[factor_col] = ic_df.set_index('date')['IC']
        
        return pd.DataFrame(all_ic)
    
    def calc_all_factors_icir(
        self,
        ic_df: pd.DataFrame,
        window: int = None,
        min_periods: int = None
    ) -> pd.DataFrame:
        """
        计算所有因子的滚动ICIR
        
        Args:
            ic_df: IC时间序列DataFrame（列为因子名）
            window: 滚动窗口
            min_periods: 最小期数
            
        Returns:
            所有因子的滚动ICIR DataFrame
        """
        icir_df = pd.DataFrame(index=ic_df.index)
        
        for col in ic_df.columns:
            icir_df[col] = self.calc_rolling_icir(
                ic_df[col], window, min_periods
            )
        
        return icir_df
    
    # ========================================================================
    # 因子权重计算
    # ========================================================================
    
    def calc_icir_weights(
        self,
        icir_values: Dict[str, float],
        directions: Dict[str, int] = None,
        clip_negative: bool = True
    ) -> Dict[str, float]:
        """
        根据ICIR计算因子权重
        
        Args:
            icir_values: 因子ICIR值字典
            directions: 因子方向字典
            clip_negative: 是否将负权重截断为0
            
        Returns:
            因子权重字典
        """
        if directions is None:
            directions = self.factor_directions
        
        # 计算方向调整后的ICIR
        adj_icir = {}
        for factor, icir in icir_values.items():
            if np.isnan(icir):
                continue
            direction = directions.get(factor, 1)
            adj_icir[factor] = icir * direction
        
        # 截断负值
        if clip_negative:
            adj_icir = {k: max(0, v) for k, v in adj_icir.items()}
        
        # 归一化
        total = sum(adj_icir.values())
        if total > 0:
            weights = {k: v / total for k, v in adj_icir.items()}
        else:
            # 如果所有权重都为0，使用等权
            weights = {k: 1.0 / len(adj_icir) for k in adj_icir}
        
        return weights
    
    def calc_time_varying_weights(
        self,
        icir_df: pd.DataFrame,
        directions: Dict[str, int] = None,
        clip_negative: bool = True
    ) -> pd.DataFrame:
        """
        计算时变因子权重
        
        Args:
            icir_df: 滚动ICIR DataFrame
            directions: 因子方向字典
            clip_negative: 是否将负权重截断为0
            
        Returns:
            时变因子权重DataFrame
        """
        if directions is None:
            directions = self.factor_directions
        
        weights_df = pd.DataFrame(index=icir_df.index, columns=icir_df.columns)
        
        for idx in icir_df.index:
            icir_values = icir_df.loc[idx].to_dict()
            weights = self.calc_icir_weights(icir_values, directions, clip_negative)
            
            for factor, weight in weights.items():
                weights_df.loc[idx, factor] = weight
        
        return weights_df.astype(float)
    
    # ========================================================================
    # 复合因子计算
    # ========================================================================
    
    def calc_composite_factor(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        return_col: str,
        date_col: str = 'trade_date',
        rolling_window: int = None,
        min_periods: int = None,
        directions: Dict[str, int] = None
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        计算RankICIR加权复合因子
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            return_col: 收益率列名
            date_col: 日期列名
            rolling_window: ICIR滚动窗口
            min_periods: 最小期数
            directions: 因子方向字典
            
        Returns:
            (含复合因子的DataFrame, IC时间序列, ICIR时间序列, 权重时间序列)
        """
        if rolling_window is None:
            rolling_window = RANKICIR_CONFIG['rolling_window']
        if min_periods is None:
            min_periods = RANKICIR_CONFIG['min_periods']
        if directions is None:
            directions = self.factor_directions
        
        # 1. 计算所有因子的IC时间序列
        logger.info("计算RankIC时间序列...")
        ic_df = self.calc_all_factors_ic(df, factor_cols, return_col, date_col)
        
        # 2. 计算滚动ICIR
        logger.info("计算滚动RankICIR...")
        icir_df = self.calc_all_factors_icir(ic_df, rolling_window, min_periods)
        
        # 3. 计算时变权重
        logger.info("计算因子权重...")
        weights_df = self.calc_time_varying_weights(icir_df, directions)
        
        # 4. 计算复合因子
        logger.info("计算复合因子...")
        result = df.copy()
        dates = sorted(df[date_col].unique())
        
        result['复合因子'] = np.nan
        
        for date in dates:
            if date not in weights_df.index:
                continue
            
            mask = result[date_col] == date
            weights = weights_df.loc[date].dropna().to_dict()
            
            if not weights:
                continue
            
            # 对当期因子值进行标准化和加权
            composite = pd.Series(0.0, index=result[mask].index)
            
            for factor_col, weight in weights.items():
                if factor_col not in result.columns:
                    continue
                
                factor_values = result.loc[mask, factor_col]
                
                # 横截面标准化
                factor_rank = factor_values.rank(pct=True)
                
                # 方向调整
                direction = directions.get(factor_col, 1)
                if direction == -1:
                    factor_rank = 1 - factor_rank
                
                composite += factor_rank * weight
            
            result.loc[mask, '复合因子'] = composite
        
        return result, ic_df, icir_df, weights_df
    
    # ========================================================================
    # 因子分组回测
    # ========================================================================
    
    def group_backtest(
        self,
        df: pd.DataFrame,
        factor_col: str,
        return_col: str,
        date_col: str = 'trade_date',
        n_groups: int = 5,
        direction: int = 1
    ) -> pd.DataFrame:
        """
        因子分组回测
        
        Args:
            df: 数据DataFrame
            factor_col: 因子列名
            return_col: 收益率列名
            date_col: 日期列名
            n_groups: 分组数量
            direction: 因子方向（1为正向，-1为负向）
            
        Returns:
            分组收益DataFrame
        """
        result = df.copy()
        
        # 按日期分组计算分位数组
        result['group'] = result.groupby(date_col)[factor_col].transform(
            lambda x: pd.qcut(x.rank(method='first'), n_groups, labels=False) + 1
        )
        
        # 如果因子方向为负，翻转分组
        if direction == -1:
            result['group'] = n_groups + 1 - result['group']
        
        # 计算各组收益
        group_returns = result.groupby([date_col, 'group'])[return_col].mean().unstack()
        group_returns.columns = [f'G{i}' for i in group_returns.columns]
        
        # 计算多空收益
        group_returns['Long-Short'] = group_returns[f'G{n_groups}'] - group_returns['G1']
        
        return group_returns
    
    def calc_group_stats(
        self,
        group_returns: pd.DataFrame
    ) -> pd.DataFrame:
        """
        计算分组统计指标
        
        Args:
            group_returns: 分组收益DataFrame
            
        Returns:
            统计指标DataFrame
        """
        stats_dict = {}
        
        for col in group_returns.columns:
            returns = group_returns[col]
            
            stats_dict[col] = {
                '平均收益': returns.mean(),
                '收益标准差': returns.std(),
                '夏普比率': returns.mean() / returns.std() * np.sqrt(12) if returns.std() > 0 else np.nan,
                '胜率': (returns > 0).mean(),
                '最大收益': returns.max(),
                '最小收益': returns.min(),
                '期数': len(returns)
            }
        
        return pd.DataFrame(stats_dict).T
    
    # ========================================================================
    # 因子统计报告
    # ========================================================================
    
    def generate_factor_report(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        return_col: str,
        date_col: str = 'trade_date'
    ) -> pd.DataFrame:
        """
        生成因子统计报告
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            return_col: 收益率列名
            date_col: 日期列名
            
        Returns:
            因子统计报告DataFrame
        """
        report = []
        
        for factor_col in factor_cols:
            if factor_col not in df.columns:
                continue
            
            # 计算IC序列
            ic_series = self.calc_ic_series(df, factor_col, return_col, date_col)['IC']
            
            # 计算统计指标
            stats = {
                '因子名称': factor_col,
                'IC均值': ic_series.mean(),
                'IC标准差': ic_series.std(),
                'ICIR': self.calc_icir(ic_series, annualize=False),
                'ICIR_年化': self.calc_icir(ic_series, annualize=True),
                'IC>0比例': (ic_series > 0).mean(),
                'IC绝对值>0.02比例': (ic_series.abs() > 0.02).mean(),
                't统计量': ic_series.mean() / (ic_series.std() / np.sqrt(len(ic_series))) if ic_series.std() > 0 else np.nan,
                '期数': len(ic_series)
            }
            
            report.append(stats)
        
        return pd.DataFrame(report)
    
    # ========================================================================
    # 因子相关性分析
    # ========================================================================
    
    def calc_factor_correlation(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        date_col: str = 'trade_date',
        method: str = 'spearman'
    ) -> pd.DataFrame:
        """
        计算因子相关性矩阵
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            date_col: 日期列名
            method: 相关系数方法
            
        Returns:
            相关性矩阵DataFrame
        """
        # 计算每期的因子相关性，然后取平均
        corr_matrices = []
        
        for date, group in df.groupby(date_col):
            factor_data = group[factor_cols].dropna()
            if len(factor_data) < MIN_SAMPLES_FOR_IC:
                continue
            
            if method == 'spearman':
                corr = factor_data.corr(method='spearman')
            else:
                corr = factor_data.corr(method='pearson')
            
            corr_matrices.append(corr)
        
        if not corr_matrices:
            return pd.DataFrame()
        
        # 取平均
        avg_corr = sum(corr_matrices) / len(corr_matrices)
        return avg_corr
    
    def analyze_factor_decay(
        self,
        df: pd.DataFrame,
        factor_col: str,
        return_cols: List[str],
        date_col: str = 'trade_date'
    ) -> pd.DataFrame:
        """
        分析因子衰减（不同持仓期的IC）
        
        Args:
            df: 数据DataFrame
            factor_col: 因子列名
            return_cols: 不同持仓期收益率列名列表
            date_col: 日期列名
            
        Returns:
            因子衰减分析DataFrame
        """
        decay_stats = []
        
        for return_col in return_cols:
            if return_col not in df.columns:
                continue
            
            ic_series = self.calc_ic_series(df, factor_col, return_col, date_col)['IC']
            
            decay_stats.append({
                '持仓期': return_col,
                'IC均值': ic_series.mean(),
                'ICIR': self.calc_icir(ic_series, annualize=False),
                'IC>0比例': (ic_series > 0).mean()
            })
        
        return pd.DataFrame(decay_stats)

# -*- coding: utf-8 -*-
"""
因子预处理模块
==============
负责因子数据的标准化、去极值、缺失值处理等
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union
from scipy import stats

from .config import FACTOR_CONFIGS, get_factor_directions

logger = logging.getLogger(__name__)

# Constants for magic numbers
MIN_SAMPLES_FOR_NEUTRALIZE = 10  # Minimum samples required for neutralization


class FactorPreprocessor:
    """
    因子预处理器
    
    提供因子数据的标准化、去极值、缺失值处理等功能
    """
    
    def __init__(self):
        """初始化预处理器"""
        self.factor_directions = get_factor_directions()
    
    # ========================================================================
    # 缺失值处理
    # ========================================================================
    
    def fill_missing(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        method: str = 'median',
        group_col: str = None
    ) -> pd.DataFrame:
        """
        填充缺失值
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            method: 填充方法（'median', 'mean', 'zero', 'drop'）
            group_col: 分组列名（按组填充）
            
        Returns:
            处理后的DataFrame
        """
        result = df.copy()
        
        for col in factor_cols:
            if col not in result.columns:
                continue
            
            if method == 'drop':
                result = result.dropna(subset=[col])
            elif method == 'zero':
                result[col] = result[col].fillna(0)
            elif group_col and group_col in result.columns:
                if method == 'median':
                    result[col] = result.groupby(group_col)[col].transform(
                        lambda x: x.fillna(x.median())
                    )
                elif method == 'mean':
                    result[col] = result.groupby(group_col)[col].transform(
                        lambda x: x.fillna(x.mean())
                    )
            else:
                if method == 'median':
                    result[col] = result[col].fillna(result[col].median())
                elif method == 'mean':
                    result[col] = result[col].fillna(result[col].mean())
        
        return result
    
    # ========================================================================
    # 去极值处理
    # ========================================================================
    
    def winsorize(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        method: str = 'mad',
        limits: tuple = (0.01, 0.99),
        n_std: float = 3.0,
        group_col: str = None
    ) -> pd.DataFrame:
        """
        去极值处理
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            method: 去极值方法（'percentile', 'std', 'mad'）
            limits: 分位数上下限（用于percentile方法）
            n_std: 标准差倍数（用于std/mad方法）
            group_col: 分组列名
            
        Returns:
            处理后的DataFrame
        """
        result = df.copy()
        
        for col in factor_cols:
            if col not in result.columns:
                continue
            
            if group_col and group_col in result.columns:
                result[col] = result.groupby(group_col)[col].transform(
                    lambda x: self._winsorize_series(x, method, limits, n_std)
                )
            else:
                result[col] = self._winsorize_series(
                    result[col], method, limits, n_std
                )
        
        return result
    
    def _winsorize_series(
        self,
        series: pd.Series,
        method: str,
        limits: tuple,
        n_std: float
    ) -> pd.Series:
        """对单个Series进行去极值"""
        s = series.copy()
        valid_mask = s.notna()
        
        if valid_mask.sum() == 0:
            return s
        
        if method == 'percentile':
            lower = s[valid_mask].quantile(limits[0])
            upper = s[valid_mask].quantile(limits[1])
        elif method == 'std':
            mean = s[valid_mask].mean()
            std = s[valid_mask].std()
            lower = mean - n_std * std
            upper = mean + n_std * std
        elif method == 'mad':
            # MAD方法：使用中位数绝对偏差
            median = s[valid_mask].median()
            mad = np.median(np.abs(s[valid_mask] - median))
            lower = median - n_std * 1.4826 * mad
            upper = median + n_std * 1.4826 * mad
        else:
            return s
        
        s = s.clip(lower=lower, upper=upper)
        return s
    
    # ========================================================================
    # 标准化处理
    # ========================================================================
    
    def standardize(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        method: str = 'zscore',
        group_col: str = None
    ) -> pd.DataFrame:
        """
        标准化处理
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            method: 标准化方法（'zscore', 'minmax', 'rank'）
            group_col: 分组列名
            
        Returns:
            处理后的DataFrame
        """
        result = df.copy()
        
        for col in factor_cols:
            if col not in result.columns:
                continue
            
            if group_col and group_col in result.columns:
                result[col] = result.groupby(group_col)[col].transform(
                    lambda x: self._standardize_series(x, method)
                )
            else:
                result[col] = self._standardize_series(result[col], method)
        
        return result
    
    def _standardize_series(
        self,
        series: pd.Series,
        method: str
    ) -> pd.Series:
        """对单个Series进行标准化"""
        s = series.copy()
        valid_mask = s.notna()
        
        if valid_mask.sum() == 0:
            return s
        
        if method == 'zscore':
            mean = s[valid_mask].mean()
            std = s[valid_mask].std()
            if std > 0:
                s[valid_mask] = (s[valid_mask] - mean) / std
            else:
                s[valid_mask] = 0
        elif method == 'minmax':
            min_val = s[valid_mask].min()
            max_val = s[valid_mask].max()
            if max_val > min_val:
                s[valid_mask] = (s[valid_mask] - min_val) / (max_val - min_val)
            else:
                s[valid_mask] = 0.5
        elif method == 'rank':
            s[valid_mask] = s[valid_mask].rank(pct=True)
        
        return s
    
    # ========================================================================
    # 排名转换
    # ========================================================================
    
    def rank_transform(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        group_col: str = None,
        pct: bool = True
    ) -> pd.DataFrame:
        """
        将因子值转换为排名
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            group_col: 分组列名
            pct: 是否转换为百分比排名
            
        Returns:
            处理后的DataFrame
        """
        result = df.copy()
        
        for col in factor_cols:
            if col not in result.columns:
                continue
            
            if group_col and group_col in result.columns:
                result[f'{col}_rank'] = result.groupby(group_col)[col].transform(
                    lambda x: x.rank(pct=pct)
                )
            else:
                result[f'{col}_rank'] = result[col].rank(pct=pct)
        
        return result
    
    # ========================================================================
    # 因子方向调整
    # ========================================================================
    
    def adjust_direction(
        self,
        df: pd.DataFrame,
        factor_cols: List[str] = None,
        directions: Dict[str, int] = None
    ) -> pd.DataFrame:
        """
        根据因子方向调整符号
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            directions: 因子方向字典（正向为1，负向为-1）
            
        Returns:
            调整后的DataFrame
        """
        result = df.copy()
        
        if directions is None:
            directions = self.factor_directions
        
        if factor_cols is None:
            factor_cols = [col for col in directions.keys() if col in result.columns]
        
        for col in factor_cols:
            if col not in result.columns:
                continue
            
            direction = directions.get(col, 1)
            if direction == -1:
                result[col] = -result[col]
        
        return result
    
    # ========================================================================
    # 综合预处理流程
    # ========================================================================
    
    def preprocess(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        group_col: str = 'trade_date',
        fill_method: str = 'median',
        winsorize_method: str = 'mad',
        standardize_method: str = 'zscore',
        adjust_dir: bool = True
    ) -> pd.DataFrame:
        """
        综合预处理流程
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            group_col: 分组列名（通常按调仓日期分组）
            fill_method: 缺失值填充方法
            winsorize_method: 去极值方法
            standardize_method: 标准化方法
            adjust_dir: 是否调整因子方向
            
        Returns:
            预处理后的DataFrame
        """
        result = df.copy()
        
        # 1. 去极值
        if winsorize_method:
            result = self.winsorize(result, factor_cols, winsorize_method, group_col=group_col)
        
        # 2. 填充缺失值
        if fill_method:
            result = self.fill_missing(result, factor_cols, fill_method, group_col=group_col)
        
        # 3. 标准化
        if standardize_method:
            result = self.standardize(result, factor_cols, standardize_method, group_col=group_col)
        
        # 4. 调整因子方向
        if adjust_dir:
            result = self.adjust_direction(result, factor_cols)
        
        return result
    
    # ========================================================================
    # 行业/市值中性化
    # ========================================================================
    
    def neutralize(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        group_col: str = 'trade_date',
        neutralize_cols: List[str] = None
    ) -> pd.DataFrame:
        """
        中性化处理（回归残差法）
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            group_col: 分组列名
            neutralize_cols: 中性化变量列名（如行业、市值等）
            
        Returns:
            中性化后的DataFrame
        """
        if neutralize_cols is None or len(neutralize_cols) == 0:
            return df
        
        result = df.copy()
        
        for col in factor_cols:
            if col not in result.columns:
                continue
            
            if group_col and group_col in result.columns:
                result[col] = result.groupby(group_col).apply(
                    lambda x: self._neutralize_group(x, col, neutralize_cols)
                ).reset_index(level=0, drop=True)
            else:
                result[col] = self._neutralize_group(result, col, neutralize_cols)
        
        return result
    
    def _neutralize_group(
        self,
        df: pd.DataFrame,
        factor_col: str,
        neutralize_cols: List[str]
    ) -> pd.Series:
        """对单组数据进行中性化"""
        valid_mask = df[factor_col].notna()
        for col in neutralize_cols:
            if col in df.columns:
                valid_mask &= df[col].notna()
        
        if valid_mask.sum() < MIN_SAMPLES_FOR_NEUTRALIZE:
            return df[factor_col]
        
        y = df.loc[valid_mask, factor_col].values
        X = df.loc[valid_mask, neutralize_cols].values
        
        # 添加常数项
        X = np.column_stack([np.ones(len(X)), X])
        
        try:
            # OLS回归
            beta = np.linalg.lstsq(X, y, rcond=None)[0]
            residuals = y - X @ beta
            
            result = df[factor_col].copy()
            result.loc[valid_mask] = residuals
            return result
        except Exception as e:
            logger.debug(f"Error neutralizing factor {factor_col}: {e}")
            return df[factor_col]
    
    # ========================================================================
    # 因子合成
    # ========================================================================
    
    def composite_factors(
        self,
        df: pd.DataFrame,
        factor_cols: List[str],
        weights: Dict[str, float] = None,
        method: str = 'weighted'
    ) -> pd.Series:
        """
        因子合成
        
        Args:
            df: 数据DataFrame
            factor_cols: 因子列名列表
            weights: 因子权重字典
            method: 合成方法（'weighted', 'equal', 'rank_weighted'）
            
        Returns:
            合成后的因子Series
        """
        if weights is None:
            weights = {col: 1.0 / len(factor_cols) for col in factor_cols}
        
        # 归一化权重
        total_weight = sum(weights.get(col, 0) for col in factor_cols)
        if total_weight > 0:
            weights = {col: weights.get(col, 0) / total_weight for col in factor_cols}
        
        if method == 'equal':
            weights = {col: 1.0 / len(factor_cols) for col in factor_cols}
        
        # 加权求和
        composite = pd.Series(0.0, index=df.index)
        
        for col in factor_cols:
            if col in df.columns:
                weight = weights.get(col, 0)
                composite += df[col].fillna(0) * weight
        
        return composite

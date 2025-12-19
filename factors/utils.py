# -*- coding: utf-8 -*-
"""
工具函数模块
============
提供通用的工具函数
"""

import os
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Union
from datetime import datetime, timedelta


def ensure_dir(path: str):
    """确保目录存在"""
    if not os.path.exists(path):
        os.makedirs(path)


def format_ts_code(stock_code: str) -> str:
    """
    格式化为Tushare股票代码
    
    Args:
        stock_code: 6位股票代码
        
    Returns:
        Tushare格式代码（如 000001.SZ）
    """
    code = str(stock_code).zfill(6)
    if code.startswith(('6', '9')):
        return f"{code}.SH"
    return f"{code}.SZ"


def parse_ts_code(ts_code: str) -> str:
    """
    从Tushare代码解析出6位股票代码
    
    Args:
        ts_code: Tushare格式代码
        
    Returns:
        6位股票代码
    """
    return ts_code.split('.')[0]


def date_to_str(date: Union[str, datetime, pd.Timestamp], fmt: str = '%Y%m%d') -> str:
    """
    将日期转换为字符串
    
    Args:
        date: 日期
        fmt: 格式
        
    Returns:
        日期字符串
    """
    if isinstance(date, str):
        return date
    elif isinstance(date, (datetime, pd.Timestamp)):
        return date.strftime(fmt)
    return str(date)


def str_to_date(date_str: str, fmt: str = '%Y%m%d') -> datetime:
    """
    将字符串转换为日期
    
    Args:
        date_str: 日期字符串
        fmt: 格式
        
    Returns:
        datetime对象
    """
    return datetime.strptime(date_str, fmt)


def get_period_from_date(trade_date: str) -> str:
    """
    根据调仓日期推断报告期
    
    Args:
        trade_date: 调仓日期（YYYYMMDD）
        
    Returns:
        报告期（YYYYMMDD）
    """
    date = str_to_date(trade_date)
    year = date.year
    month = date.month
    
    # 根据月份推断上一个报告期
    if month <= 4:
        # 1-4月，使用去年三季报
        return f"{year-1}0930"
    elif month <= 8:
        # 5-8月，使用当年一季报
        return f"{year}0331"
    elif month <= 10:
        # 9-10月，使用当年中报
        return f"{year}0630"
    else:
        # 11-12月，使用当年三季报
        return f"{year}0930"


def get_quarter_end_dates(start_year: int, end_year: int) -> List[str]:
    """
    获取季度末日期列表
    
    Args:
        start_year: 起始年份
        end_year: 结束年份
        
    Returns:
        季度末日期列表
    """
    dates = []
    for year in range(start_year, end_year + 1):
        dates.extend([
            f"{year}0331",
            f"{year}0630",
            f"{year}0930",
            f"{year}1231"
        ])
    return dates


def rolling_apply(
    df: pd.DataFrame,
    func,
    window: int,
    min_periods: int = None,
    group_col: str = None
) -> pd.Series:
    """
    滚动应用函数
    
    Args:
        df: 数据DataFrame
        func: 应用函数
        window: 窗口大小
        min_periods: 最小期数
        group_col: 分组列
        
    Returns:
        结果Series
    """
    if min_periods is None:
        min_periods = window
    
    if group_col:
        return df.groupby(group_col).apply(
            lambda x: x.rolling(window, min_periods=min_periods).apply(func)
        )
    return df.rolling(window, min_periods=min_periods).apply(func)


def cross_sectional_rank(
    series: pd.Series,
    pct: bool = True
) -> pd.Series:
    """
    计算横截面排名
    
    Args:
        series: 数据Series
        pct: 是否转换为百分比
        
    Returns:
        排名Series
    """
    return series.rank(pct=pct)


def winsorize_series(
    series: pd.Series,
    lower: float = 0.01,
    upper: float = 0.99
) -> pd.Series:
    """
    对Series进行Winsorize处理
    
    Args:
        series: 数据Series
        lower: 下分位数
        upper: 上分位数
        
    Returns:
        处理后的Series
    """
    lower_val = series.quantile(lower)
    upper_val = series.quantile(upper)
    return series.clip(lower=lower_val, upper=upper_val)


def zscore_normalize(series: pd.Series) -> pd.Series:
    """
    Z-score标准化
    
    Args:
        series: 数据Series
        
    Returns:
        标准化后的Series
    """
    mean = series.mean()
    std = series.std()
    if std == 0:
        return series - mean
    return (series - mean) / std


def calc_return(
    prices: pd.Series,
    periods: int = 1,
    log_return: bool = False
) -> pd.Series:
    """
    计算收益率
    
    Args:
        prices: 价格序列
        periods: 收益率期数
        log_return: 是否使用对数收益率
        
    Returns:
        收益率序列
    """
    if log_return:
        return np.log(prices / prices.shift(periods))
    return prices.pct_change(periods)


def calc_cumulative_return(returns: pd.Series) -> pd.Series:
    """
    计算累计收益率
    
    Args:
        returns: 收益率序列
        
    Returns:
        累计收益率序列
    """
    return (1 + returns).cumprod() - 1


def calc_drawdown(cumulative_returns: pd.Series) -> pd.Series:
    """
    计算回撤
    
    Args:
        cumulative_returns: 累计收益率序列
        
    Returns:
        回撤序列
    """
    wealth = 1 + cumulative_returns
    running_max = wealth.cummax()
    return (wealth - running_max) / running_max


def calc_max_drawdown(cumulative_returns: pd.Series) -> float:
    """
    计算最大回撤
    
    Args:
        cumulative_returns: 累计收益率序列
        
    Returns:
        最大回撤
    """
    drawdown = calc_drawdown(cumulative_returns)
    return drawdown.min()


def calc_sharpe_ratio(
    returns: pd.Series,
    rf: float = 0.0,
    periods_per_year: int = 12
) -> float:
    """
    计算夏普比率
    
    Args:
        returns: 收益率序列
        rf: 无风险利率（年化）
        periods_per_year: 每年期数
        
    Returns:
        夏普比率
    """
    excess_returns = returns - rf / periods_per_year
    mean_return = excess_returns.mean()
    std_return = excess_returns.std()
    
    if std_return == 0:
        return np.nan
    
    return mean_return / std_return * np.sqrt(periods_per_year)


def calc_information_ratio(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    periods_per_year: int = 12
) -> float:
    """
    计算信息比率
    
    Args:
        returns: 策略收益率序列
        benchmark_returns: 基准收益率序列
        periods_per_year: 每年期数
        
    Returns:
        信息比率
    """
    excess_returns = returns - benchmark_returns
    mean_excess = excess_returns.mean()
    std_excess = excess_returns.std()
    
    if std_excess == 0:
        return np.nan
    
    return mean_excess / std_excess * np.sqrt(periods_per_year)


def calc_win_rate(returns: pd.Series) -> float:
    """
    计算胜率
    
    Args:
        returns: 收益率序列
        
    Returns:
        胜率
    """
    return (returns > 0).mean()


def calc_profit_loss_ratio(returns: pd.Series) -> float:
    """
    计算盈亏比
    
    Args:
        returns: 收益率序列
        
    Returns:
        盈亏比
    """
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    
    if len(losses) == 0 or losses.mean() == 0:
        return np.nan
    
    return -wins.mean() / losses.mean()


def generate_performance_stats(
    returns: pd.Series,
    benchmark_returns: pd.Series = None,
    periods_per_year: int = 12
) -> Dict:
    """
    生成绩效统计
    
    Args:
        returns: 策略收益率序列
        benchmark_returns: 基准收益率序列
        periods_per_year: 每年期数
        
    Returns:
        绩效统计字典
    """
    cumulative = calc_cumulative_return(returns)
    
    stats = {
        '累计收益率': cumulative.iloc[-1] if len(cumulative) > 0 else np.nan,
        '年化收益率': returns.mean() * periods_per_year,
        '年化波动率': returns.std() * np.sqrt(periods_per_year),
        '夏普比率': calc_sharpe_ratio(returns, periods_per_year=periods_per_year),
        '最大回撤': calc_max_drawdown(cumulative),
        '胜率': calc_win_rate(returns),
        '盈亏比': calc_profit_loss_ratio(returns),
        '期数': len(returns)
    }
    
    if benchmark_returns is not None:
        stats['信息比率'] = calc_information_ratio(
            returns, benchmark_returns, periods_per_year
        )
        stats['超额收益'] = returns.mean() - benchmark_returns.mean()
    
    return stats

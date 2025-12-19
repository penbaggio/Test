# -*- coding: utf-8 -*-
"""
因子计算模块
============
负责计算需要从Tushare数据计算的因子
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from .config import (
    FACTOR_CONFIGS,
    get_factor_config,
    CALCULATED_FACTORS,
)
from .loader import DataLoader


class FactorCalculator:
    """
    因子计算器
    
    负责计算需要从Tushare数据获取的因子
    """
    
    def __init__(self, loader: DataLoader = None):
        """
        初始化因子计算器
        
        Args:
            loader: 数据加载器，如果不提供则自动创建
        """
        self.loader = loader or DataLoader()
        self._daily_cache: Dict[str, pd.DataFrame] = {}
        self._index_cache: Dict[str, pd.DataFrame] = {}
    
    # ========================================================================
    # 工具方法
    # ========================================================================
    
    def _get_trade_dates(self, start_date: str, end_date: str) -> List[str]:
        """获取交易日列表"""
        cal = self.loader.get_trade_cal(start_date, end_date)
        if cal is not None and len(cal) > 0:
            return sorted(cal['cal_date'].tolist())
        return []
    
    def _get_offset_trade_date(
        self, 
        base_date: str, 
        offset: int,
        trade_dates: List[str] = None
    ) -> Optional[str]:
        """
        获取偏移N个交易日的日期
        
        Args:
            base_date: 基准日期
            offset: 偏移天数（负数为往前）
            trade_dates: 交易日列表（可选）
            
        Returns:
            偏移后的交易日期
        """
        if trade_dates is None:
            # 获取足够范围的交易日
            start = (datetime.strptime(base_date, '%Y%m%d') - timedelta(days=abs(offset)*2)).strftime('%Y%m%d')
            end = (datetime.strptime(base_date, '%Y%m%d') + timedelta(days=abs(offset)*2)).strftime('%Y%m%d')
            trade_dates = self._get_trade_dates(start, end)
        
        if base_date not in trade_dates:
            # 找最近的交易日
            for td in sorted(trade_dates, reverse=True):
                if td <= base_date:
                    base_date = td
                    break
        
        try:
            idx = trade_dates.index(base_date)
            target_idx = idx + offset
            if 0 <= target_idx < len(trade_dates):
                return trade_dates[target_idx]
        except ValueError:
            pass
        
        return None
    
    def _ensure_daily_data(
        self, 
        ts_code: str, 
        start_date: str, 
        end_date: str
    ) -> pd.DataFrame:
        """确保日线数据已加载"""
        cache_key = f"{ts_code}_{start_date}_{end_date}"
        
        if cache_key not in self._daily_cache:
            df = self.loader.get_daily_data(ts_code, start_date, end_date)
            if df is not None and len(df) > 0:
                df = df.sort_values('trade_date').reset_index(drop=True)
                self._daily_cache[cache_key] = df
            else:
                self._daily_cache[cache_key] = pd.DataFrame()
        
        return self._daily_cache[cache_key]
    
    def _ensure_index_data(
        self, 
        ts_code: str, 
        start_date: str, 
        end_date: str
    ) -> pd.DataFrame:
        """确保指数数据已加载"""
        cache_key = f"index_{ts_code}_{start_date}_{end_date}"
        
        if cache_key not in self._index_cache:
            df = self.loader.get_index_daily(ts_code, start_date, end_date)
            if df is not None and len(df) > 0:
                df = df.sort_values('trade_date').reset_index(drop=True)
                self._index_cache[cache_key] = df
            else:
                self._index_cache[cache_key] = pd.DataFrame()
        
        return self._index_cache[cache_key]
    
    # ========================================================================
    # 市净率因子（账面市值比 = 1/PB = 净资产/市值）
    # ========================================================================
    
    def calc_pb_ratio(
        self,
        ts_code: str,
        trade_date: str,
        period: str
    ) -> Optional[float]:
        """
        计算市净率（账面市值比）
        
        Args:
            ts_code: 股票代码
            trade_date: 调仓日期
            period: 报告期（YYYYMMDD）
            
        Returns:
            账面市值比 = 报告期末净资产 / 调仓日总市值 (1/PB)
        """
        try:
            # 1. 获取调仓日总市值
            daily_basic = self.loader.get_daily_basic_info(trade_date)
            if daily_basic is None or len(daily_basic) == 0:
                return None
            
            stock_basic = daily_basic[daily_basic['ts_code'] == ts_code]
            if len(stock_basic) == 0:
                return None
            
            total_mv = stock_basic.iloc[0].get('total_mv')  # 总市值（万元）
            if pd.isna(total_mv) or total_mv <= 0:
                return None
            
            # 2. 获取报告期末净资产（归属母公司股东权益）
            fina = self.loader.pro.balancesheet(
                ts_code=ts_code,
                period=period,
                fields='ts_code,end_date,total_hldr_eqy_exc_min_int'
            )
            if fina is None or len(fina) == 0:
                return None
            
            # 归属母公司股东权益（元）
            equity = fina.iloc[0].get('total_hldr_eqy_exc_min_int')
            if pd.isna(equity) or equity <= 0:
                return None
            
            # 计算账面市值比 = 净资产 / 总市值
            # 注意单位转换：总市值万元 -> 元
            bm_ratio = equity / (total_mv * 10000)
            return bm_ratio
            
        except Exception as e:
            return None
    
    # ========================================================================
    # 经营活动现金流量净额占比因子
    # ========================================================================
    
    def calc_cashflow_ratio(
        self,
        ts_code: str,
        trade_date: str,
        period: str
    ) -> Optional[float]:
        """
        计算经营活动现金流量净额占比
        
        Args:
            ts_code: 股票代码
            trade_date: 调仓日期
            period: 报告期（YYYYMMDD）
            
        Returns:
            经营活动现金流量净额 / 总资产
        """
        try:
            # 获取现金流量表
            cashflow = self.loader.pro.cashflow(
                ts_code=ts_code,
                period=period,
                fields='ts_code,end_date,n_cashflow_act'
            )
            
            if cashflow is None or len(cashflow) == 0:
                return None
            
            # 获取资产负债表（总资产）
            balance = self.loader.pro.balancesheet(
                ts_code=ts_code,
                period=period,
                fields='ts_code,end_date,total_assets'
            )
            
            if balance is None or len(balance) == 0:
                return None
            
            # 取数据
            cf_value = cashflow.iloc[0].get('n_cashflow_act')  # 经营活动现金流量净额
            total_assets = balance.iloc[0].get('total_assets')  # 总资产
            
            if pd.isna(cf_value) or pd.isna(total_assets):
                return None
            
            if total_assets == 0:
                return None
            
            return cf_value / total_assets
            
        except Exception as e:
            return None
    
    # ========================================================================
    # 单季度ROE同比因子
    # ========================================================================
    
    def calc_roe_yoy(
        self,
        ts_code: str,
        trade_date: str,
        period: str
    ) -> Optional[float]:
        """
        计算单季度ROE同比
        
        Args:
            ts_code: 股票代码
            trade_date: 调仓日期
            period: 报告期（YYYYMMDD）
            
        Returns:
            单季度ROE同比变化（当期ROE - 去年同期ROE）
        """
        try:
            # 获取当期财务指标
            fina_curr = self.loader.pro.fina_indicator(
                ts_code=ts_code,
                period=period,
                fields='ts_code,end_date,roe,q_roe'
            )
            
            if fina_curr is None or len(fina_curr) == 0:
                return None
            
            # 获取去年同期
            year = int(period[:4])
            month_day = period[4:]
            prev_period = f"{year - 1}{month_day}"
            
            fina_prev = self.loader.pro.fina_indicator(
                ts_code=ts_code,
                period=prev_period,
                fields='ts_code,end_date,roe,q_roe'
            )
            
            if fina_prev is None or len(fina_prev) == 0:
                return None
            
            # 使用单季度ROE (q_roe)
            curr_roe = fina_curr.iloc[0].get('q_roe')
            prev_roe = fina_prev.iloc[0].get('q_roe')
            
            # 如果没有单季度ROE，尝试自己计算
            if pd.isna(curr_roe) or pd.isna(prev_roe):
                # 使用累计ROE计算单季度
                curr_roe_cum = fina_curr.iloc[0].get('roe')
                prev_roe_cum = fina_prev.iloc[0].get('roe')
                
                if pd.isna(curr_roe_cum) or pd.isna(prev_roe_cum):
                    return None
                
                # 简化处理：直接使用累计ROE的同比
                return curr_roe_cum - prev_roe_cum
            
            return curr_roe - prev_roe
            
        except Exception as e:
            return None
    
    # ========================================================================
    # 日收益波动率因子
    # ========================================================================
    
    def _get_n_trade_days_before(self, trade_dates: List[str], date_str: str, n: int) -> str:
        """
        获取某日期前n个交易日（与原始脚本完全一致）
        """
        import bisect
        date_str = str(date_str).replace('-', '').replace('/', '')
        
        # 找到第一个大于等于date_str的位置
        idx = bisect.bisect_left(trade_dates, date_str)
        
        # 如果date_str正好是交易日，idx指向它
        # 如果不是交易日，idx指向下一个交易日
        if idx < len(trade_dates) and trade_dates[idx] == date_str:
            # date_str是交易日
            target_idx = idx - n
        else:
            # date_str不是交易日，找前一个交易日
            if idx > 0:
                target_idx = idx - 1 - n
            else:
                target_idx = 0 - n
        
        # 边界检查
        if target_idx < 0:
            return trade_dates[0]
        if target_idx >= len(trade_dates):
            return trade_dates[-1]
        
        return trade_dates[target_idx]
    
    def calc_volatility(
        self,
        ts_code: str,
        trade_date: str,
        window: int = 60
    ) -> Optional[float]:
        """
        计算日收益波动率（过去3个月日度收益率标准差）
        
        Args:
            ts_code: 股票代码
            trade_date: 调仓日期
            window: 回溯窗口（交易日），默认60个交易日约3个月
            
        Returns:
            日收益率标准差
        """
        try:
            # 获取交易日历
            cal = self.loader.get_trade_cal('20150101', '20251231')
            if cal is None or len(cal) == 0:
                return None
            trade_dates = sorted(cal['cal_date'].tolist())
            
            trade_date_fmt = trade_date.replace('-', '').replace('/', '')
            
            # 使用交易日历精确计算T-window的日期
            start_date = self._get_n_trade_days_before(trade_dates, trade_date_fmt, window)
            
            # 获取日线数据
            daily_df = self._ensure_daily_data(ts_code, start_date, trade_date_fmt)
            if daily_df is None or len(daily_df) == 0:
                return None
            
            # 筛选日期范围
            df = daily_df[(daily_df['trade_date'] >= start_date) & 
                          (daily_df['trade_date'] <= trade_date_fmt)].copy()
            
            if len(df) < 20:  # 至少需要20个交易日
                return None
            
            df = df.sort_values('trade_date')
            
            # 计算日收益率
            df['ret'] = df['close'].pct_change()
            
            # 计算标准差（去除第一个NaN值）
            returns = df['ret'].dropna()
            
            if len(returns) < 20:
                return None
            
            return returns.std()
            
        except Exception as e:
            return None
            return None
    
    # ========================================================================
    # 盈余公告跳空超额因子
    # ========================================================================
    
    def calc_earnings_gap(
        self,
        ts_code: str,
        trade_date: str,
        period: str,
        benchmark: str = '000905.SH'
    ) -> Optional[float]:
        """
        计算盈余公告跳空超额收益（与原始脚本一致）
        
        逻辑说明:
        - 使用disclosure_date接口获取财报披露日期
        - 如果披露日是交易日，假设盘后发布，次日开盘为反应日
        - 如果披露日不是交易日，下一个交易日开盘为反应日
        
        Args:
            ts_code: 股票代码
            trade_date: 调仓日期
            period: 报告期（YYYYMMDD）
            benchmark: 基准指数（中证500）
            
        Returns:
            盈余公告跳空超额收益
        """
        try:
            # 获取披露日期
            disclosure = self.loader.pro.disclosure_date(end_date=period)
            if disclosure is None or len(disclosure) == 0:
                return None
            
            disc = disclosure[disclosure['ts_code'] == ts_code]
            if disc.empty:
                return None
            
            actual_date = disc['actual_date'].iloc[0]
            if pd.isna(actual_date):
                return None
            
            actual_date = str(int(actual_date)) if isinstance(actual_date, float) else str(actual_date)
            
            # 获取交易日历
            cal = self.loader.get_trade_cal('20150101', '20251231')
            if cal is None or len(cal) == 0:
                return None
            trade_dates = sorted(cal['cal_date'].tolist())
            
            # 判断披露日是否为交易日
            is_trade_day = actual_date in trade_dates
            
            if is_trade_day:
                # 披露日是交易日，假设盘后发布
                # 反应日 = 下一个交易日
                # 基准日 = 披露日（当天收盘价）
                idx = trade_dates.index(actual_date)
                if idx + 1 >= len(trade_dates):
                    return None
                reaction_day = trade_dates[idx + 1]
                base_day = actual_date
            else:
                # 披露日不是交易日
                # 反应日 = 下一个交易日
                # 基准日 = 披露日前的最后一个交易日
                reaction_day = None
                base_day = None
                for td in trade_dates:
                    if td > actual_date:
                        reaction_day = td
                        break
                    base_day = td
                if reaction_day is None or base_day is None:
                    return None
            
            # 获取个股数据
            start_date = (datetime.strptime(trade_date, '%Y%m%d') - timedelta(days=400)).strftime('%Y%m%d')
            stock_df = self._ensure_daily_data(ts_code, start_date, trade_date)
            if stock_df is None or len(stock_df) == 0:
                return None
            
            stock_reaction = stock_df[stock_df['trade_date'] == reaction_day]
            stock_base = stock_df[stock_df['trade_date'] == base_day]
            
            if stock_reaction.empty or stock_base.empty:
                return None
            
            stock_open_reaction = stock_reaction['open'].iloc[0]
            stock_close_base = stock_base['close'].iloc[0]
            
            if pd.isna(stock_open_reaction) or pd.isna(stock_close_base) or stock_close_base == 0:
                return None
            
            # 获取指数数据
            index_df = self._ensure_index_data(benchmark, start_date, trade_date)
            if index_df is None or len(index_df) == 0:
                return None
            
            index_reaction = index_df[index_df['trade_date'] == reaction_day]
            index_base = index_df[index_df['trade_date'] == base_day]
            
            if index_reaction.empty or index_base.empty:
                return None
            
            index_open_reaction = index_reaction['open'].iloc[0]
            index_close_base = index_base['close'].iloc[0]
            
            if pd.isna(index_open_reaction) or pd.isna(index_close_base) or index_close_base == 0:
                return None
            
            # 计算跳空超额
            stock_gap = stock_open_reaction / stock_close_base - 1
            index_gap = index_open_reaction / index_close_base - 1
            
            return stock_gap - index_gap
            
        except Exception as e:
            return None
    
    def _get_limit_up_threshold(self, ts_code: str, name: str = '') -> float:
        """
        根据股票代码和名称获取涨停阈值
        
        Returns:
            涨停阈值百分比（如9.8表示9.8%）
        """
        ts_code = str(ts_code)
        name = str(name) if name else ''
        
        # ST股票涨跌幅5%
        if 'ST' in name.upper() or '*ST' in name.upper():
            return 4.8
        
        # 北交所股票涨跌幅30%
        if ts_code.startswith('8') and ts_code.endswith('.BJ'):
            return 29.8
        
        # 科创板(688)涨跌幅20%
        if ts_code.startswith('688'):
            return 19.8
        
        # 创业板(300/301)涨跌幅20%
        if ts_code.startswith('300') or ts_code.startswith('301'):
            return 19.8
        
        # 普通股票涨跌幅10%
        return 9.8
    
    # ========================================================================
    # 剥离涨停动量因子
    # ========================================================================
    
    def calc_momentum_ex_limit(
        self,
        ts_code: str,
        trade_date: str,
        start_offset: int = 260,
        end_offset: int = 20,
        stock_name: str = ''
    ) -> Optional[float]:
        """
        计算剥离涨停动量（与原始脚本完全一致）
        
        Args:
            ts_code: 股票代码
            trade_date: 调仓日期
            start_offset: 起始偏移（交易日前）
            end_offset: 结束偏移（交易日前）
            stock_name: 股票名称（用于ST判断）
            
        Returns:
            剥离涨停后的累计收益
        """
        try:
            # 获取交易日历
            cal = self.loader.get_trade_cal('20150101', '20251231')
            if cal is None or len(cal) == 0:
                return None
            trade_dates = sorted(cal['cal_date'].tolist())
            
            trade_date_fmt = trade_date.replace('-', '').replace('/', '')
            
            # 使用交易日历精确计算日期范围
            start_date = self._get_n_trade_days_before(trade_dates, trade_date_fmt, start_offset)
            end_date = self._get_n_trade_days_before(trade_dates, trade_date_fmt, end_offset)
            
            # 获取日线数据
            daily_df = self._ensure_daily_data(ts_code, start_date, end_date)
            if daily_df is None or len(daily_df) == 0:
                return None
            
            # 筛选日期范围
            df = daily_df[(daily_df['trade_date'] >= start_date) & 
                          (daily_df['trade_date'] <= end_date)].copy()
            
            if len(df) < 50:  # 至少需要50个交易日
                return None
            
            df = df.sort_values('trade_date')
            
            # 获取涨停阈值（根据股票类型动态确定）
            limit_threshold = self._get_limit_up_threshold(ts_code, stock_name)
            
            # 判断涨停
            df['is_limit_up'] = df['pct_chg'] >= limit_threshold
            
            # 剔除涨停日
            df_no_limit = df[~df['is_limit_up']]
            
            if len(df_no_limit) < 20:
                return None
            
            # 检查pct_chg是否有效
            valid_pct = df_no_limit['pct_chg'].dropna()
            if len(valid_pct) < 20:
                return None
            
            # 计算累计收益率
            cum_ret = (1 + valid_pct / 100).prod() - 1
            
            return cum_ret
            
        except Exception as e:
            return None
    
    # ========================================================================
    # 批量计算接口
    # ========================================================================
    
    def calculate_all_factors(
        self,
        df: pd.DataFrame,
        factors: List[str] = None,
        show_progress: bool = True
    ) -> pd.DataFrame:
        """
        批量计算所有需要计算的因子
        
        Args:
            df: 包含股票代码和调仓日期的DataFrame
            factors: 要计算的因子列表，默认为所有需要计算的因子
            show_progress: 是否显示进度
            
        Returns:
            添加了因子列的DataFrame
        """
        if factors is None:
            factors = CALCULATED_FACTORS
        
        result = df.copy()
        
        # 确保有ts_code列
        if 'ts_code' not in result.columns and '股票代码' in result.columns:
            result['ts_code'] = result['股票代码'].apply(
                lambda x: f"{str(x).zfill(6)}.SH" if str(x).startswith(('6', '9')) 
                else f"{str(x).zfill(6)}.SZ"
            )
        
        # 确保有trade_date列
        if 'trade_date' not in result.columns and '调仓日期' in result.columns:
            result['trade_date'] = pd.to_datetime(result['调仓日期']).dt.strftime('%Y%m%d')
        
        total = len(result)
        
        for factor_name in factors:
            config = get_factor_config(factor_name)
            if not config.is_calculated:
                continue
            
            print(f"\nCalculating factor: {factor_name}")
            
            factor_values = []
            
            for i, row in result.iterrows():
                if show_progress and (i + 1) % 100 == 0:
                    print(f"  Progress: {i + 1}/{total}")
                
                ts_code = row['ts_code']
                trade_date = row['trade_date']
                period = row.get('报告期', row.get('period', ''))
                if pd.notna(period):
                    period = str(int(period)) if isinstance(period, float) else str(period)
                
                value = None
                
                if factor_name == "市净率":
                    value = self.calc_pb_ratio(ts_code, trade_date, period)
                elif factor_name == "经营活动现金流量净额占比":
                    value = self.calc_cashflow_ratio(ts_code, trade_date, period)
                elif factor_name == "单季度ROE同比":
                    value = self.calc_roe_yoy(ts_code, trade_date, period)
                elif factor_name == "日收益波动率":
                    value = self.calc_volatility(
                        ts_code, trade_date,
                        **config.calc_params
                    )
                elif factor_name == "盈余公告跳空超额":
                    value = self.calc_earnings_gap(
                        ts_code, trade_date, period,
                        **config.calc_params
                    )
                elif factor_name == "剥离涨停动量":
                    value = self.calc_momentum_ex_limit(
                        ts_code, trade_date,
                        **config.calc_params
                    )
                
                factor_values.append(value)
            
            result[config.column_name] = factor_values
            
            # 统计覆盖率
            valid_count = sum(1 for v in factor_values if v is not None)
            coverage = valid_count / total * 100
            print(f"  Coverage: {valid_count}/{total} ({coverage:.1f}%)")
        
        return result
    
    def calculate_single_factor(
        self,
        ts_code: str,
        trade_date: str,
        factor_name: str,
        period: str = None
    ) -> Optional[float]:
        """
        计算单个因子值
        
        Args:
            ts_code: 股票代码
            trade_date: 调仓日期
            factor_name: 因子名称
            period: 报告期
            
        Returns:
            因子值
        """
        config = get_factor_config(factor_name)
        
        if factor_name == "市净率":
            return self.calc_pb_ratio(ts_code, trade_date, period)
        elif factor_name == "经营活动现金流量净额占比":
            return self.calc_cashflow_ratio(ts_code, trade_date, period)
        elif factor_name == "单季度ROE同比":
            return self.calc_roe_yoy(ts_code, trade_date, period)
        elif factor_name == "日收益波动率":
            return self.calc_volatility(ts_code, trade_date, **config.calc_params)
        elif factor_name == "盈余公告跳空超额":
            return self.calc_earnings_gap(ts_code, trade_date, period, **config.calc_params)
        elif factor_name == "剥离涨停动量":
            return self.calc_momentum_ex_limit(ts_code, trade_date, **config.calc_params)
        
        return None

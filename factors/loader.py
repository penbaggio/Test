# -*- coding: utf-8 -*-
"""
数据加载模块
============
负责从Tushare和本地文件加载数据，支持缓存机制
"""

import os
import pickle
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
import pandas as pd
import numpy as np
import tushare as ts

from .config import (
    TUSHARE_TOKEN, 
    CACHE_DIR, 
    CACHE_ENABLED, 
    CACHE_EXPIRE_DAYS,
    DATA_PATHS,
)


class DataLoader:
    """
    数据加载器
    
    负责从Tushare API和本地文件加载数据，支持缓存机制以提高效率
    """
    
    def __init__(self, token: str = None, cache_dir: str = None):
        """
        初始化数据加载器
        
        Args:
            token: Tushare API token
            cache_dir: 缓存目录
        """
        self.token = token or TUSHARE_TOKEN
        self.cache_dir = cache_dir or CACHE_DIR
        self._pro = None
        
        # 确保缓存目录存在
        if CACHE_ENABLED and not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
    
    @property
    def pro(self):
        """获取Tushare Pro API实例"""
        if self._pro is None:
            ts.set_token(self.token)
            self._pro = ts.pro_api()
        return self._pro
    
    # ========================================================================
    # 缓存管理
    # ========================================================================
    
    def _get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        # 使用MD5哈希处理长key
        hash_key = hashlib.md5(cache_key.encode()).hexdigest()[:16]
        safe_key = "".join(c if c.isalnum() or c in "_-" else "_" for c in cache_key[:50])
        return os.path.join(self.cache_dir, f"{safe_key}_{hash_key}.pkl")
    
    def _load_cache(self, cache_key: str, max_age_days: int = None) -> Optional[Any]:
        """加载缓存数据"""
        if not CACHE_ENABLED:
            return None
            
        cache_path = self._get_cache_path(cache_key)
        if not os.path.exists(cache_path):
            return None
            
        max_age_days = max_age_days or CACHE_EXPIRE_DAYS
        file_time = datetime.fromtimestamp(os.path.getmtime(cache_path))
        if datetime.now() - file_time > timedelta(days=max_age_days):
            return None
            
        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Warning: Failed to load cache {cache_key}: {e}")
            return None
    
    def _save_cache(self, cache_key: str, data: Any):
        """保存缓存数据"""
        if not CACHE_ENABLED:
            return
            
        cache_path = self._get_cache_path(cache_key)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)
        except Exception as e:
            print(f"Warning: Failed to save cache {cache_key}: {e}")
    
    def clear_cache(self):
        """清除所有缓存"""
        if os.path.exists(self.cache_dir):
            for f in os.listdir(self.cache_dir):
                if f.endswith('.pkl'):
                    os.remove(os.path.join(self.cache_dir, f))
            print(f"Cleared cache in {self.cache_dir}")
    
    # ========================================================================
    # 本地数据加载
    # ========================================================================
    
    def load_factor_data(self, file_path: str = None) -> pd.DataFrame:
        """
        加载因子数据文件
        
        Args:
            file_path: 文件路径，默认为配置中的input_file
            
        Returns:
            因子数据DataFrame
        """
        file_path = file_path or DATA_PATHS["input_file"]
        
        df = pd.read_csv(file_path, dtype={'股票代码': str})
        
        # 标准化股票代码格式
        if '股票代码' in df.columns:
            df['股票代码'] = df['股票代码'].str.zfill(6)
            # 添加ts_code格式
            df['ts_code'] = df['股票代码'].apply(
                lambda x: f"{x}.SH" if x.startswith(('6', '9')) else f"{x}.SZ"
            )
        
        # 转换日期格式
        if '调仓日期' in df.columns:
            df['trade_date'] = pd.to_datetime(df['调仓日期']).dt.strftime('%Y%m%d')
        
        print(f"Loaded factor data: {len(df)} records, {df['调仓日期'].nunique()} periods")
        return df
    
    # ========================================================================
    # Tushare数据加载
    # ========================================================================
    
    def get_daily_data(
        self, 
        ts_code: str, 
        start_date: str, 
        end_date: str,
        adj: str = None
    ) -> pd.DataFrame:
        """
        获取股票日线数据
        
        Args:
            ts_code: 股票代码（如 000001.SZ）
            start_date: 开始日期（YYYYMMDD）
            end_date: 结束日期（YYYYMMDD）
            adj: 复权类型（qfq/hfq/None），默认None表示不复权
            
        Returns:
            日线数据DataFrame
        """
        cache_key = f"daily_{ts_code}_{start_date}_{end_date}_{adj}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            if adj:
                df = ts.pro_bar(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date,
                    adj=adj
                )
            else:
                # 默认使用不复权数据（与原始脚本一致）
                df = self.pro.daily(
                    ts_code=ts_code,
                    start_date=start_date,
                    end_date=end_date
                )
            
            if df is not None and len(df) > 0:
                df = df.sort_values('trade_date')
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error getting daily data for {ts_code}: {e}")
            return pd.DataFrame()
    
    def get_daily_basic(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        获取股票每日指标数据（包含涨停标志等）
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            每日指标数据DataFrame
        """
        cache_key = f"daily_basic_{ts_code}_{start_date}_{end_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            df = self.pro.stk_limit(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and len(df) > 0:
                df = df.sort_values('trade_date')
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error getting daily basic for {ts_code}: {e}")
            return pd.DataFrame()
    
    def get_index_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        获取指数日线数据
        
        Args:
            ts_code: 指数代码（如 000985.SH）
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            指数日线数据DataFrame
        """
        cache_key = f"index_{ts_code}_{start_date}_{end_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            df = self.pro.index_daily(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and len(df) > 0:
                df = df.sort_values('trade_date')
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error getting index data for {ts_code}: {e}")
            return pd.DataFrame()
    
    def get_disclosure_dates(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        获取财报公告日期
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            公告日期数据DataFrame
        """
        cache_key = f"disclosure_{ts_code}_{start_date}_{end_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            df = self.pro.disclosure_date(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and len(df) > 0:
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error getting disclosure dates for {ts_code}: {e}")
            return pd.DataFrame()
    
    def get_express_dates(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        获取业绩快报公告日期
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            业绩快报数据DataFrame
        """
        cache_key = f"express_{ts_code}_{start_date}_{end_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            df = self.pro.express(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and len(df) > 0:
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error getting express dates for {ts_code}: {e}")
            return pd.DataFrame()
    
    def get_forecast_dates(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        获取业绩预告公告日期
        
        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            业绩预告数据DataFrame
        """
        cache_key = f"forecast_{ts_code}_{start_date}_{end_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            df = self.pro.forecast(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and len(df) > 0:
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error getting forecast dates for {ts_code}: {e}")
            return pd.DataFrame()
    
    def get_fina_indicator(
        self,
        ts_code: str,
        period: str = None
    ) -> pd.DataFrame:
        """
        获取财务指标数据
        
        Args:
            ts_code: 股票代码
            period: 报告期（YYYYMMDD）
            
        Returns:
            财务指标数据DataFrame
        """
        cache_key = f"fina_{ts_code}_{period or 'all'}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            if period:
                df = self.pro.fina_indicator(ts_code=ts_code, period=period)
            else:
                df = self.pro.fina_indicator(ts_code=ts_code)
            
            if df is not None and len(df) > 0:
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error getting fina indicator for {ts_code}: {e}")
            return pd.DataFrame()
    
    def get_daily_basic_info(
        self,
        trade_date: str
    ) -> pd.DataFrame:
        """
        获取全市场每日基本面数据
        
        Args:
            trade_date: 交易日期
            
        Returns:
            每日基本面数据DataFrame
        """
        cache_key = f"daily_basic_info_{trade_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            df = self.pro.daily_basic(trade_date=trade_date)
            
            if df is not None and len(df) > 0:
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error getting daily basic info for {trade_date}: {e}")
            return pd.DataFrame()
    
    def get_trade_cal(
        self,
        start_date: str,
        end_date: str,
        exchange: str = 'SSE'
    ) -> pd.DataFrame:
        """
        获取交易日历
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            exchange: 交易所（SSE/SZSE）
            
        Returns:
            交易日历DataFrame
        """
        cache_key = f"trade_cal_{exchange}_{start_date}_{end_date}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        try:
            df = self.pro.trade_cal(
                exchange=exchange,
                start_date=start_date,
                end_date=end_date
            )
            
            if df is not None and len(df) > 0:
                # 只保留交易日
                df = df[df['is_open'] == 1]
                self._save_cache(cache_key, df)
            return df
        except Exception as e:
            print(f"Error getting trade calendar: {e}")
            return pd.DataFrame()
    
    # ========================================================================
    # 批量数据加载
    # ========================================================================
    
    def batch_get_daily_data(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: str,
        adj: str = 'qfq',
        show_progress: bool = True
    ) -> Dict[str, pd.DataFrame]:
        """
        批量获取股票日线数据
        
        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权类型
            show_progress: 是否显示进度
            
        Returns:
            股票代码 -> 日线数据的字典
        """
        result = {}
        total = len(ts_codes)
        
        for i, ts_code in enumerate(ts_codes):
            if show_progress and (i + 1) % 50 == 0:
                print(f"Loading daily data: {i + 1}/{total}")
            
            df = self.get_daily_data(ts_code, start_date, end_date, adj)
            if df is not None and len(df) > 0:
                result[ts_code] = df
        
        return result
    
    def get_all_daily_data(
        self,
        ts_codes: List[str],
        start_date: str,
        end_date: str,
        adj: str = 'qfq'
    ) -> pd.DataFrame:
        """
        获取所有股票的日线数据并合并
        
        Args:
            ts_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            adj: 复权类型
            
        Returns:
            合并后的日线数据DataFrame
        """
        cache_key = f"all_daily_{hash(tuple(sorted(ts_codes)))}_{start_date}_{end_date}_{adj}"
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached
        
        data_dict = self.batch_get_daily_data(ts_codes, start_date, end_date, adj)
        
        if data_dict:
            df = pd.concat(data_dict.values(), ignore_index=True)
            self._save_cache(cache_key, df)
            return df
        
        return pd.DataFrame()

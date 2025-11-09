import os
import logging
from typing import Optional
from datetime import date
import pandas as pd

from .calendar import TradingCalendar

logger = logging.getLogger(__name__)


def fetch_benchmark_series(base_dir: str, data_client, code: str, start: date, end: date, initial_nav: float = 1.0) -> Optional[pd.DataFrame]:
    """获取基准指数收盘价并归一化为净值。

    优先使用数据客户端的 get_index_close_series(start,end)；若不可用，则基于交易日输出常数序列，避免流程中断。
    返回列: date, close(optional), nav
    """
    # 输出与缓存路径
    data_dir = os.path.normpath(os.path.join(base_dir, 'data'))
    os.makedirs(data_dir, exist_ok=True)
    safe_code = str(code).replace(':', '_').replace('/', '_')
    cache_path = os.path.join(data_dir, f'benchmark_{safe_code}.csv')

    # 优先从数据源拉取
    df = None
    if data_client is not None and hasattr(data_client, 'get_index_close_series'):
        try:
            df = data_client.get_index_close_series(code, start, end)
        except Exception as e:
            logger.exception(f"从数据源获取基准失败：code={code}，{e}")

    # 若无数据，回退到常数序列
    if df is None or df.empty:
        logger.warning(f"未获取到基准收盘价，回退为常数基准：code={code}")
        cal = TradingCalendar(data_client=data_client)
        days = cal.trade_days_between(start, end)
        df = pd.DataFrame({'date': days, 'nav': [initial_nav] * len(days)})
        try:
            df.to_csv(cache_path, index=False, encoding='utf-8')
        except Exception:
            pass
        return df

    # 归一化为净值
    keep_cols = [c for c in df.columns if c in ('date', 'close')]
    if 'date' not in keep_cols:
        raise ValueError('benchmark dataframe must contain date column')
    if 'close' not in df.columns:
        # 如果只有 nav，直接返回
        if 'nav' in df.columns:
            out = df[['date', 'nav']].copy()
        else:
            raise ValueError('benchmark dataframe missing close/nav columns')
    else:
        df = df.sort_values('date').reset_index(drop=True)
        base = float(df['close'].iloc[0])
        if base == 0:
            base = 1.0
        out = df[['date', 'close']].copy()
        out['nav'] = initial_nav * (out['close'] / base)
    # 缓存落盘
    try:
        out.to_csv(cache_path, index=False, encoding='utf-8')
        logger.info(f"基准缓存已写入：{cache_path}，行数={len(out)}")
    except Exception:
        pass
    return out

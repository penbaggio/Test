from typing import List, Dict
import pandas as pd
from datetime import datetime
from pathlib import Path

# WindPy 全局调用要求在主环境中 w.start()
try:
    from WindPy import w  # type: ignore
except ImportError:
    w = None

FIELDS = 'close'
CACHE_DIR = Path(__file__).parent / 'cache_prices'
CACHE_DIR.mkdir(exist_ok=True)


def ensure_wind():
    if w is None:
        raise RuntimeError('WindPy 未安装或无法导入')
    if not w.isconnected():
        w.start()


def _cache_path(code: str) -> Path:
    safe_code = code.replace('.', '_')
    return CACHE_DIR / f'{safe_code}.csv'


def fetch_price_dataframe(code: str, start: str, end: str) -> pd.DataFrame:
    """直接从Wind获取单只股票前复权收盘价。"""
    ensure_wind()
    data = w.wsd(code, FIELDS, start, end, 'PriceAdj=F')  # PriceAdj=F 前复权
    if data.ErrorCode != 0:
        raise RuntimeError(f'Wind读取失败 {code} {data.ErrorCode}')
    df = pd.DataFrame({'date': data.Times, 'close': data.Data[0]})
    df['date'] = pd.to_datetime(df['date'])
    df['close'] = pd.to_numeric(df['close'], errors='coerce')
    df.dropna(subset=['close'], inplace=True)
    df.set_index('date', inplace=True)
    return df


def get_or_fetch_price(code: str, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
    """如果缓存存在则读取，否则从Wind获取并缓存。简单策略: 不做部分日期拼接，直接全区间缓存。"""
    cache_file = _cache_path(code)
    if use_cache and cache_file.exists():
        try:
            df = pd.read_csv(cache_file, parse_dates=['date'])
            df['close'] = pd.to_numeric(df['close'], errors='coerce')
            df.dropna(subset=['close'], inplace=True)
            df.set_index('date', inplace=True)
            if not df.empty and df.index.min() <= pd.to_datetime(start) and df.index.max() >= pd.to_datetime(end):
                return df.loc[(df.index >= pd.to_datetime(start)) & (df.index <= pd.to_datetime(end))].copy()
        except Exception:
            pass
    df_new = fetch_price_dataframe(code, start, end)
    if use_cache:
        df_new.reset_index().to_csv(cache_file, index=False)
    return df_new


def batch_fetch_prices(codes: List[str], start: str, end: str, use_cache: bool = True) -> Dict[str, pd.DataFrame]:
    price_dict = {}
    for c in codes:
        try:
            price_dict[c] = get_or_fetch_price(c, start, end, use_cache=use_cache)
        except Exception as e:
            print('价格获取失败', c, e)
    return price_dict


def fetch_benchmark(code: str, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
    return get_or_fetch_price(code, start, end, use_cache=use_cache)


if __name__ == '__main__':
    # 简单测试 (需Wind环境)
    if w is not None:
        ensure_wind()
        df = get_or_fetch_price('00001.HK', '2024-01-01', datetime.today().strftime('%Y-%m-%d'))
        print(df.head())

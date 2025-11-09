"""Tushare 数据访问封装（港股）。

更新点：
- 交易日历：优先使用 hk_tradecal（参考文档 https://tushare.pro/document/2?doc_id=250 ），
  回退到 trade_cal(exchange='HKEX')，再回退到简单工作日。
- 价格：使用 hk_daily_adj 获取前复权/复权日线（按单日/单标的查询），并做结果缓存；
  若获取失败则回退到占位价格（10.0）。

注意：需要先 ts.set_token(token) 然后 pro = ts.pro_api()。
"""
from datetime import date
from typing import List, Dict, Optional, Tuple
import time
import pandas as pd

try:
    import tushare as ts  # type: ignore
    TUSHARE_AVAILABLE = True
except Exception:
    TUSHARE_AVAILABLE = False
    ts = None  # type: ignore

class TushareClient:
    def __init__(self, token: Optional[str] = None, retry: int = 3, sleep: float = 1.0):
        self.retry = retry
        self.sleep = sleep
        self.started = False
        self.pro = None
        # 简单缓存：交易日与每日价格
        self._cal_cache: Dict[Tuple[str, str], List[date]] = {}
        self._price_cache: Dict[Tuple[str, str], Tuple[float, float]] = {}  # key=(YYYYMMDD, ts_code) -> (open, close)
        self._frame_cache: Dict[str, pd.DataFrame] = {}  # key=ts_code -> DataFrame(index=date, cols=[open,close])
        self._bench_cache: Dict[str, pd.DataFrame] = {}  # key=code -> DataFrame(date, close)
        if TUSHARE_AVAILABLE:
            try:
                if token:
                    ts.set_token(token)
                self.pro = ts.pro_api()
                self.started = True
            except Exception:
                self.started = False

    def _ensure(self) -> bool:
        return TUSHARE_AVAILABLE and self.started and self.pro is not None

    # --- 工具：代码归一化 ---
    @staticmethod
    def _to_ts_code(sym: str) -> str:
        """将池中代码如 '0175.HK'/'941.HK' 归一化为 Tushare 5 位格式 '00175.HK'/'00941.HK'。"""
        try:
            core, suf = sym.split('.')
            digits = ''.join(ch for ch in core if ch.isdigit())
            if len(digits) < 5:
                digits = digits.zfill(5)
            return f"{digits}.{suf.upper()}"
        except Exception:
            return sym

    @staticmethod
    def _to_pydate(s: str) -> date:
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))

    @staticmethod
    def _normalize_index_code(code: str) -> str:
        """尽力归一化指数代码到 Tushare 习惯：
        - 若形如 HSI.HK 或 ^HSI 则转为 HSI.HI（如 tushare 需要）或直接使用。
        由于 tushare 的 HK 指数接口代码格式可能不同，这里仅做最小修正；失败则原样返回。
        """
        c = str(code).upper()
        if c.endswith('.HK'):
            core = c[:-3]
            return f"{core}.HI"
        if c.startswith('^'):
            return c[1:] + '.HI'
        return c

    # --- 交易日 ---
    def get_trading_days(self, start: date, end: date) -> List[date]:
        if not self._ensure():
            # 回退：周一至周五
            days = []
            cur = start
            while cur <= end:
                if cur.weekday() < 5:
                    days.append(cur)
                cur = date.fromordinal(cur.toordinal() + 1)
            return days
        k = (start.strftime('%Y%m%d'), end.strftime('%Y%m%d'))
        if k in self._cal_cache:
            return self._cal_cache[k]
        # 优先 hk_tradecal
        for _ in range(self.retry):
            try:
                df = self.pro.hk_tradecal(start_date=k[0], end_date=k[1])
                if df is not None and not df.empty:
                    if 'is_open' in df.columns:
                        df = df[df['is_open'] == 1]
                    df = df.sort_values(df.columns[0])
                    # 支持 cal_date 或 trade_date 字段
                    date_col = 'cal_date' if 'cal_date' in df.columns else ('trade_date' if 'trade_date' in df.columns else None)
                    if date_col is not None:
                        days = [date(int(d[:4]), int(d[4:6]), int(d[6:])) for d in df[date_col]]
                        self._cal_cache[k] = days
                        return days
            except Exception:
                time.sleep(self.sleep)
        # 回退 trade_cal(exchange='HKEX')
        for _ in range(self.retry):
            try:
                df = self.pro.trade_cal(exchange='HKEX', start_date=k[0], end_date=k[1])
                if df is not None and not df.empty:
                    df = df[df['is_open'] == 1].sort_values('cal_date')
                    days = [date(int(d[:4]), int(d[4:6]), int(d[6:])) for d in df['cal_date']]
                    self._cal_cache[k] = days
                    return days
            except Exception:
                time.sleep(self.sleep)
        # 最终回退
        days = []
        cur = start
        while cur <= end:
            if cur.weekday() < 5:
                days.append(cur)
            cur = date.fromordinal(cur.toordinal() + 1)
        self._cal_cache[k] = days
        return days

    def get_next_trade_day(self, d: date) -> Optional[date]:
        days = self.get_trading_days(d, date.fromordinal(d.toordinal() + 10))
        for td in days:
            if td > d:
                return td
        return None

    def get_prev_trade_day(self, d: date) -> Optional[date]:
        days = self.get_trading_days(date.fromordinal(d.toordinal() - 10), d)
        prev = [x for x in days if x < d]
        return prev[-1] if prev else None

    # --- 价格批量预取（按标的整段日期） ---
    def prefetch_prices(self, symbols: List[str], start: date, end: date):
        if not self._ensure():
            return
        s = start.strftime('%Y%m%d')
        e = end.strftime('%Y%m%d')
        # 去重并归一化为 Tushare ts_code
        ts_codes = list({self._to_ts_code(sym) for sym in symbols})
        for ts_code in ts_codes:
            if ts_code in self._frame_cache:
                # 若已有缓存覆盖区间，跳过；简单起见直接跳过
                continue
            for _ in range(self.retry):
                try:
                    df = self.pro.hk_daily_adj(ts_code=ts_code, start_date=s, end_date=e)
                    if df is not None and not df.empty:
                        # 规范字段并以日期为索引
                        if 'trade_date' in df.columns:
                            df['date'] = pd.to_datetime(df['trade_date']).dt.date
                        elif 'cal_date' in df.columns:
                            df['date'] = pd.to_datetime(df['cal_date']).dt.date
                        else:
                            # 无日期字段则跳过
                            self._frame_cache[ts_code] = pd.DataFrame(columns=['open','close']).set_index(pd.Index([], name='date'))
                            break
                        keep = df[['date','open','close']].copy()
                        keep = keep.dropna(subset=['open','close'])
                        keep = keep.sort_values('date').set_index('date')
                        self._frame_cache[ts_code] = keep
                        break
                except Exception:
                    time.sleep(self.sleep)
            # 若仍无缓存，存入空框架，调用时会回退
            self._frame_cache.setdefault(ts_code, pd.DataFrame(columns=['open','close']).set_index(pd.Index([], name='date')))

    def _get_from_frame(self, trade_day: date, ts_code: str) -> Tuple[Optional[float], Optional[float]]:
        df = self._frame_cache.get(ts_code)
        if df is None or df.empty:
            return None, None
        # 直接取当日，否则取上一个可用交易日（向下取最近日期）
        if trade_day in df.index:
            row = df.loc[trade_day]
            return float(row['open']), float(row['close'])
        # 找到 <= trade_day 的最后一个日期
        lesser = df.index[df.index <= trade_day]
        if len(lesser) == 0:
            return None, None
        last_day = max(lesser)
        row = df.loc[last_day]
        return float(row['open']), float(row['close'])

    def _get_exact_from_frame(self, trade_day: date, ts_code: str) -> Tuple[Optional[float], Optional[float]]:
        """仅当日精确匹配，用于成交价（禁止用前一日回带影响交易）。"""
        df = self._frame_cache.get(ts_code)
        if df is None or df.empty:
            return None, None
        if trade_day in df.index:
            row = df.loc[trade_day]
            return float(row['open']), float(row['close'])
        return None, None

    # --- 价格（hk_daily_adj，逐标的按日查询，带缓存） ---
    def _fetch_adj_ohlc(self, trade_day: date, ts_code: str) -> Tuple[Optional[float], Optional[float]]:
        d = trade_day.strftime('%Y%m%d')
        key = (d, ts_code)
        if key in self._price_cache:
            return self._price_cache[key]
        if not self._ensure():
            self._price_cache[key] = (10.0, 10.0)
            return (10.0, 10.0)
        open_p, close_p = None, None
        for _ in range(self.retry):
            try:
                df = self.pro.hk_daily_adj(ts_code=ts_code, start_date=d, end_date=d)
                if df is not None and not df.empty:
                    row = df.iloc[0]
                    # 字段名按 tushare 约定：open/close
                    if row.get('open') is not None:
                        open_p = float(row['open'])
                    if row.get('close') is not None:
                        close_p = float(row['close'])
                    break
            except Exception:
                time.sleep(self.sleep)
        # 缓存真实结果或 None，占位仅在 _ensure() 为 False 时使用
        self._price_cache[key] = (open_p, close_p)
        return (open_p, close_p)

    def get_open_prices(self, trade_day: date, symbols: List[str], field: str = 'OPEN', adj: str = '') -> Dict[str, Optional[float]]:
        prices: Dict[str, Optional[float]] = {}
        for s in symbols:
            ts_code = self._to_ts_code(s)
            # 对成交价，只允许当日精确数据；若没有则尝试单日接口；仍无则返回 None（跳过交易）
            o, _ = self._get_exact_from_frame(trade_day, ts_code)
            if o is None:
                o, _ = self._fetch_adj_ohlc(trade_day, ts_code)
            prices[s] = o if o is not None else None
        return prices

    def get_close_prices(self, trade_day: date, symbols: List[str], field: str = 'CLOSE', adj: str = '') -> Dict[str, float]:
        prices: Dict[str, float] = {}
        for s in symbols:
            ts_code = self._to_ts_code(s)
            o, c = self._get_from_frame(trade_day, ts_code)
            if c is None:
                o, c = self._fetch_adj_ohlc(trade_day, ts_code)
            prices[s] = c if c is not None else 10.0
        return prices

    # --- 指数收盘序列 ---
    def get_index_close_series(self, code: str, start: date, end: date) -> Optional[pd.DataFrame]:
        """返回列: date, close。优先 hk_index_daily；失败则尝试 index_daily。
        若接口/代码不适配则返回空 DataFrame。
        """
        if not self._ensure():
            return None
        k = f"{code}_{start:%Y%m%d}_{end:%Y%m%d}"
        if k in self._bench_cache:
            return self._bench_cache[k]
        s = start.strftime('%Y%m%d')
        e = end.strftime('%Y%m%d')
        # 可能的代码归一化
        candidates = [code, self._normalize_index_code(code)]
        for cand in candidates:
            # 1) hk_index_daily（若可用）
            for _ in range(self.retry):
                try:
                    if hasattr(self.pro, 'hk_index_daily'):
                        df = self.pro.hk_index_daily(ts_code=cand, start_date=s, end_date=e)
                        if df is not None and not df.empty:
                            out = df.copy()
                            date_col = 'trade_date' if 'trade_date' in out.columns else ('cal_date' if 'cal_date' in out.columns else None)
                            if date_col is None:
                                continue
                            out['date'] = pd.to_datetime(out[date_col]).dt.date
                            if 'close' not in out.columns and 'close_price' in out.columns:
                                out.rename(columns={'close_price': 'close'}, inplace=True)
                            keep = out[['date', 'close']].dropna().sort_values('date').reset_index(drop=True)
                            self._bench_cache[k] = keep
                            return keep
                except Exception:
                    time.sleep(self.sleep)
            # 2) index_daily（大陆指数，做兜底）
            for _ in range(self.retry):
                try:
                    df2 = self.pro.index_daily(ts_code=cand, start_date=s, end_date=e)
                    if df2 is not None and not df2.empty:
                        out = df2.copy()
                        out['date'] = pd.to_datetime(out['trade_date']).dt.date
                        keep = out[['date', 'close']].dropna().sort_values('date').reset_index(drop=True)
                        self._bench_cache[k] = keep
                        return keep
                except Exception:
                    time.sleep(self.sleep)
        # 失败返回空
        self._bench_cache[k] = pd.DataFrame(columns=['date', 'close'])
        return self._bench_cache[k]

"""Wind 数据访问封装。

说明：
- 需安装并登录 Wind 终端并具备 WindPy 环境 (通常: from WindPy import w).
- 这里使用 try/except 以便在 Wind 不可用时回退到占位逻辑。
- 实际使用时可扩展缓存、批量下载与异常分类处理。
"""
from datetime import date, datetime
from typing import List, Dict, Optional
import time

try:
    from WindPy import w  # type: ignore
    WIND_AVAILABLE = True
except Exception:
    WIND_AVAILABLE = False

class WindClient:
    def __init__(self, retry: int = 3, sleep: float = 1.0):
        self.retry = retry
        self.sleep = sleep
        self.started = False
        if WIND_AVAILABLE:
            try:
                w.start()
                self.started = True
            except Exception:
                self.started = False

    def _ensure(self) -> bool:
        return WIND_AVAILABLE and self.started

    def get_trading_days(self, start: date, end: date) -> List[date]:
        if not self._ensure():
            # 回退：简单周一至周五
            days = []
            cur = start
            while cur <= end:
                if cur.weekday() < 5:
                    days.append(cur)
                cur = cur.fromordinal(cur.toordinal() + 1)
            return days
        # Wind tdays 接口
        for _ in range(self.retry):
            try:
                r = w.tdays(start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d'))
                return [x.date() for x in r.Data[0]]
            except Exception:
                time.sleep(self.sleep)
        return []

    def get_next_trade_day(self, d: date) -> Optional[date]:
        # 使用 tdays 获取 d+1 至 d+10 范围并取第一个大于 d 的
        days = self.get_trading_days(d, date.fromordinal(d.toordinal() + 10))
        for td in days:
            if td > d:
                return td
        return None

    def get_prev_trade_day(self, d: date) -> Optional[date]:
        days = self.get_trading_days(date.fromordinal(d.toordinal() - 10), d)
        prev = [x for x in days if x < d]
        return prev[-1] if prev else None

    def get_open_prices(self, trade_day: date, symbols: List[str], field: str = 'OPEN', adj: str = '') -> Dict[str, float]:
        if not self._ensure():
            return {s: 10.0 for s in symbols}
        prices: Dict[str, float] = {}
        query_day = trade_day.strftime('%Y-%m-%d')
        for _ in range(self.retry):
            try:
                r = w.wss(symbols, field, f"tradeDate={query_day};priceAdj={adj}")
                for i, sym in enumerate(symbols):
                    val = r.Data[0][i]
                    if val is None:
                        continue
                    prices[sym] = float(val)
                break
            except Exception:
                time.sleep(self.sleep)
        # 缺失填充
        for s in symbols:
            prices.setdefault(s, 10.0)
        return prices

    def get_close_prices(self, trade_day: date, symbols: List[str], field: str = 'CLOSE', adj: str = '') -> Dict[str, float]:
        if not self._ensure():
            return {s: 10.0 for s in symbols}
        prices: Dict[str, float] = {}
        query_day = trade_day.strftime('%Y-%m-%d')
        for _ in range(self.retry):
            try:
                r = w.wss(symbols, field, f"tradeDate={query_day};priceAdj={adj}")
                for i, sym in enumerate(symbols):
                    val = r.Data[0][i]
                    if val is None:
                        continue
                    prices[sym] = float(val)
                break
            except Exception:
                time.sleep(self.sleep)
        for s in symbols:
            prices.setdefault(s, 10.0)
        return prices

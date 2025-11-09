from datetime import date, timedelta
from typing import List, Optional

class TradingCalendar:
    """统一使用 data_client (可为 TushareClient) 提供交易日；若不可用则回退周一至周五。"""
    def __init__(self, market: str = 'HKEX', data_client=None):
        self.market = market
        self.data_client = data_client

    def _weekday_days(self, start: date, end: date) -> List[date]:
        days: List[date] = []
        cur = start
        while cur <= end:
            if cur.weekday() < 5:
                days.append(cur)
            cur = cur + timedelta(days=1)
        return days

    def is_trade_day(self, d: date) -> bool:
        if self.data_client is not None:
            days = self.data_client.get_trading_days(d, d)
            if not days:
                days = self._weekday_days(d, d)
            return len(days) == 1 and days[0] == d
        return d.weekday() < 5

    def next_trade_day(self, d: date) -> Optional[date]:
        if d is None:
            return None
        if self.data_client is not None:
            nd = self.data_client.get_next_trade_day(d)
            if nd is not None:
                return nd
        cur = d
        for _ in range(366):
            cur = cur + timedelta(days=1)
            if self.is_trade_day(cur):
                return cur
        return None

    def prev_trade_day(self, d: date) -> Optional[date]:
        if d is None:
            return None
        if self.data_client is not None:
            pd = self.data_client.get_prev_trade_day(d)
            if pd is not None:
                return pd
        cur = d
        for _ in range(366):
            cur = cur - timedelta(days=1)
            if self.is_trade_day(cur):
                return cur
        return None

    def trade_days_between(self, start: date, end: date) -> List[date]:
        if self.data_client is not None:
            days = self.data_client.get_trading_days(start, end)
            if not days:
                days = self._weekday_days(start, end)
            return days
        return self._weekday_days(start, end)

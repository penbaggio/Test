from typing import Dict, List, Tuple
from datetime import date
from .portfolio import Portfolio

class Rebalancer:
    def __init__(self, fee_buy: float=0.004, fee_sell: float=0.004, min_trade_ratio: float=0.005, lot_size: int=1, price_mode: str='next_open', data_client=None, open_field: str='OPEN', close_field: str='CLOSE', adj: str=''):
        self.fee_buy = fee_buy
        self.fee_sell = fee_sell
        self.min_trade_ratio = min_trade_ratio
        self.lot_size = lot_size
        self.price_mode = price_mode
        self.data_client = data_client
        self.open_field = open_field
        self.close_field = close_field
        self.adj = adj
        self.last_diag: Dict[str, int] = {}

    # -------- 价格占位接口 --------
    def get_prices(self, trade_day: date, symbols: List[str]) -> Dict[str, float]:
        # 价格获取：若有数据客户端则取开盘价，否则回退到占位常数
        if self.data_client is not None:
            return self.data_client.get_open_prices(trade_day, symbols, self.open_field, self.adj)
        return {s: 10.0 for s in symbols}

    def get_all_positions_prices(self, trade_day: date, symbols: List[str]) -> Dict[str, float]:
        if self.data_client is not None:
            return self.data_client.get_close_prices(trade_day, symbols, self.close_field, self.adj)
        return {s: 10.0 for s in symbols}

    # -------- 再平衡逻辑 --------
    def rebalance(self, trade_day: date, target_symbols: List[str], prices: Dict[str, float], portfolio: Portfolio) -> List[Tuple]:
        trades: List[Tuple] = []
        # 诊断计数
        diag = {
            'target_count': len(target_symbols),
            'tradable_targets': 0,
            'locked_targets': 0,
            'locked_sells': 0,
            'buys': 0,
            'sells': 0,
            'locked_targets_list': [],
            'locked_sells_list': [],
        }

        # 前瞻性校正：使用前一交易日收盘价评估组合总值（不使用当日收盘）
        pv_prices: Dict[str, float] = {}
        if getattr(self, 'data_client', None) is not None:
            prev_day = self.data_client.get_prev_trade_day(trade_day)
            union_syms = list(set(list(portfolio.positions.keys()) + list(target_symbols)))
            if prev_day is not None:
                try:
                    pv_prices = self.data_client.get_close_prices(prev_day, union_syms)
                except Exception:
                    pv_prices = {}
        # 若无数据客户端或获取失败，则退回用当日可用开盘价估值
        if not pv_prices:
            pv_prices = {s: p for s, p in prices.items() if p is not None}
        pv = portfolio.total_value(pv_prices)

        # 确定当日可交易目标（有开盘价且>0）与锁定集合（缺开盘价）
        tradable_targets = [s for s in target_symbols if prices.get(s) is not None and prices.get(s, 0) > 0]
        locked_targets = [s for s in target_symbols if s not in tradable_targets]
        diag['tradable_targets'] = len(tradable_targets)
        diag['locked_targets'] = len(locked_targets)
        diag['locked_targets_list'] = list(locked_targets)

        # 需要卖出的非目标集股票，但若无开盘价则延迟卖出（锁定）
        locked_sells_set = set()
        for sym in list(portfolio.positions.keys()):
            if sym not in target_symbols:
                price = prices.get(sym)
                if price is None or price <= 0:
                    locked_sells_set.add(sym)
        diag['locked_sells'] = len(locked_sells_set)
        diag['locked_sells_list'] = list(locked_sells_set)

        # 计算锁定部分（无法交易的目标内与应卖未卖者）当前价值，用于从 pv 中扣除，避免对可交易目标过度分配
        def cur_val(sym: str) -> float:
            qty = portfolio.positions.get(sym, 0)
            price = pv_prices.get(sym, None)
            return qty * price if price is not None else 0.0

        locked_value = sum(cur_val(s) for s in locked_targets) + sum(cur_val(s) for s in locked_sells_set)
        pv_for_allocation = max(pv - locked_value, 0.0)
        N = max(len(tradable_targets), 1)
        target_val_each = pv_for_allocation / N

        # 1) 先卖出不在目标集的股票
        for sym in list(portfolio.positions.keys()):
            if sym not in target_symbols:
                qty = portfolio.positions[sym]
                price = prices.get(sym)
                if price is None:
                    continue
                value = qty * price
                cost = value * self.fee_sell
                portfolio.cash += value - cost
                trades.append((trade_day, 'SELL', sym, qty, price, cost))
                diag['sells'] += 1
                del portfolio.positions[sym]

        # 2) 针对目标集内的股票，计算差额并买卖以趋近等权
        for sym in tradable_targets:
            price = prices.get(sym)
            if price is None or price <= 0:
                continue
            cur_qty = portfolio.positions.get(sym, 0)
            cur_val = cur_qty * price
            diff_val = target_val_each - cur_val

            # 微调阈值：若差额占目标值小于阈值，则跳过
            if abs(diff_val) < target_val_each * self.min_trade_ratio:
                continue

            # 买入
            if diff_val > 0:
                buy_qty = int((diff_val / price) // self.lot_size * self.lot_size)
                if buy_qty <= 0:
                    continue
                est_cost = buy_qty * price * self.fee_buy
                total_cash_need = buy_qty * price + est_cost
                if total_cash_need > portfolio.cash:
                    # 按现金缩放
                    buy_qty = int((portfolio.cash / (price * (1 + self.fee_buy))) // self.lot_size * self.lot_size)
                    if buy_qty <= 0:
                        continue
                    est_cost = buy_qty * price * self.fee_buy
                    total_cash_need = buy_qty * price + est_cost
                portfolio.cash -= total_cash_need
                portfolio.positions[sym] = portfolio.positions.get(sym, 0) + buy_qty
                trades.append((trade_day, 'BUY', sym, buy_qty, price, est_cost))
                diag['buys'] += 1

            # 卖出
            else:
                sell_qty = int(((-diff_val) / price) // self.lot_size * self.lot_size)
                sell_qty = min(sell_qty, cur_qty)
                if sell_qty <= 0:
                    continue
                value = sell_qty * price
                cost = value * self.fee_sell
                portfolio.cash += value - cost
                portfolio.positions[sym] = cur_qty - sell_qty
                trades.append((trade_day, 'SELL', sym, sell_qty, price, cost))
                diag['sells'] += 1

        self.last_diag = diag
        return trades

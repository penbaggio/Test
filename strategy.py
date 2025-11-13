import backtrader as bt
import pandas as pd
from typing import Dict, List

class MultiFactorStrategy(bt.Strategy):
    params = dict(
        factor_df=None,            # pandas DataFrame 因子数据（已标准化代码）
        rebalance_dates=None,      # list[pd.Timestamp]
        portfolio_map=None,        # dict[rebalance_date -> list[codes]]
        code_to_data=None,         # dict[code -> datafeed]
        benchmark_data=None,       # benchmark feed
        commission_rate=0.002      # 单边0.2%
    )

    def __init__(self):
        # 设置手续费
        self.broker.setcommission(commission=self.p.commission_rate)
        # 建立代码到 data 的映射
        self.datas_code = {}
        for d in self.datas:
            if hasattr(d, 'p') and hasattr(d.p, 'code'):
                self.datas_code[d.p.code] = d
        self.rebalance_dates_set = set([pd.Timestamp(d) for d in self.p.rebalance_dates])
        self.last_rebalance_date = None
        self.order_refs = []

    def log(self, txt):
        dt = self.datas[0].datetime.date(0)
        print(f'{dt} {txt}')

    def next(self):
        current_dt = pd.Timestamp(self.datas[0].datetime.date(0))
        # 回测结束时间控制在外部 cerebro.run()

        if current_dt in self.rebalance_dates_set:
            self.rebalance(current_dt)

    def rebalance(self, current_dt: pd.Timestamp):
        # 使用上一交易日的前复权收盘价做权重基准
        # 获取上一交易日日期 (需要数据中前一个 bar 存在)
        prev_dt = None
        if len(self.datas[0]) >= 2:
            prev_dt = pd.Timestamp(self.datas[0].datetime.date(-1))
        else:
            prev_dt = current_dt
        target_codes: List[str] = self.p.portfolio_map.get(current_dt, [])
        if not target_codes:
            self.log('调仓日无选股数据, 跳过')
            return
        # 计算当前持仓与目标
        # 先全部平仓不在目标中的
        for position in self.broker.positions:
            pass
        current_positions = {data._name: self.getposition(data) for data in self.datas if self.getposition(data)}
        # 平掉不在目标中的持仓
        for code, pos in current_positions.items():
            if code not in target_codes and pos.size != 0:
                self.close(self.datas_code[code])
        # 计算上一日收盘价的等权权重资金分配
        total_value = self.broker.getvalue()
        target_weight = 1.0 / len(target_codes)
        alloc_value_each = total_value * target_weight
        for code in target_codes:
            data = self.datas_code.get(code)
            if data is None:
                continue
            # 上一日收盘价
            price = data.close[0]
            if len(data) >= 2:
                price_prev = data.close[-1]
            else:
                price_prev = price
            # 使用上一交易日价格计算目标股数
            size = int(alloc_value_each / price_prev)
            if size <= 0:
                continue
            pos = self.getposition(data)
            current_size = pos.size if pos else 0
            delta = size - current_size
            if delta > 0:
                self.buy(data=data, size=delta)
            elif delta < 0:
                self.sell(data=data, size=abs(delta))
        self.last_rebalance_date = current_dt
        self.log(f'调仓完成: {current_dt.date()} 目标数 {len(target_codes)}')

    def stop(self):
        self.log('策略结束')

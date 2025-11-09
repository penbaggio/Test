from dataclasses import dataclass, field
from typing import Dict

@dataclass
class Portfolio:
    initial_cash: float
    cash: float = None
    positions: Dict[str, int] = field(default_factory=dict)

    def __post_init__(self):
        if self.cash is None:
            self.cash = self.initial_cash

    def total_value(self, prices: Dict[str, float]) -> float:
        pos_val = 0.0
        for sym, qty in self.positions.items():
            price = prices.get(sym)
            if price is not None:
                pos_val += qty * price
        return pos_val + self.cash

# -*- coding: utf-8 -*-
"""
因子配置模块
============
定义所有因子的配置参数，包括名称、方向、数据来源、计算参数等
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class FactorSource(Enum):
    """因子数据来源"""
    PROVIDED = "provided"      # 原始数据已提供
    CALCULATED = "calculated"  # 需要从Tushare计算


class FactorCategory(Enum):
    """因子类别"""
    VALUE = "value"          # 价值因子
    QUALITY = "quality"      # 质量因子
    MOMENTUM = "momentum"    # 动量因子
    VOLATILITY = "volatility"  # 波动率因子
    EVENT = "event"          # 事件因子


@dataclass
class FactorConfig:
    """
    因子配置类
    
    Attributes:
        name: 因子名称
        direction: 因子方向 (+1: 值越大越好, -1: 值越小越好)
        source: 数据来源
        category: 因子类别
        description: 因子描述
        column_name: 在数据中的列名（如果与name不同）
        calc_params: 计算参数
        enabled: 是否启用
    """
    name: str
    direction: int = 1
    source: FactorSource = FactorSource.PROVIDED
    category: FactorCategory = FactorCategory.VALUE
    description: str = ""
    column_name: Optional[str] = None
    calc_params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    
    def __post_init__(self):
        if self.column_name is None:
            self.column_name = self.name
        if self.direction not in (-1, 1):
            raise ValueError(f"direction must be -1 or 1, got {self.direction}")
    
    @property
    def is_calculated(self) -> bool:
        """是否需要计算"""
        return self.source == FactorSource.CALCULATED
    
    @property
    def is_provided(self) -> bool:
        """是否已提供"""
        return self.source == FactorSource.PROVIDED


# ============================================================================
# 因子配置定义
# ============================================================================

# 市净率因子
PB_RATIO = FactorConfig(
    name="市净率",
    direction=1,  # 根据实际IC方向调整为正
    source=FactorSource.CALCULATED,
    category=FactorCategory.VALUE,
    description="市净率 = 调仓日总市值 / 报告期末净资产（归属母公司股东权益）",
    column_name="市净率",
)

# 经营活动现金流量净额占比因子
CASHFLOW_RATIO = FactorConfig(
    name="经营活动现金流量净额占比",
    direction=1,  # 正向：现金流占比越高越好
    source=FactorSource.CALCULATED,
    category=FactorCategory.QUALITY,
    description="经营活动现金流量净额 / 总资产",
    column_name="经营活动现金流量净额占比",
)

# 单季度ROE同比因子
ROE_YOY = FactorConfig(
    name="单季度ROE同比",
    direction=1,  # 正向：ROE同比增长越高越好
    source=FactorSource.CALCULATED,
    category=FactorCategory.QUALITY,
    description="单季度ROE与去年同期的同比变化",
    column_name="单季度ROE同比",
)

# 日收益波动率因子
VOLATILITY = FactorConfig(
    name="日收益波动率",
    direction=1,  # 根据实际IC方向调整为正
    source=FactorSource.CALCULATED,
    category=FactorCategory.VOLATILITY,
    description="过去60个交易日收益率的标准差",
    column_name="日收益波动率",
    calc_params={
        "window": 60,  # 回溯窗口（交易日）
    }
)

# 盈余公告跳空超额因子
EARNINGS_GAP = FactorConfig(
    name="盈余公告跳空超额",
    direction=1,  # 正向：超额收益越高越好
    source=FactorSource.CALCULATED,
    category=FactorCategory.EVENT,
    description="盈余公告次日开盘价/昨日收盘价 - 中证500指数次日开盘价/昨日收盘价",
    column_name="盈余公告跳空超额",
    calc_params={
        "benchmark": "000905.SH",  # 基准指数：中证500
    }
)

# 剥离涨停动量因子
MOMENTUM_EX_LIMIT = FactorConfig(
    name="剥离涨停动量",
    direction=1,  # 根据实际IC方向调整为正（动量正向有效）
    source=FactorSource.CALCULATED,
    category=FactorCategory.MOMENTUM,
    description="过去260-20日区间内，剔除涨停日后的累计收益",
    column_name="剥离涨停动量",
    calc_params={
        "start_offset": 260,  # 起始偏移（交易日前）
        "end_offset": 20,     # 结束偏移（交易日前）
    }
)


# ============================================================================
# 因子配置集合
# ============================================================================

# 所有因子配置
FACTOR_CONFIGS: Dict[str, FactorConfig] = {
    "市净率": PB_RATIO,
    "经营活动现金流量净额占比": CASHFLOW_RATIO,
    "单季度ROE同比": ROE_YOY,
    "日收益波动率": VOLATILITY,
    "盈余公告跳空超额": EARNINGS_GAP,
    "剥离涨停动量": MOMENTUM_EX_LIMIT,
}

# 原始提供的因子
PROVIDED_FACTORS: List[str] = [
    name for name, config in FACTOR_CONFIGS.items() 
    if config.is_provided
]

# 需要计算的因子
CALCULATED_FACTORS: List[str] = [
    name for name, config in FACTOR_CONFIGS.items() 
    if config.is_calculated
]

# 启用的因子
ENABLED_FACTORS: List[str] = [
    name for name, config in FACTOR_CONFIGS.items() 
    if config.enabled
]


def get_factor_config(name: str) -> FactorConfig:
    """获取因子配置"""
    if name not in FACTOR_CONFIGS:
        raise ValueError(f"Unknown factor: {name}")
    return FACTOR_CONFIGS[name]


def get_factor_directions() -> Dict[str, int]:
    """获取所有因子方向"""
    return {name: config.direction for name, config in FACTOR_CONFIGS.items()}


def get_enabled_factor_configs() -> Dict[str, FactorConfig]:
    """获取所有启用的因子配置"""
    return {
        name: config for name, config in FACTOR_CONFIGS.items() 
        if config.enabled
    }


# ============================================================================
# 全局配置
# ============================================================================

# Tushare API配置
TUSHARE_TOKEN = "98b2900883e70c8b1e141fdb33e4a5a1123dc999d217fcd2c0ce4c89"

# 数据缓存配置
CACHE_DIR = "data_cache"
CACHE_ENABLED = True
CACHE_EXPIRE_DAYS = 7

# RankICIR计算配置
RANKICIR_CONFIG = {
    "rolling_window": 12,      # 滚动窗口期数
    "min_periods": 6,          # 最小期数要求
    "return_periods": 1,       # 收益率期数（月）
}

# 数据路径配置
DATA_PATHS = {
    "input_file": "表1-回测股票池因子.csv",
    "output_file": "表1-回测股票池因子_新增.csv",
    "composite_file": "表2-复合因子结果.csv",
    "rankic_file": "表3-RankIC时间序列.csv",
    "rankicir_file": "表4-RankICIR时间序列.csv",
    "weights_file": "表5-因子权重时间序列.csv",
}

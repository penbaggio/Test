# -*- coding: utf-8 -*-
"""
因子模块
========
用于ROE高质量选股策略的因子计算、分析和回测

模块结构:
- config: 因子配置
- loader: 数据加载
- calculator: 因子计算
- preprocessor: 因子预处理
- analyzer: 因子分析
- utils: 工具函数
"""

from .config import FactorConfig, FACTOR_CONFIGS
from .loader import DataLoader
from .calculator import FactorCalculator
from .preprocessor import FactorPreprocessor
from .analyzer import FactorAnalyzer

__all__ = [
    'FactorConfig',
    'FACTOR_CONFIGS',
    'DataLoader',
    'FactorCalculator',
    'FactorPreprocessor',
    'FactorAnalyzer',
]

__version__ = '1.0.0'

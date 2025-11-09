# 港股通月度等权回测骨架

该目录提供一个最小化的“月度换仓 + 下一交易日开盘价成交 + 双边千四费率”回测骨架。价格与交易日历均为占位逻辑，需要接入 Wind。

## 结构
```
backtest/
  config.yaml        # 参数配置
  main.py            # 主程序入口
  core/
    loader.py        # 股票池 CSV 读取
    calendar.py      # 交易日历占位实现（需替换）
    portfolio.py     # 组合对象：仓位与现金
    executor.py      # 再平衡逻辑，含费率与微调阈值
    metrics.py       # 基础绩效指标
  output/            # 运行后输出 nav_curve.csv、trades.csv、metrics_basic.json、metrics_with_benchmark.json、benchmark_nav.csv
```

## 使用步骤
1. 确认 `config.yaml` 中 `pool_csv` 路径指向股票池文件。
2. 接入真实 Wind 行情：修改 `executor.py` 中 `get_prices` 和 `get_all_positions_prices` 方法，返回指定交易日开盘/收盘或前复权价格。
3. 接入交易日历：替换 `calendar.py` 的 `is_trade_day`、`next_trade_day` 等方法为 Wind 交易日数据。
4. 在命令行运行：
```powershell
python .\backtest\main.py
```
5. 查看结果：
  - `backtest/output/nav_curve.csv`（组合日度净值）
  - `backtest/output/trades.csv`（交易明细）
  - `backtest/output/metrics_basic.json`（基础指标）
  - `backtest/output/benchmark_nav.csv`（基准净值）
  - `backtest/output/metrics_with_benchmark.json`（与基准对比指标）
  - 日志：`backtest/output/logs/backtest.log`

## 核心参数
- initial_capital：初始资金规模
- fee_rate_buy / fee_rate_sell：买卖单边费率（双边千四=0.004）
- min_trade_ratio：低于该相对差额不微调，降低换手与成本
- price_mode：目前占位，仅支持 next_open，实际可扩展

## 再平衡逻辑简述
- 对不在当期目标集的股票全部卖出。
- 对目标集按组合当前总值进行等权分配，忽略微小差额（受 min_trade_ratio 控制）。
- 买卖均按下一交易日开盘价成交，扣除双边千四费用。
- 持仓市值 + 现金形成每日净值，输出净值曲线并计算基础指标（累计收益、年化收益、年化波动、Sharpe、最大回撤）。

## 待接入与扩展
- Wind 行情：支持前复权开盘、收盘、停牌、除权处理。
- 手续费拆分：佣金、印花税、交易征费。
- 行业与因子归因：新增模块 `attribution.py`。
- 滑点模型：按成交额占比或盘口差额估算冲击成本。
- Benchmark：引入港股通指数（H50069.CSI）日度净值，计算相对指标（信息比率、Alpha、Beta、相关性）。
  - 更换基准：修改 `config.yaml` 中的 `benchmark_code`（例如 `HSCEI.HI` 或其他 Tushare 指数代码）。

## 风险提示
当前价格与日历均为占位，回测结果仅用于验证流程，不代表真实绩效。接入真实数据后需重新校验再平衡与成本计算。

## 下一步建议
- 替换价格与日历接口
- 增加日志与异常处理（停牌、缺失价格）
- 写单元测试：验证换仓与成本计算公式

如需我直接帮你接入 Wind 或补充测试样例，请继续说明需求。

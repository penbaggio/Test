import pandas as pd
import backtrader as bt
import matplotlib.pyplot as plt
from factor_loader import load_factor_data, compute_rebalance_dates, select_portfolio
from wind_data import batch_fetch_prices, fetch_benchmark
from strategy import MultiFactorStrategy

START_DATE = '2015-01-01'
END_DATE = '2025-08-26'
BENCHMARK_CODE = '881005.WI'


def prepare_portfolios(df_factor: pd.DataFrame, rebalance_dates):
    portfolio_map = {}
    for d in rebalance_dates:
        codes = select_portfolio(df_factor, d)
        portfolio_map[pd.Timestamp(d)] = codes
    return portfolio_map


def run_backtest():
    df_factor = load_factor_data()
    rebalance_dates = compute_rebalance_dates(df_factor, START_DATE, END_DATE)
    portfolio_map = prepare_portfolios(df_factor, rebalance_dates)
    # 汇总所有需要的股票代码
    all_codes = sorted({c for codes in portfolio_map.values() for c in codes})
    # Wind 获取价格数据
    price_dict = batch_fetch_prices(all_codes, START_DATE, END_DATE, use_cache=True)
    benchmark_df = fetch_benchmark(BENCHMARK_CODE, START_DATE, END_DATE, use_cache=True)

    cerebro = bt.Cerebro()
    # 添加股票数据
    for code, dfp in price_dict.items():
        if dfp.empty:
            continue
        # 补齐 Backtrader 所需列
        df_full = dfp.copy()
        for col in ['open', 'high', 'low']:
            if col not in df_full.columns:
                df_full[col] = df_full['close']
        if 'volume' not in df_full.columns:
            df_full['volume'] = 0
        if 'openinterest' not in df_full.columns:
            df_full['openinterest'] = 0
        data = bt.feeds.PandasData(dataname=df_full, name=code)
        data.p.code = code  # 动态属性
        cerebro.adddata(data)
    # 添加基准(可作为额外数据)
    bench_df_full = benchmark_df.copy()
    for col in ['open', 'high', 'low']:
        if col not in bench_df_full.columns:
            bench_df_full[col] = bench_df_full['close']
    if 'volume' not in bench_df_full.columns:
        bench_df_full['volume'] = 0
    if 'openinterest' not in bench_df_full.columns:
        bench_df_full['openinterest'] = 0
    bench_data = bt.feeds.PandasData(dataname=bench_df_full, name='BENCH')
    bench_data.p.code = 'BENCH'
    cerebro.adddata(bench_data)

    cerebro.addstrategy(MultiFactorStrategy,
                        factor_df=df_factor,
                        rebalance_dates=rebalance_dates,
                        portfolio_map=portfolio_map,
                        commission_rate=0.002)
    # 添加分析器: 日度收益、回撤、夏普(需风险自由利率设置, 这里使用默认)
    cerebro.addanalyzer(bt.analyzers.TimeReturn, _name='timereturn', timeframe=bt.TimeFrame.Days)
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe', timeframe=bt.TimeFrame.Days)

    cerebro.broker.setcash(10_000_000)  # 初始资金 1000万
    # 运行
    results = cerebro.run()
    strat = results[0]
    final_value = cerebro.broker.getvalue()
    print('最终组合净值:', final_value)
    # 绩效指标输出
    tr = strat.analyzers.timereturn.get_analysis()
    dd = strat.analyzers.drawdown.get_analysis()
    sharpe = strat.analyzers.sharpe.get_analysis()
    print('最大回撤%:', dd.get('maxdrawdown'))
    print('最大回撤资金:', dd.get('maxmoneydrawdown'))
    print('夏普比率:', sharpe.get('sharperatio'))

    # 净值曲线 (组合 vs 基准)
    port_series = pd.Series(tr).sort_index()
    port_equity = (1 + port_series).cumprod()
    bench_ret = benchmark_df['close'].pct_change().fillna(0)
    bench_equity = (1 + bench_ret).cumprod()
    # 对齐日期
    combined = pd.DataFrame({'Portfolio': port_equity, 'Benchmark': bench_equity})
    combined.dropna(how='all', inplace=True)
    plt.figure(figsize=(10, 5))
    combined.plot(ax=plt.gca())
    plt.title('组合 vs 基准 净值曲线')
    plt.ylabel('净值')
    plt.tight_layout()
    plt.savefig('equity_curve.png')
    print('净值曲线保存为 equity_curve.png')


if __name__ == '__main__':
    run_backtest()

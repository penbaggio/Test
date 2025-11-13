import pandas as pd
import backtrader as bt
import matplotlib.pyplot as plt
import math
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
    price_dict = batch_fetch_prices(all_codes, START_DATE, END_DATE, use_cache=False)
    benchmark_df = fetch_benchmark(BENCHMARK_CODE, START_DATE, END_DATE, use_cache=False)

    cerebro = bt.Cerebro()
    # 添加股票数据
    for code, dfp in price_dict.items():
        if dfp.empty:
            continue
        # 补齐 Backtrader 所需列并使用默认的大小写列名
        df_full = dfp.copy()
        df_full.rename(columns={'close': 'Close'}, inplace=True)
        for src, dst in [('Close','Open'), ('Close','High'), ('Close','Low')]:
            if dst not in df_full.columns:
                df_full[dst] = df_full[src]
        if 'Volume' not in df_full.columns:
            df_full['Volume'] = 0
        if 'OpenInterest' not in df_full.columns:
            df_full['OpenInterest'] = 0
        data = bt.feeds.PandasData(dataname=df_full, name=code)
        data.p.code = code  # 动态属性
        cerebro.adddata(data)
    # 添加基准(可作为额外数据)
    bench_df_full = benchmark_df.copy()
    bench_df_full.rename(columns={'close': 'Close'}, inplace=True)
    for src, dst in [('Close','Open'), ('Close','High'), ('Close','Low')]:
        if dst not in bench_df_full.columns:
            bench_df_full[dst] = bench_df_full[src]
    if 'Volume' not in bench_df_full.columns:
        bench_df_full['Volume'] = 0
    if 'OpenInterest' not in bench_df_full.columns:
        bench_df_full['OpenInterest'] = 0
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
    initial_cash = 10_000_000
    print('最终组合净值:', final_value)
    # 绩效指标输出
    tr = strat.analyzers.timereturn.get_analysis()
    dd = strat.analyzers.drawdown.get_analysis()
    sharpe = strat.analyzers.sharpe.get_analysis()
    # 如果 analyzer 返回 None，手动计算最大回撤
    max_dd_pct = dd.get('maxdrawdown')
    max_dd_money = dd.get('maxmoneydrawdown')
    port_series = pd.Series(tr).sort_index()
    port_equity = (1 + port_series).cumprod()
    if max_dd_pct is None or max_dd_money is None:
        rolling_max = port_equity.cummax()
        drawdowns = port_equity / rolling_max - 1.0
        max_dd_pct = drawdowns.min() * 100.0 if not drawdowns.empty else None
        max_dd_money = (port_equity.min() - rolling_max[drawdowns.idxmin()]) * initial_cash if not drawdowns.empty else None
    # 年化收益与波动率
    if not port_series.empty:
        total_days = (port_series.index[-1] - port_series.index[0]).days + 1
        years = total_days / 365.25
        cagr = (final_value / initial_cash)**(1/years) - 1 if years > 0 else None
        daily_vol = port_series.std()
        ann_vol = daily_vol * math.sqrt(252) if daily_vol is not None else None
        manual_sharpe = (cagr / ann_vol) if (ann_vol and ann_vol != 0 and cagr is not None) else None
    else:
        cagr = ann_vol = manual_sharpe = None
    # 基准净值与超额收益
    bench_ret = benchmark_df['close'].pct_change().fillna(0)
    bench_equity = (1 + bench_ret).cumprod()
    excess_equity = port_equity.reindex(bench_equity.index, method='ffill') / bench_equity
    excess_cagr = (excess_equity.dropna().iloc[-1])**(1/years) - 1 if years > 0 and not excess_equity.dropna().empty else None
    print('最大回撤%:', max_dd_pct)
    print('最大回撤资金:', max_dd_money)
    print('夏普比率(分析器):', sharpe.get('sharperatio'))
    print('年化收益(CAGR):', cagr)
    print('年化波动率:', ann_vol)
    print('手动夏普(零无风险):', manual_sharpe)
    print('超额年化收益(组合/基准):', excess_cagr)

    # 字体设置，避免中文乱码 (若系统无字体会 fallback)
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    # 净值曲线 (组合 vs 基准 vs 超额)
    combined = pd.DataFrame({'组合净值': port_equity, '基准净值': bench_equity, '超额净值(组合/基准)': excess_equity})
    combined.dropna(how='all', inplace=True)
    plt.figure(figsize=(11, 5))
    combined.plot(ax=plt.gca())
    plt.title('组合 / 基准 / 超额 净值曲线')
    plt.ylabel('净值')
    plt.tight_layout()
    plt.savefig('equity_curve.png')
    print('净值曲线保存为 equity_curve.png')


if __name__ == '__main__':
    run_backtest()

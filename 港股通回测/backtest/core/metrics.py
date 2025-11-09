import pandas as pd

class Metrics:
    def basic(self, nav_df: pd.DataFrame) -> dict:
        nav_df = nav_df.sort_values('date').reset_index(drop=True)
        nav_series = nav_df['nav']
        if nav_series.iloc[0] == 0:
            return {}
        ret = nav_series.pct_change().fillna(0.0)
        cum_return = nav_series.iloc[-1] / nav_series.iloc[0] - 1
        ann_factor = 252 / max(1, len(nav_df))
        ann_return = (1 + cum_return) ** (ann_factor) - 1
        ann_vol = ret.std() * (252 ** 0.5)
        sharpe = ann_return / ann_vol if ann_vol > 0 else None
        dd = (nav_series.cummax() - nav_series) / nav_series.cummax()
        mdd = dd.max()
        return {
            'cum_return': float(cum_return),
            'ann_return': float(ann_return),
            'ann_vol': float(ann_vol) if ann_vol is not None else None,
            'sharpe': float(sharpe) if sharpe is not None else None,
            'max_drawdown': float(mdd)
        }

    def with_benchmark(self, nav_df: pd.DataFrame, bench_df: pd.DataFrame) -> dict:
        nav_df = nav_df.sort_values('date').reset_index(drop=True)
        bench_df = bench_df.sort_values('date').reset_index(drop=True)
        # 对齐日期
        df = pd.merge(nav_df[['date', 'nav']], bench_df[['date', 'nav']], on='date', how='inner', suffixes=('_port', '_bench'))
        if df.empty:
            return {}
        rp = df['nav_port'].pct_change().fillna(0.0)
        rb = df['nav_bench'].pct_change().fillna(0.0)
        rex = rp - rb  # 超额收益
        ann_factor = 252 / max(1, len(df))
        port_cum = df['nav_port'].iloc[-1] / df['nav_port'].iloc[0] - 1
        bench_cum = df['nav_bench'].iloc[-1] / df['nav_bench'].iloc[0] - 1
        ex_cum = (1 + port_cum) / (1 + bench_cum) - 1
        port_ann = (1 + port_cum) ** ann_factor - 1
        bench_ann = (1 + bench_cum) ** ann_factor - 1
        ex_ann = (1 + ex_cum) ** ann_factor - 1
        port_vol = rp.std() * (252 ** 0.5)
        bench_vol = rb.std() * (252 ** 0.5)
        ex_vol = rex.std() * (252 ** 0.5)
        # 夏普（超额）
        sharpe = port_ann / port_vol if port_vol > 0 else None
        ir = rex.mean() * 252 / ex_vol if ex_vol and ex_vol > 0 else None
        # Beta & Alpha（假设无风险利率 rf=0）
        rf = 0.0
        cov = (rp - rp.mean()).mul(rb - rb.mean()).mean()
        var_b = (rb - rb.mean()).pow(2).mean()
        beta = cov / var_b if var_b and var_b > 0 else None
        alpha = port_ann - (rf + (beta if beta is not None else 0) * (bench_ann - rf)) if beta is not None else None
        corr = rp.corr(rb) if rp.std() > 0 and rb.std() > 0 else None
        # 回撤（组合）
        dd = (df['nav_port'].cummax() - df['nav_port']) / df['nav_port'].cummax()
        mdd = dd.max()
        return {
            'port_cum': float(port_cum),
            'bench_cum': float(bench_cum),
            'excess_cum': float(ex_cum),
            'port_ann': float(port_ann),
            'bench_ann': float(bench_ann),
            'excess_ann': float(ex_ann),
            'port_vol': float(port_vol) if port_vol is not None else None,
            'bench_vol': float(bench_vol) if bench_vol is not None else None,
            'excess_vol': float(ex_vol) if ex_vol is not None else None,
            'sharpe': float(sharpe) if sharpe is not None else None,
            'information_ratio': float(ir) if ir is not None else None,
            'beta': float(beta) if beta is not None else None,
            'alpha': float(alpha) if alpha is not None else None,
            'correlation': float(corr) if corr is not None else None,
            'max_drawdown': float(mdd)
        }

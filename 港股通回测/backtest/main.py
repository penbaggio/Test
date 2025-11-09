import os
import sys
import yaml
import logging
import json
import pandas as pd
from datetime import datetime, timedelta
from tqdm import tqdm

from core.loader import load_pool
from core.calendar import TradingCalendar
from core.portfolio import Portfolio
from core.executor import Rebalancer
from core.metrics import Metrics
from core.benchmark import fetch_benchmark_series
try:
    from core.tushare_client import TushareClient  # tushare 数据源
except Exception:
    TushareClient = None


def load_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def ensure_path(base_dir: str, rel_path: str) -> str:
    p = os.path.normpath(os.path.join(base_dir, rel_path))
    return p


def setup_logging(base_dir: str, level: str = 'INFO', log_dir: str = 'output/logs'):
    level_map = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
    }
    log_level = level_map.get(str(level).upper(), logging.INFO)
    abs_log_dir = os.path.normpath(os.path.join(base_dir, log_dir))
    os.makedirs(abs_log_dir, exist_ok=True)
    log_path = os.path.join(abs_log_dir, 'backtest.log')

    # 清理重复 handlers
    root = logging.getLogger()
    if root.handlers:
        for h in list(root.handlers):
            root.removeHandler(h)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_path, encoding='utf-8')
        ]
    )
    logging.getLogger(__name__).info(f"日志初始化完成：level={level}, path={log_path}")


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg = load_config(os.path.join(base_dir, 'config.yaml'))

    # 日志
    setup_logging(base_dir, cfg.get('log_level', 'INFO'), cfg.get('log_dir', 'output/logs'))
    logger = logging.getLogger('backtest.main')

    pool_path = ensure_path(base_dir, cfg['pool_csv'])
    pool_df = load_pool(pool_path)
    logger.info(f"股票池加载完成：{pool_path}，记录数={len(pool_df)}")

    # 仅使用 Tushare 或占位逻辑
    data_client = None
    if cfg.get('use_tushare', False) and TushareClient is not None:
        data_client = TushareClient(token=cfg.get('tushare_token'), retry=cfg.get('tushare_retry', 3), sleep=cfg.get('tushare_sleep', 1.0))
        logger.info("已启用 Tushare 数据源")
    else:
        logger.warning("未启用真实数据源，将使用占位价格进行回测（仅用于流程验证）")

    cal = TradingCalendar(market=cfg.get('calendar_market', 'HKEX'), data_client=data_client)
    rebal_dates = sorted(pool_df['调仓日'].unique())

    # 若有数据客户端，预取全周期价格（按全股票池与全日期范围）
    if data_client is not None and hasattr(data_client, 'prefetch_prices'):
        all_syms = sorted(pool_df['证券代码'].unique().tolist())
        start_all = rebal_dates[0]
        # 末期延长一段，覆盖持仓展开区间
        end_all = rebal_dates[-1]
        cal_tmp = TradingCalendar(market=cfg.get('calendar_market', 'HKEX'), data_client=data_client)
        end_all_exec = cal_tmp.next_trade_day(end_all) or end_all
        end_all_final = cal_tmp.prev_trade_day(end_all_exec) or end_all_exec
        logger.info(f"预取价格数据：标的={len(all_syms)}，区间={start_all}~{end_all_final}")
        data_client.prefetch_prices(all_syms, start_all, end_all_final)

    # 初始化组合
    portfolio = Portfolio(initial_cash=cfg.get('initial_capital', 10_000_000))
    rebalancer = Rebalancer(
        fee_buy=cfg.get('fee_rate_buy', 0.004),
        fee_sell=cfg.get('fee_rate_sell', 0.004),
        min_trade_ratio=cfg.get('min_trade_ratio', 0.005),
        lot_size=cfg.get('lot_size', 1),
        price_mode=cfg.get('price_mode', 'next_open'),
        data_client=data_client,
        open_field=cfg.get('fields_open', 'OPEN'),
        close_field=cfg.get('fields_close', 'CLOSE'),
        adj=cfg.get('adjust_mode', '')
    )

    daily_nav = []
    trade_logs = []

    for i, d in enumerate(tqdm(rebal_dates, desc='Rebalance periods')):
        # 确定执行日（下一交易日）
        exec_day = cal.next_trade_day(d)
        if exec_day is None:
            logger.warning(f"调仓日 {d} 无下一交易日，跳过")
            continue

        # 当期目标股票
        symbols = pool_df.loc[pool_df['调仓日'] == d, '证券代码'].tolist()

        # 获取执行日价格（占位：使用价格接口替代）——覆盖“目标集 ∪ 当前持仓”
        union_syms = list(set(symbols) | set(portfolio.positions.keys()))
        prices = rebalancer.get_prices(exec_day, union_syms)

        # 组合等权再平衡
        trades = rebalancer.rebalance(exec_day, symbols, prices, portfolio)
        trade_logs.extend(trades)
        if getattr(rebalancer, 'last_diag', None):
            logger.info(f"{exec_day} 再平衡：目标={len(symbols)}，可交易={rebalancer.last_diag.get('tradable_targets')}，买入={rebalancer.last_diag.get('buys')}，卖出={rebalancer.last_diag.get('sells')}，锁定目标={rebalancer.last_diag.get('locked_targets')}，锁定卖出={rebalancer.last_diag.get('locked_sells')}")

        # 展开持仓至下一个执行日前一日
        next_d = rebal_dates[i+1] if i+1 < len(rebal_dates) else None
        # 结束日定义：下一调仓执行日前一交易日；若最后一期仅记录执行日
        if next_d:
            next_exec = cal.next_trade_day(next_d)
            end_day = cal.prev_trade_day(next_exec) if next_exec else exec_day
        else:
            end_day = exec_day

        day_list = cal.trade_days_between(exec_day, end_day)
        for tday in tqdm(day_list, desc=f'Holding {exec_day}->{end_day}', leave=False):
            day_prices = rebalancer.get_all_positions_prices(tday, list(portfolio.positions.keys()))
            nav = portfolio.total_value(day_prices)
            daily_nav.append({'date': tday, 'nav': nav})
        logger.debug(f"持仓展开完成：{exec_day} 到 {end_day}，天数={len(day_list)}，期末净值={daily_nav[-1]['nav'] if daily_nav else portfolio.cash}")

    # 导出结果
    out_dir = ensure_path(base_dir, 'output')
    os.makedirs(out_dir, exist_ok=True)
    nav_path = os.path.join(out_dir, 'nav_curve.csv')
    trades_path = os.path.join(out_dir, 'trades.csv')
    pd.DataFrame(daily_nav).to_csv(nav_path, index=False, encoding='utf-8')
    pd.DataFrame(trade_logs, columns=['date','side','symbol','qty','price','cost']).to_csv(trades_path, index=False, encoding='utf-8')
    logger.info(f"结果已导出：{nav_path}，{trades_path}")

    # 计算基础指标
    nav_df = pd.DataFrame(daily_nav)
    if not nav_df.empty:
        # 基础指标
        m = Metrics()
        basic_metrics = m.basic(nav_df)
        logger.info(f"基础指标：{basic_metrics}")
        # 导出基础指标
        basic_metrics_path = os.path.join(out_dir, 'metrics_basic.json')
        try:
            with open(basic_metrics_path, 'w', encoding='utf-8') as f:
                json.dump(basic_metrics, f, ensure_ascii=False, indent=2)
            logger.info(f"基础指标已导出：{basic_metrics_path}")
        except Exception as e:
            logger.warning(f"基础指标导出失败：{e}")
        # 基准
        bench_code = cfg.get('benchmark_code') or cfg.get('benchmark')
        bench_init = float(cfg.get('benchmark_initial', 1.0))
        bench_df = None
        if bench_code:
            try:
                start_d = nav_df['date'].min()
                end_d = nav_df['date'].max()
                bench_df = fetch_benchmark_series(base_dir, data_client, bench_code, start_d, end_d, bench_init)
            except Exception as e:
                logger.exception(f"获取基准失败：{e}")
        if bench_df is not None and not bench_df.empty:
            bench_metrics = m.with_benchmark(nav_df, bench_df)
            logger.info(f"基准对比指标：{bench_metrics}")
            # 导出基准净值
            bench_out = os.path.join(out_dir, 'benchmark_nav.csv')
            bench_df.to_csv(bench_out, index=False, encoding='utf-8')
            logger.info(f"基准净值已导出：{bench_out}")
            # 导出基准对比指标
            bench_metrics_path = os.path.join(out_dir, 'metrics_with_benchmark.json')
            try:
                with open(bench_metrics_path, 'w', encoding='utf-8') as f:
                    json.dump(bench_metrics, f, ensure_ascii=False, indent=2)
                logger.info(f"基准对比指标已导出：{bench_metrics_path}")
            except Exception as e:
                logger.warning(f"基准对比指标导出失败：{e}")
        else:
            logger.warning("未生成基准序列，跳过对比指标计算。")
    else:
        logger.error('净值为空：未生成 NAV，请接入价格数据源。')


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
增强版价值策略因子选股回测系统
特点：
1. 完善的调仓逻辑
2. 使用上一交易日收盘价
3. 精确的交易成本计算
4. 与基准对比分析
"""

import backtrader as bt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# Wind API
try:
    from WindPy import w
    w.start()
    print("Wind API 启动成功")
except Exception as e:
    print(f"Wind API 启动失败: {e}")


class PercentCommissionScheme(bt.CommInfoBase):
    """自定义交易成本方案 - 单边0.2%"""
    params = (
        ('commission', 0.002),  # 0.2%
        ('stocklike', True),
        ('commtype', bt.CommInfoBase.COMM_PERC),
    )

    def _getcommission(self, size, price, pseudoexec):
        """计算交易成本"""
        return abs(size) * price * self.params.commission


class EnhancedValueStrategy(bt.Strategy):
    """增强版价值因子选股策略"""
    
    params = (
        ('top_n', 30),  # 选择前30只股票
        ('printlog', True),  # 是否打印日志
    )
    
    def __init__(self):
        self.order_list = []
        self.current_holdings = []  # 当前持仓股票代码列表
        self.rebalance_dates = []  # 已执行的调仓日期
        self.trade_dates = []  # 所有交易日期
        self.portfolio_values = []  # 组合价值记录
        self.planned_rebalance_dates = []  # 计划调仓日期（从因子数据中读取）
        
        # 加载因子数据
        self.factor_data = self.load_factor_data()
        
        # 从因子数据中提取所有调仓日期
        if self.factor_data is not None and not self.factor_data.empty:
            self.planned_rebalance_dates = sorted(self.factor_data['日期'].unique())
            print(f"从因子数据中读取到{len(self.planned_rebalance_dates)}个调仓日期:")
            for date in self.planned_rebalance_dates:
                print(f"  - {date.strftime('%Y-%m-%d')}")
        
        # 获取所有股票代码
        self.all_stock_codes = [d._name for d in self.datas if d._name != 'benchmark']
        print(f"回测包含{len(self.all_stock_codes)}只股票")
        
    def load_factor_data(self):
        """加载因子数据"""
        try:
            factor_file = 'd:\\昭融汇利\\3. 港股通\\1. 价值策略\\价值策略因子选股_backtrader\\价值策略因子数据【CSV】.csv'
            df = pd.read_csv(factor_file, encoding='utf-8')
            df['日期'] = pd.to_datetime(df['日期'])
            print(f"成功加载因子数据，共{len(df)}条记录")
            return df
        except Exception as e:
            print(f"加载因子数据失败: {e}")
            return pd.DataFrame()
    
    def prenext(self):
        """数据预热阶段"""
        self.next()
    
    def next(self):
        """策略主逻辑"""
        current_date = self.datas[0].datetime.date(0)
        
        # 记录组合价值
        self.portfolio_values.append({
            'date': current_date,
            'value': self.broker.getvalue()
        })
        
        # 判断是否需要调仓
        if self.should_rebalance(current_date):
            self.log(f"\n{'='*80}")
            self.log(f"调仓日: {current_date}")
            self.log(f"当前组合价值: {self.broker.getvalue():,.2f}")
            self.log(f"{'='*80}")
            
            # 选择目标股票
            target_stocks = self.select_stocks(current_date)
            
            if target_stocks:
                self.rebalance_portfolio(target_stocks, current_date)
            
            # 记录调仓日期
            self.rebalance_dates.append(current_date)
    
    def should_rebalance(self, current_date):
        """判断是否应该调仓 - 基于因子数据中的实际日期"""
        # 检查当前日期是否接近任何一个计划调仓日期
        for planned_date in self.planned_rebalance_dates:
            planned_date_obj = planned_date.date() if hasattr(planned_date, 'date') else planned_date
            
            # 允许5天的误差范围（因为可能遇到非交易日）
            date_diff = abs((current_date - planned_date_obj).days)
            
            if date_diff <= 5:
                # 检查是否已经在这个日期附近调仓过
                for executed_date in self.rebalance_dates:
                    if abs((executed_date - planned_date_obj).days) <= 5:
                        return False  # 已经调仓过了
                
                return True  # 应该调仓
        
        return False
    
    def select_stocks(self, current_date):
        """
        基于三因子等权排序选择前30只股票
        使用当前调仓日期对应的因子数据（而非之前的数据）
        """
        if self.factor_data is None or self.factor_data.empty:
            return []
        
        # 找到最接近当前日期的因子数据日期
        current_date_ts = pd.Timestamp(current_date)
        date_diffs = abs(self.factor_data['日期'] - current_date_ts)
        closest_date = self.factor_data.loc[date_diffs.idxmin(), '日期']
        
        # 如果最接近的日期相差超过10天，则使用之前的最近数据
        if abs((closest_date.date() - current_date).days) > 10:
            available_data = self.factor_data[self.factor_data['日期'] <= current_date_ts]
            if available_data.empty:
                self.log(f"警告: 在{current_date}之前没有可用的因子数据")
                return []
            closest_date = available_data['日期'].max()
        
        # 获取该日期的数据
        latest_data = self.factor_data[self.factor_data['日期'] == closest_date].copy()
        
        self.log(f"使用因子数据日期: {closest_date.strftime('%Y-%m-%d')}, "
                f"可用股票: {len(latest_data)}只")
        
        # 过滤退市股票
        latest_data = latest_data[~latest_data['证券代码'].str.contains('!', na=False)]
        
        # 只保留有价格数据的股票
        latest_data = latest_data[latest_data['证券代码'].isin(self.all_stock_codes)]
        
        if len(latest_data) < self.params.top_n:
            self.log(f"警告: 可用股票数量({len(latest_data)})少于目标数量({self.params.top_n})")
        
        # 三因子排名（越大越好）
        latest_data['现金流量排名'] = latest_data['现金流量比例'].rank(ascending=False, method='min')
        latest_data['股息率排名'] = latest_data['股息率'].rank(ascending=False, method='min')
        latest_data['回购比例排名'] = latest_data['回购比例'].rank(ascending=False, method='min')
        
        # 等权复合得分（排名越小越好）
        latest_data['复合得分'] = (
            latest_data['现金流量排名'] + 
            latest_data['股息率排名'] + 
            latest_data['回购比例排名']
        ) / 3.0
        
        # 选择复合得分最小的前N只
        top_stocks = latest_data.nsmallest(self.params.top_n, '复合得分')
        
        # 打印选股结果
        self.log(f"\n选出前{len(top_stocks)}只股票:")
        for idx, row in top_stocks.iterrows():
            self.log(f"  {row['证券代码']} {row['证券名称']}: "
                    f"现金流={row['现金流量比例']:.4f}, "
                    f"股息率={row['股息率']:.4f}, "
                    f"回购={row['回购比例']:.4f}, "
                    f"得分={row['复合得分']:.2f}")
        
        return top_stocks['证券代码'].tolist()
    
    def rebalance_portfolio(self, target_stocks, current_date):
        """执行组合调仓 - 等权配置"""
        # 取消所有未完成的订单
        for order in self.order_list:
            self.cancel(order)
        self.order_list = []
        
        # 当前持仓
        current_positions = {}
        for data in self.datas:
            if data._name == 'benchmark':
                continue
            pos = self.getposition(data)
            if pos.size != 0:
                current_positions[data._name] = pos
        
        # 计算需要卖出和买入的股票
        current_stocks = set(current_positions.keys())
        target_stocks_set = set(target_stocks)
        
        to_sell = current_stocks - target_stocks_set
        to_buy = target_stocks_set - current_stocks
        to_adjust = current_stocks & target_stocks_set
        
        self.log(f"\n调仓操作:")
        self.log(f"  卖出: {len(to_sell)}只")
        self.log(f"  买入: {len(to_buy)}只")
        self.log(f"  调整: {len(to_adjust)}只")
        
        # 第一步: 卖出不在目标组合中的股票
        for stock_code in to_sell:
            data = self.getdatabyname(stock_code)
            pos = self.getposition(data)
            if pos.size > 0:
                self.log(f"  卖出 {stock_code}: {pos.size}股")
                order = self.close(data=data)
                self.order_list.append(order)
        
        # 第二步: 计算目标仓位并执行买入/调整
        # 等权配置：每只股票占1/N
        target_weight = 1.0 / len(target_stocks)
        portfolio_value = self.broker.getvalue()
        
        for stock_code in target_stocks:
            data = self.getdatabyname(stock_code)
            if data is None:
                self.log(f"  警告: 未找到{stock_code}的数据")
                continue
            
            # 目标持仓金额
            target_value = portfolio_value * target_weight
            current_price = data.close[0]
            
            if current_price <= 0:
                self.log(f"  警告: {stock_code}价格无效: {current_price}")
                continue
            
            # 目标持仓股数
            target_size = int(target_value / current_price)
            
            # 当前持仓
            current_pos = self.getposition(data)
            current_size = current_pos.size
            
            # 计算需要调整的股数
            size_diff = target_size - current_size
            
            if abs(size_diff) > 0:
                if size_diff > 0:
                    self.log(f"  买入 {stock_code}: {size_diff}股 "
                            f"@ {current_price:.2f} "
                            f"(目标金额: {target_value:.2f})")
                    order = self.buy(data=data, size=size_diff)
                else:
                    self.log(f"  卖出 {stock_code}: {-size_diff}股 "
                            f"@ {current_price:.2f}")
                    order = self.sell(data=data, size=-size_diff)
                
                self.order_list.append(order)
        
        # 更新当前持仓列表
        self.current_holdings = target_stocks.copy()
    
    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f"    ✓ 买入成交: {order.data._name}, "
                        f"价格: {order.executed.price:.4f}, "
                        f"数量: {order.executed.size:.0f}, "
                        f"成本: {order.executed.value:.2f}, "
                        f"手续费: {order.executed.comm:.2f}")
            elif order.issell():
                self.log(f"    ✓ 卖出成交: {order.data._name}, "
                        f"价格: {order.executed.price:.4f}, "
                        f"数量: {order.executed.size:.0f}, "
                        f"金额: {order.executed.value:.2f}, "
                        f"手续费: {order.executed.comm:.2f}")
        
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f"    ✗ 订单失败: {order.data._name}, 状态: {order.getstatusname()}")
        
        # 从订单列表中移除
        if order in self.order_list:
            self.order_list.remove(order)
    
    def notify_trade(self, trade):
        """交易通知"""
        if not trade.isclosed:
            return
        
        self.log(f"    交易关闭: {trade.data._name}, "
                f"利润: {trade.pnl:.2f}, "
                f"净利润: {trade.pnlcomm:.2f}")
    
    def log(self, txt, dt=None):
        """日志输出"""
        if self.params.printlog:
            dt = dt or self.datas[0].datetime.date(0)
            print(f'{dt} {txt}')
    
    def stop(self):
        """策略结束"""
        self.log('\n' + '='*80)
        self.log(f'策略结束')
        self.log(f'最终组合价值: {self.broker.getvalue():,.2f}')
        self.log(f'总调仓次数: {len(self.rebalance_dates)}')
        self.log('='*80)


def get_all_stock_codes(factor_file):
    """从因子文件获取所有股票代码"""
    df = pd.read_csv(factor_file, encoding='utf-8')
    # 排除退市股票
    codes = df[~df['证券代码'].str.contains('!', na=False)]['证券代码'].unique()
    return codes.tolist()


def get_wind_stock_data(stock_codes, start_date, end_date):
    """批量获取股票前复权收盘价"""
    print(f"\n开始获取{len(stock_codes)}只股票的价格数据...")
    print(f"日期范围: {start_date} 至 {end_date}")
    
    price_data = {}
    failed_stocks = []
    
    try:
        for i, code in enumerate(stock_codes, 1):
            if i % 10 == 0:
                print(f"  进度: {i}/{len(stock_codes)}")
            
            # 获取前复权收盘价
            result = w.wsd(code, "close,volume", start_date, end_date, 
                          "PriceAdj=F;Currency=CNY")
            
            if result.ErrorCode != 0:
                print(f"  失败: {code} - {result.Data}")
                failed_stocks.append(code)
                continue
            
            # 转换为DataFrame
            df = pd.DataFrame({
                'datetime': result.Times,
                'close': result.Data[0],
                'volume': result.Data[1] if len(result.Data) > 1 else [0] * len(result.Times)
            })
            
            df['datetime'] = pd.to_datetime(df['datetime'])
            df.set_index('datetime', inplace=True)
            
            # 填充OHLC
            df['open'] = df['close']
            df['high'] = df['close']
            df['low'] = df['close']
            
            # 去除空值
            df = df.dropna()
            
            if len(df) > 0:
                price_data[code] = df
            else:
                failed_stocks.append(code)
        
        print(f"\n成功获取: {len(price_data)}只")
        if failed_stocks:
            print(f"失败: {len(failed_stocks)}只")
        
    except Exception as e:
        print(f"获取数据时出错: {e}")
    
    return price_data


def get_benchmark_data(start_date, end_date):
    """获取基准指数 881005.WI"""
    print(f"\n获取基准指数 881005.WI...")
    
    try:
        result = w.wsd("881005.WI", "close", start_date, end_date, "")
        
        if result.ErrorCode != 0:
            print(f"获取失败: {result.Data}")
            return None
        
        df = pd.DataFrame({
            'datetime': result.Times,
            'close': result.Data[0]
        })
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        # 填充OHLCV
        df['open'] = df['close']
        df['high'] = df['close']
        df['low'] = df['close']
        df['volume'] = 0
        
        print(f"成功获取基准数据，共{len(df)}条记录")
        return df
        
    except Exception as e:
        print(f"获取基准数据失败: {e}")
        return None


def analyze_results(strat, benchmark_df):
    """分析回测结果"""
    print("\n" + "="*80)
    print("回测结果分析")
    print("="*80)
    
    # 提取组合净值曲线
    portfolio_df = pd.DataFrame(strat.portfolio_values)
    portfolio_df['date'] = pd.to_datetime(portfolio_df['date'])
    portfolio_df.set_index('date', inplace=True)
    
    # 计算收益率
    portfolio_df['return'] = portfolio_df['value'].pct_change()
    
    # 基本统计
    initial_value = portfolio_df['value'].iloc[0]
    final_value = portfolio_df['value'].iloc[-1]
    total_return = (final_value - initial_value) / initial_value
    
    # 计算年化收益率
    days = (portfolio_df.index[-1] - portfolio_df.index[0]).days
    years = days / 365.25
    annual_return = (1 + total_return) ** (1 / years) - 1
    
    # 计算波动率
    volatility = portfolio_df['return'].std() * np.sqrt(252)
    
    # 计算夏普比率（假设无风险利率为0）
    sharpe = annual_return / volatility if volatility > 0 else 0
    
    # 计算最大回撤
    cummax = portfolio_df['value'].cummax()
    drawdown = (portfolio_df['value'] - cummax) / cummax
    max_drawdown = drawdown.min()
    
    # 与基准对比
    if benchmark_df is not None and not benchmark_df.empty:
        # 对齐日期
        merged = portfolio_df.join(benchmark_df[['close']], how='inner')
        merged['benchmark_return'] = merged['close'].pct_change()
        
        # 归一化
        merged['portfolio_norm'] = merged['value'] / merged['value'].iloc[0]
        merged['benchmark_norm'] = merged['close'] / merged['close'].iloc[0]
        
        # 基准收益率
        benchmark_total_return = (merged['close'].iloc[-1] - merged['close'].iloc[0]) / merged['close'].iloc[0]
        benchmark_annual_return = (1 + benchmark_total_return) ** (1 / years) - 1
        
        # 超额收益
        excess_return = annual_return - benchmark_annual_return
        
        print(f"\n策略表现:")
        print(f"  总收益率: {total_return * 100:.2f}%")
        print(f"  年化收益率: {annual_return * 100:.2f}%")
        print(f"  年化波动率: {volatility * 100:.2f}%")
        print(f"  夏普比率: {sharpe:.4f}")
        print(f"  最大回撤: {max_drawdown * 100:.2f}%")
        
        print(f"\n基准表现 (881005.WI):")
        print(f"  总收益率: {benchmark_total_return * 100:.2f}%")
        print(f"  年化收益率: {benchmark_annual_return * 100:.2f}%")
        
        print(f"\n相对表现:")
        print(f"  超额年化收益: {excess_return * 100:.2f}%")
        
        return merged
    
    else:
        print(f"\n策略表现:")
        print(f"  总收益率: {total_return * 100:.2f}%")
        print(f"  年化收益率: {annual_return * 100:.2f}%")
        print(f"  年化波动率: {volatility * 100:.2f}%")
        print(f"  夏普比率: {sharpe:.4f}")
        print(f"  最大回撤: {max_drawdown * 100:.2f}%")
        
        return portfolio_df


def plot_results(results_df):
    """绘制回测结果"""
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    # 净值曲线对比
    ax1 = axes[0]
    ax1.plot(results_df.index, results_df['portfolio_norm'], 
             label='策略组合', linewidth=2, color='red')
    ax1.plot(results_df.index, results_df['benchmark_norm'], 
             label='基准 (881005.WI)', linewidth=2, color='blue', alpha=0.7)
    ax1.set_title('净值曲线对比', fontsize=14, fontweight='bold')
    ax1.set_xlabel('日期', fontsize=12)
    ax1.set_ylabel('累计净值', fontsize=12)
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    
    # 回撤曲线
    ax2 = axes[1]
    portfolio_cummax = results_df['value'].cummax()
    portfolio_drawdown = (results_df['value'] - portfolio_cummax) / portfolio_cummax * 100
    
    ax2.fill_between(results_df.index, portfolio_drawdown, 0, 
                      alpha=0.3, color='red', label='回撤')
    ax2.plot(results_df.index, portfolio_drawdown, color='red', linewidth=1.5)
    ax2.set_title('回撤曲线', fontsize=14, fontweight='bold')
    ax2.set_xlabel('日期', fontsize=12)
    ax2.set_ylabel('回撤 (%)', fontsize=12)
    ax2.legend(fontsize=11)
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('d:\\昭融汇利\\3. 港股通\\1. 价值策略\\价值策略因子选股_backtrader\\回测结果.png', 
                dpi=300, bbox_inches='tight')
    print("\n图表已保存至: 回测结果.png")
    plt.show()


def run_backtest():
    """主回测流程"""
    print("\n" + "="*80)
    print("价值策略因子选股回测系统 - Enhanced Version")
    print("="*80)
    
    # 参数设置
    START_DATE = '2015-01-01'
    END_DATE = '2025-08-26'
    INITIAL_CASH = 10000000.0  # 1000万初始资金
    
    # 获取股票列表
    factor_file = 'd:\\昭融汇利\\3. 港股通\\1. 价值策略\\价值策略因子选股_backtrader\\价值策略因子数据【CSV】.csv'
    stock_codes = get_all_stock_codes(factor_file)
    print(f"\n共{len(stock_codes)}只股票")
    
    # 获取价格数据
    price_data = get_wind_stock_data(stock_codes, START_DATE, END_DATE)
    
    if len(price_data) == 0:
        print("\n错误: 未获取到任何价格数据")
        return
    
    # 获取基准数据
    benchmark_df = get_benchmark_data(START_DATE, END_DATE)
    
    # 初始化Cerebro
    cerebro = bt.Cerebro()
    
    # 添加策略
    cerebro.addstrategy(EnhancedValueStrategy)
    
    # 添加股票数据
    print(f"\n添加{len(price_data)}只股票数据到回测引擎...")
    for stock_code, df in price_data.items():
        data_feed = bt.feeds.PandasData(
            dataname=df,
            fromdate=datetime.strptime(START_DATE, '%Y-%m-%d'),
            todate=datetime.strptime(END_DATE, '%Y-%m-%d')
        )
        cerebro.adddata(data_feed, name=stock_code)
    
    # 添加基准数据
    if benchmark_df is not None:
        benchmark_feed = bt.feeds.PandasData(
            dataname=benchmark_df,
            fromdate=datetime.strptime(START_DATE, '%Y-%m-%d'),
            todate=datetime.strptime(END_DATE, '%Y-%m-%d')
        )
        cerebro.adddata(benchmark_feed, name='benchmark')
    
    # 设置初始资金
    cerebro.broker.setcash(INITIAL_CASH)
    
    # 设置交易成本
    cerebro.broker.addcommissioninfo(PercentCommissionScheme())
    
    # 设置滑点（可选）
    # cerebro.broker.set_slippage_perc(0.0001)  # 0.01%滑点
    
    # 运行回测
    print("\n" + "="*80)
    print("开始回测...")
    print("="*80)
    print(f"初始资金: {INITIAL_CASH:,.2f}")
    
    results = cerebro.run()
    strat = results[0]
    
    final_value = cerebro.broker.getvalue()
    print(f"\n最终资金: {final_value:,.2f}")
    print(f"总收益: {final_value - INITIAL_CASH:,.2f}")
    
    # 分析结果
    results_df = analyze_results(strat, benchmark_df)
    
    # 绘制图表
    if 'benchmark_norm' in results_df.columns:
        plot_results(results_df)
    
    print("\n回测完成！")


if __name__ == '__main__':
    run_backtest()

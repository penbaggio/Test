import pandas as pd
from pathlib import Path

FACTOR_FILE = Path(__file__).parent / '价值策略因子数据【CSV】.csv'

FACTOR_COLUMNS = ['现金流量比例', '股息率', '回购比例']


def load_factor_data() -> pd.DataFrame:
    df = pd.read_csv(FACTOR_FILE)
    # 日期格式: 2015/1/1 -> 采用 pandas to_datetime 自动解析
    df['日期'] = pd.to_datetime(df['日期'])
    # 标准化证券代码: CSV中部分为4位数字，需要补齐为5位以便Wind (假设需要)
    df['证券代码_std'] = df['证券代码'].apply(standardize_code)
    # 去除名称中的退市标记供后续参考
    df['退市标记'] = df['证券名称'].str.contains('退市')
    df['证券名称_clean'] = df['证券名称'].str.replace('\(退市\)', '', regex=True)
    return df


def standardize_code(code: str) -> str:
    # 保留原始感叹号及其后缀，不做清除
    if code.endswith('.HK'):
        prefix = code.split('.')[0]
        # 若存在感叹号，直接保留完整前缀（例如 0013!1）
        if '!' in prefix:
            return code  # 原样返回
        # 否则规范为四位数字形式
        digits = prefix[-4:]
        digits = digits.zfill(4)
        return f'{digits}.HK'
    return code


def compute_rebalance_dates(df: pd.DataFrame, start: str, end: str) -> list:
    start_dt = pd.to_datetime(start)
    end_dt = pd.to_datetime(end)
    dfr = df[(df['日期'] >= start_dt) & (df['日期'] <= end_dt)]
    # 每年12月底调仓: 取该年12月的最后一个有因子数据的日期
    rebal_dates = []
    years = sorted(dfr['日期'].dt.year.unique())
    for y in years:
        dec_mask = (dfr['日期'].dt.year == y) & (dfr['日期'].dt.month == 12)
        dec_df = dfr[dec_mask]
        if dec_df.empty:
            # 如果12月没有数据则跳过该年
            continue
        last_date = dec_df['日期'].max()
        rebal_dates.append(last_date)
    # 初始建仓日强制加入 (若不在列表)
    if start_dt not in rebal_dates:
        rebal_dates.insert(0, start_dt)
    # 确保截止日期之前
    rebal_dates = [d for d in rebal_dates if d <= end_dt]
    return sorted(rebal_dates)


def select_portfolio(df: pd.DataFrame, on_date) -> list:
    # 在调仓日使用该日期对应因子值进行排名 (等权: 排名求和)
    slice_df = df[df['日期'] == on_date]
    if slice_df.empty:
        return []
    ranked = slice_df.copy()
    # 为每个因子做升序排名（假设数值越大越好, 使用 ascending=False）
    for col in FACTOR_COLUMNS:
        ranked[col + '_rank'] = ranked[col].rank(method='average', ascending=False)
    ranked['score'] = ranked[[c + '_rank' for c in FACTOR_COLUMNS]].sum(axis=1)
    ranked.sort_values('score', ascending=True, inplace=True)  # 排名值越小越好 (1最好)
    top = ranked.head(30)
    return top['证券代码_std'].tolist()


if __name__ == '__main__':
    df_factor = load_factor_data()
    rebal_dates = compute_rebalance_dates(df_factor, '2015-01-01', '2025-08-26')
    for d in rebal_dates:
        codes = select_portfolio(df_factor, d)
        print(d.date(), len(codes), codes[:5])

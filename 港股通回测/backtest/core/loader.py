import pandas as pd

def load_pool(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, encoding='utf-8')
    # 统一日期格式为 datetime.date
    df['调仓日'] = pd.to_datetime(df['调仓日']).dt.date
    df['证券代码'] = df['证券代码'].astype(str)
    return df

import pandas as pd
from pathlib import Path

def load_historical_data(file_path="historical_lite.parquet"):
    """Load historical data from parquet file"""
    try:
        df = pd.read_parquet(file_path)
        return df
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return pd.DataFrame()

def get_data_summary(df):
    """Get summary statistics of the data"""
    if df.empty:
        return {}
    return {
        "total_records": len(df),
        "columns": list(df.columns),
        "date_range": f"{df.index.min()} to {df.index.max()}" if hasattr(df.index, 'min') else "N/A"
    }

def filter_data(df, filters=None):
    """Apply filters to dataframe"""
    if filters is None:
        return df
    return df

# loggers/logger_base.py

import os
import pandas as pd

class BaseLogger:
    """
    ログの共通処理クラス
    - データ保持
    - データ追加
    - DataFrame 変換
    """
    def __init__(self, log_dir="logs", filename=None):
        self.log_dir = log_dir
        self.filename = filename
        os.makedirs(self.log_dir, exist_ok=True)
        self.records = []

    def log(self, data: dict):
        self.records.append(data)

    def _to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.records)

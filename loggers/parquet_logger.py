import os
import pandas as pd
from .base_logger import BaseLogger

class ParquetLogger(BaseLogger):
    """
    Parquet形式でログを保存するロガークラス
    """
    def __init__(self, log_dir="logs", filename="log.parquet", **kwargs):
        super().__init__(log_dir=log_dir, filename=filename, **kwargs)

    def save(self):
        df = self._to_dataframe()
        filepath = os.path.join(self.log_dir, self.filename or "log.parquet")
        df.to_parquet(filepath, index=False)
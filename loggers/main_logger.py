# loggers/main_logger.py

class MainLogger:
    """
    ログデータを記録し、指定形式で保存するためのクラス
    - 使用する形式は設定から変更可能
    - log() でデータを追加
    - save() でファイルに保存
    """
    def __init__(self, logger_class, log_dir="logs", **kwargs):
        """
        :param logger_class: 使用するロガークラス（ParquetLogger や CSVLogger）
        :param log_dir: 保存先ディレクトリ
        :param kwargs: ロガークラスの初期化パラメータ
        """
        self.logger = logger_class(log_dir=log_dir, **kwargs)

    def log(self, data: dict):
        self.logger.log(data)

    def save(self):
        self.logger.save()

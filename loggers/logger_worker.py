import time
from input_reader import InputReader
from loggers.main_logger import MainLogger
from loggers.csv_logger import CSVLogger
from loggers.parquet_logger import ParquetLogger

class LoggerWorker:
    def __init__(self, filepath, interval=0.01, format="parquet"):
        self.filepath = filepath
        self.interval = interval
        self.format = format
        self.running = False

    def run(self, status_callback=None, update_callback=None, sleep_func=None):
        reader = InputReader()
        filename = self.filepath.split("/")[-1]
        logger_class_map = {
            "csv": CSVLogger,
            "parquet": ParquetLogger,
        }
        logger_cls = logger_class_map.get(self.format)
        logger = MainLogger(logger_cls, log_dir="logs", filename=filename)
        headers = reader.get_headers()
        self.running = True
        while self.running:
            timestamp, axes, buttons = reader.read()
            values = [timestamp] + list(axes) + list(buttons)
            data = {h: v for h, v in zip(headers, values)}
            logger.log(data)
            if status_callback:
                status_callback(f"記録中... {time.time():.2f}")
            if update_callback:
                update_callback(axes, buttons)
            if sleep_func:
                sleep_func(self.interval)
            else:
                time.sleep(self.interval)
        logger.save()
        reader.close()
        if status_callback:
            status_callback("記録停止")

    def stop(self):
        self.running = False
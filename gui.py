from PySide6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QLabel, QFileDialog,
    QGraphicsScene, QGraphicsView, QGraphicsEllipseItem
)
from PySide6.QtCore import QThread, Signal, QRectF, Qt
from PySide6.QtGui import QBrush, QColor

from loggers.logger_worker import LoggerWorker
from PySide6.QtCore import QThread, Signal

# PySide6用ラッパースレッド
class LoggerWorkerThread(QThread):
    status = Signal(str)
    update = Signal(list, list)  # axes, buttons

    def __init__(self, filepath, interval=0.01, format="parquet"):
        super().__init__()
        self.worker = LoggerWorker(filepath, interval, format=format)
        self._running = False

    def run(self):
        self._running = True
        def status_callback(msg):
            self.status.emit(msg)
        def update_callback(axes, buttons):
            self.update.emit(axes, buttons)
        def sleep_func(interval):
            self.msleep(int(interval * 1000))
        self.worker.running = True
        self.worker.run(status_callback, update_callback, sleep_func)
        self._running = False

    def stop(self):
        self.worker.stop()

# 仮想コントローラー表示
class ControllerView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene()
        self.setScene(self.scene)

        # 左スティック領域
        self.left_area = QGraphicsEllipseItem(QRectF(0, 0, 80, 80))
        self.left_area.setBrush(QBrush(Qt.gray))
        self.scene.addItem(self.left_area)

        self.left_stick = QGraphicsEllipseItem(QRectF(30, 30, 20, 20))
        self.left_stick.setBrush(QBrush(Qt.red))
        self.scene.addItem(self.left_stick)

        # Aボタン
        self.btn_a = QGraphicsEllipseItem(QRectF(150, 20, 20, 20))
        self.btn_a.setBrush(QBrush(Qt.green))
        self.scene.addItem(self.btn_a)

    def update_view(self, axes, buttons):
        if len(axes) >= 2:
            x = 30 + axes[0] * 30
            y = 30 + axes[1] * 30
            self.left_stick.setRect(x, y, 20, 20)

        if len(buttons) > 0:
            if buttons[0]:
                self.btn_a.setBrush(QBrush(QColor("yellow")))
            else:
                self.btn_a.setBrush(QBrush(Qt.green))


# メインウィンドウ
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controller Logger (PySide6)")
        self.worker = None

        layout = QVBoxLayout()
        # 記録方式選択
        from PySide6.QtWidgets import QComboBox, QLineEdit
        self.format_box = QComboBox()
        self.format_box.addItems(["parquet", "csv"])
        layout.addWidget(QLabel("記録方式"))
        layout.addWidget(self.format_box)

        # ファイル名入力欄（未入力なら自動生成）
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("ファイル名（未入力なら自動生成）")
        layout.addWidget(QLabel("ファイル名"))
        layout.addWidget(self.filename_edit)
        # config.jsonから記録方式の初期値をセット
        import json
        try:
            with open("config.json", "r", encoding="utf-8") as f:
                config = json.load(f)
                default_format = config.get("log_format", "parquet")
        except Exception:
            default_format = "parquet"
        idx = self.format_box.findText(default_format)
        if idx >= 0:
            self.format_box.setCurrentIndex(idx)

        self.label = QLabel("待機中")
        layout.addWidget(self.label)

        self.start_btn = QPushButton("記録開始")
        self.start_btn.clicked.connect(self.start_logging)
        layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("記録停止")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_logging)
        layout.addWidget(self.stop_btn)

        self.controller_view = ControllerView()
        layout.addWidget(self.controller_view)

        self.setLayout(layout)

        # 記録方式変更時にconfig.jsonへ保存
        def save_format_to_config(format_value):
            import json
            try:
                with open("config.json", "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception:
                config = {}
            config["log_format"] = format_value
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

        self.format_box.currentTextChanged.connect(save_format_to_config)

    def start_logging(self):
        import datetime
        selected_format = self.format_box.currentText()
        ext = ".parquet" if selected_format == "parquet" else ".csv"
        filename = self.filename_edit.text().strip()
        if not filename:
            filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ext
        else:
            # 入力値に拡張子がなければ追加
            if not filename.lower().endswith(ext):
                filename += ext
        filepath = filename  # ファイル名のみ渡す（ディレクトリはlogger側で管理）
        self.worker = LoggerWorkerThread(filepath, format=selected_format)
        self.worker.status.connect(self.label.setText)
        self.worker.update.connect(self.controller_view.update_view)
        self.worker.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.label.setText("記録開始")

    def stop_logging(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait()
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.label.setText("停止中")

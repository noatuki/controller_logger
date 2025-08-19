from PySide6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QLabel, QFileDialog,
    QGraphicsScene, QGraphicsView, QGraphicsEllipseItem
)
from PySide6.QtCore import QThread, Signal, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter

from loggers.logger_worker import LoggerWorker
from PySide6.QtCore import QThread, Signal, QTimer

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

# 入力キー表示用ビュー
class InputDisplayView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 120)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.key_labels = []

    def update_view(self, axes, buttons):
        active_keys = []

        # 左スティック（axes[0], axes[1]）8方向判定
        def stick_dir(x, y):
            if abs(x) < 0.4 and abs(y) < 0.4:
                return None
            dirs = [
                ("↑",    y < -0.7 and abs(x) < 0.5),
                ("↓",    y >  0.7 and abs(x) < 0.5),
                ("←",    x < -0.7 and abs(y) < 0.5),
                ("→",    x >  0.7 and abs(y) < 0.5),
                ("↖",    x < -0.5 and y < -0.5),
                ("↗",    x >  0.5 and y < -0.5),
                ("↙",    x < -0.5 and y >  0.5),
                ("↘",    x >  0.5 and y >  0.5),
            ]
            for label, cond in dirs:
                if cond: return label
            return None

        if len(axes) >= 2:
            dir_l = stick_dir(axes[0], axes[1])
            if dir_l: active_keys.append(f"左スティック:{dir_l}")

        # 右スティック（axes[2], axes[3]）8方向判定
        if len(axes) >= 4:
            dir_r = stick_dir(axes[2], axes[3])
            if dir_r: active_keys.append(f"右スティック:{dir_r}")

        # D-Pad（buttons配列末尾4つ: up, down, left, right）＋斜め判定
        if len(buttons) >= 4:
            up, down, left, right = buttons[-4], buttons[-3], buttons[-2], buttons[-1]
            # 斜め判定
            if up and left:
                active_keys.append("D-Pad:↖")
            if up and right:
                active_keys.append("D-Pad:↗")
            if down and left:
                active_keys.append("D-Pad:↙")
            if down and right:
                active_keys.append("D-Pad:↘")
            # 単方向
            if up and not (left or right):
                active_keys.append("D-Pad:↑")
            if down and not (left or right):
                active_keys.append("D-Pad:↓")
            if left and not (up or down):
                active_keys.append("D-Pad:←")
            if right and not (up or down):
                active_keys.append("D-Pad:→")

        # ボタン入力（ボタン数に応じて動的ラベル）
        for i, pressed in enumerate(buttons):
            if pressed and i < 12:
                active_keys.append(f"Btn{i+1}")

        # ラベル更新
        for label in self.key_labels:
            self.layout.removeWidget(label)
            label.deleteLater()
        self.key_labels.clear()
        for key in active_keys:
            lbl = QLabel(key)
            lbl.setStyleSheet("font-size:32px; color:red; font-weight:bold;")
            self.layout.addWidget(lbl)
            self.key_labels.append(lbl)

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

        self.input_display = InputDisplayView()
        layout.addWidget(self.input_display)

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
        self.worker.update.connect(self.input_display.update_view)
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

from PySide6.QtWidgets import (
    QWidget, QPushButton, QVBoxLayout, QLabel, QFileDialog,
    QGraphicsScene, QGraphicsView, QGraphicsEllipseItem,
    QDialog, QFormLayout, QHBoxLayout, QLineEdit, QComboBox,
    QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import QThread, Signal, QTimer, Qt

import time
import os
import json

from loggers.logger_worker import LoggerWorker

# PySide6用ラッパースレッド
class LoggerWorkerThread(QThread):
    status = Signal(str)
    update = Signal(object, object)  # axes, buttons

    def __init__(self, filepath, interval=0.01, format="parquet"):
        super().__init__()
        self.worker = LoggerWorker(filepath, interval, format=format)
        self._running = False

    def run(self):
        self._running = True
        last_update = 0.0
        last_status = 0.0

        def status_callback(msg):
            nonlocal last_status
            now = time.time()
            # ステータスは約2Hzで送信
            if now - last_status >= 0.5:
                self.status.emit(msg)
                last_status = now

        def update_callback(axes, buttons):
            nonlocal last_update
            now = time.time()
            # 入力更新は約30Hzで送信
            if now - last_update >= (1.0 / 30.0):
                self.update.emit(axes, buttons)
                last_update = now

        def sleep_func(interval):
            # 最低1msはスリープ
            self.msleep(max(1, int(interval * 1000)))

        self.worker.running = True
        self.worker.run(status_callback, update_callback, sleep_func)
        self._running = False

    def stop(self):
        self.worker.stop()

# 設定の読み書きヘルパー
CONFIG_PATH = "config.json"

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# 入力キー表示用ビュー
class InputDisplayView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 120)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.label = QLabel("")
        self.label.setStyleSheet("font-size:32px; color:red; font-weight:bold;")
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.layout.addWidget(self.label)

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

        text = "\n".join(active_keys) if active_keys else ""
        self.label.setText(text)

# 設定ダイアログ
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.setModal(True)

        self.cfg = load_config()

        layout = QFormLayout()

        # 記録方式
        self.format_box = QComboBox()
        self.format_box.addItems(["parquet", "csv"])
        current_format = self.cfg.get("log_format", "parquet")
        idx = self.format_box.findText(current_format)
        if idx >= 0:
            self.format_box.setCurrentIndex(idx)
        layout.addRow("記録方式", self.format_box)

        # 保存先ディレクトリ
        hbox_dir = QHBoxLayout()
        self.save_dir_edit = QLineEdit()
        self.save_dir_edit.setText(self.cfg.get("save_dir", "logs"))
        btn_browse = QPushButton("参照")
        def browse_dir():
            d = QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択", self.save_dir_edit.text() or "logs")
            if d:
                self.save_dir_edit.setText(d)
        btn_browse.clicked.connect(browse_dir)
        hbox_dir.addWidget(self.save_dir_edit)
        hbox_dir.addWidget(btn_browse)
        layout.addRow("保存先ディレクトリ", hbox_dir)

        # ファイル名テンプレート
        self.filename_template_edit = QLineEdit()
        self.filename_template_edit.setPlaceholderText("%Y%m%d_%H%M%S")
        self.filename_template_edit.setText(self.cfg.get("filename_template", "%Y%m%d_%H%M%S"))
        layout.addRow("ファイル名テンプレート", self.filename_template_edit)

        # サンプリング間隔（秒）
        self.sample_interval_spin = QDoubleSpinBox()
        self.sample_interval_spin.setRange(0.001, 1.0)
        self.sample_interval_spin.setSingleStep(0.001)
        self.sample_interval_spin.setValue(self.cfg.get("sample_interval", 0.02))
        layout.addRow("サンプリング間隔 (秒)", self.sample_interval_spin)

        # ボタン（保存/キャンセル）
        btn_hbox = QHBoxLayout()
        self.ok_btn = QPushButton("保存")
        self.cancel_btn = QPushButton("キャンセル")
        btn_hbox.addWidget(self.ok_btn)
        btn_hbox.addWidget(self.cancel_btn)
        layout.addRow(btn_hbox)

        self.setLayout(layout)

        self.ok_btn.clicked.connect(self.on_accept)
        self.cancel_btn.clicked.connect(self.reject)

    def on_accept(self):
        # 簡易バリデーション
        cfg = load_config()
        cfg["log_format"] = self.format_box.currentText()
        cfg["save_dir"] = self.save_dir_edit.text().strip() or "logs"
        cfg["filename_template"] = self.filename_template_edit.text().strip() or "%Y%m%d_%H%M%S"
        cfg["sample_interval"] = float(self.sample_interval_spin.value())

        # 保存先ディレクトリがなければ作成
        try:
            os.makedirs(cfg["save_dir"], exist_ok=True)
        except Exception:
            pass

        save_config(cfg)
        self.accept()

# メインウィンドウ
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controller Logger (PySide6)")
        self.worker = None

        self.config = load_config()

        layout = QVBoxLayout()

        # 設定表示と設定ボタン
        from PySide6.QtWidgets import QHBoxLayout as _QHBoxLayout
        h = _QHBoxLayout()
        self.format_label = QLabel(f"記録方式: {self.config.get('log_format','parquet')}")
        h.addWidget(self.format_label)
        self.settings_btn = QPushButton("設定")
        self.settings_btn.clicked.connect(self.open_settings)
        h.addWidget(self.settings_btn)
        layout.addLayout(h)

        # ファイル名入力欄（未入力なら自動生成 / テンプレ適用）
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("ファイル名（テンプレートを使用する場合は空欄）")
        layout.addWidget(QLabel("ファイル名"))
        layout.addWidget(self.filename_edit)

        self.status_label = QLabel("待機中")
        layout.addWidget(self.status_label)

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

        # UI更新タイマーと最新値バッファ
        self.latest_axes = []
        self.latest_buttons = []
        self.latest_status = "待機中"
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(33)  # 約30Hz
        self.ui_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self.ui_timer.timeout.connect(self.on_ui_timer)
        # ウィンドウ操作時の一時停止用ディファタイマー
        self._ui_defer_timer = QTimer(self)
        self._ui_defer_timer.setSingleShot(True)
        self._ui_defer_timer.setInterval(200)  # 操作終了後に再開
        self._ui_defer_timer.timeout.connect(self._resume_ui_updates)

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            # 設定を再読み込みして反映
            self.config = load_config()
            self.format_label.setText(f"記録方式: {self.config.get('log_format','parquet')}")
            # 変更されたサンプリング間隔はワーカー起動時に利用される

    def start_logging(self):
        import datetime
        selected_format = self.config.get("log_format", "parquet")
        ext = ".parquet" if selected_format == "parquet" else ".csv"
        filename = self.filename_edit.text().strip()
        if not filename:
            # テンプレート対応
            template = self.config.get("filename_template", "%Y%m%d_%H%M%S")
            filename = datetime.datetime.now().strftime(template) + ext
        else:
            # 入力値に拡張子がなければ追加
            if not filename.lower().endswith(ext):
                filename += ext
        save_dir = self.config.get("save_dir", "logs")
        filepath = os.path.join(save_dir, filename)
        interval = float(self.config.get("sample_interval", 0.02))
        self.worker = LoggerWorkerThread(filepath, interval=interval, format=selected_format)  # サンプリング間隔を使用
        # 高頻度シグナルはバッファに保存し、UIはタイマーで更新
        self.worker.status.connect(self.on_worker_status)
        self.worker.update.connect(self.on_worker_update)
        self.worker.start()
        # UIタイマー開始（約30Hz）
        self.latest_status = "記録開始"
        if hasattr(self, "ui_timer"):
            self.ui_timer.start()
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.status_label.setText("記録開始")

    def stop_logging(self):
        # UIタイマー停止
        if hasattr(self, "ui_timer"):
            self.ui_timer.stop()
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.latest_status = "停止中"
        self.status_label.setText("停止中")

    # ワーカーの最新入力をバッファ
    def on_worker_update(self, axes, buttons):
        self.latest_axes = list(axes)
        self.latest_buttons = list(buttons)

    # ワーカーのステータス文字列をバッファ
    def on_worker_status(self, msg):
        self.latest_status = msg

    # UIタイマーで表示更新（約30Hz）
    def on_ui_timer(self):
        try:
            self.input_display.update_view(self.latest_axes, self.latest_buttons)
        except Exception:
            pass
        self.status_label.setText(self.latest_status)

    # ウィンドウ操作中はUI更新を一時停止し、操作完了後に再開
    def _pause_ui_updates_temporarily(self):
        if self.ui_timer.isActive():
            self.ui_timer.stop()
        # 画面更新を抑止（レイアウト・再描画を止める）
        self.setUpdatesEnabled(False)
        self._ui_defer_timer.start()

    def _resume_ui_updates(self):
        # 画面更新を再開
        self.setUpdatesEnabled(True)
        self.update()
        if self.worker:
            self.ui_timer.start()

    def resizeEvent(self, event):
        self._pause_ui_updates_temporarily()
        super().resizeEvent(event)

    def moveEvent(self, event):
        self._pause_ui_updates_temporarily()
        super().moveEvent(event)

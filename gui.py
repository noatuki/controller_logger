from PySide6.QtWidgets import (
    QMainWindow, QWidget, QPushButton, QVBoxLayout, QLabel, QFileDialog,
    QDialog, QFormLayout, QHBoxLayout, QLineEdit, QComboBox,
    QDoubleSpinBox, QListWidget, QListWidgetItem, QTabWidget, QToolBar,
    QStatusBar, QSystemTrayIcon, QMenu, QStyle, QSplitter, QFrame,
    QSizePolicy, QSpacerItem, QAbstractItemView, QTableView, QHeaderView, QMessageBox,
    QGroupBox, QRadioButton, QSlider, QButtonGroup
)
from PySide6.QtCore import QThread, Signal, QTimer, Qt, QSize, QAbstractTableModel, QModelIndex
from PySide6.QtGui import QIcon, QGuiApplication, QAction, QShortcut, QKeySequence

import time
import os
import json
import pandas as pd
import datetime
import sys

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

# 入力キー表示用ビュー（改良）
class InputDisplayView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 220)
        root = QVBoxLayout(self)
        title = QLabel("コントローラ入力")
        title.setStyleSheet("font-size:14px; font-weight:600;")
        root.addWidget(title)

        self.label = QLabel("")
        self.label.setStyleSheet(
            "font-size:28px; color:#E57373; font-weight:700;"
            "padding:8px; border-radius:8px; background:rgba(255,255,255,0.05);"
        )
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        root.addWidget(self.label, 1)

        self.axes_label = QLabel("Axes: []")
        self.axes_label.setStyleSheet("color:#B0BEC5;")
        root.addWidget(self.axes_label)

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
                if cond:
                    return label
            return None

        if len(axes) >= 2:
            dir_l = stick_dir(axes[0], axes[1])
            if dir_l:
                active_keys.append(f"左スティック:{dir_l}")

        # 右スティック（axes[2], axes[3]）8方向判定
        if len(axes) >= 4:
            dir_r = stick_dir(axes[2], axes[3])
            if dir_r:
                active_keys.append(f"右スティック:{dir_r}")

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

        text = "  ".join(active_keys) if active_keys else ""
        self.label.setText(text)
        self.axes_label.setText(f"Axes: {[round(a,3) for a in axes]}")

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

class SettingsPanel(QWidget):
    saved = Signal(dict)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = dict(cfg) if cfg else {}
        root = QVBoxLayout(self)

        # 記録方式
        gb_format = QGroupBox("記録方式")
        f_l = QHBoxLayout()
        self.radio_parquet = QRadioButton("parquet")
        self.radio_csv = QRadioButton("csv")
        fmt = self._cfg.get("log_format", "parquet")
        (self.radio_parquet if fmt == "parquet" else self.radio_csv).setChecked(True)
        f_l.addWidget(self.radio_parquet)
        f_l.addWidget(self.radio_csv)
        f_l.addStretch(1)
        gb_format.setLayout(f_l)
        root.addWidget(gb_format)

        # 保存先ディレクトリ
        gb_dir = QGroupBox("保存先ディレクトリ")
        d_l = QHBoxLayout()
        self.edit_dir = QLineEdit(self._cfg.get("save_dir", "logs"))
        self.btn_browse = QPushButton("参照")
        self.dir_status = QLabel("")
        self.dir_status.setStyleSheet("color:#B0BEC5;")
        d_l.addWidget(self.edit_dir, 1)
        d_l.addWidget(self.btn_browse)
        d_l.addWidget(self.dir_status)
        gb_dir.setLayout(d_l)
        root.addWidget(gb_dir)

        # ファイル名テンプレート
        gb_tmpl = QGroupBox("ファイル名テンプレート")
        t_l = QVBoxLayout()
        row = QHBoxLayout()
        self.edit_tmpl = QLineEdit(self._cfg.get("filename_template", "%Y%m%d_%H%M%S"))
        self.edit_tmpl.setPlaceholderText("%Y%m%d_%H%M%S")
        self.preview_label = QLabel("例: -")
        self.preview_label.setStyleSheet("color:#B0BEC5;")
        row.addWidget(self.edit_tmpl, 1)
        t_l.addLayout(row)
        t_l.addWidget(self.preview_label)
        gb_tmpl.setLayout(t_l)
        root.addWidget(gb_tmpl)

        # サンプリング間隔
        gb_sample = QGroupBox("サンプリング間隔")
        s_l = QHBoxLayout()
        self.slider_ms = QSlider(Qt.Horizontal)
        self.slider_ms.setRange(1, 1000)  # 1ms - 1000ms
        ms = int(float(self._cfg.get("sample_interval", 0.02)) * 1000)
        self.slider_ms.setValue(max(1, min(1000, ms)))
        self.spin_sec = QDoubleSpinBox()
        self.spin_sec.setRange(0.001, 1.0)
        self.spin_sec.setSingleStep(0.001)
        self.spin_sec.setDecimals(3)
        self.spin_sec.setValue(self.slider_ms.value() / 1000.0)
        self.hz_label = QLabel("")
        self.hz_label.setStyleSheet("color:#B0BEC5;")
        s_l.addWidget(QLabel("ms:"))
        s_l.addWidget(self.slider_ms, 1)
        s_l.addSpacing(8)
        s_l.addWidget(QLabel("sec:"))
        s_l.addWidget(self.spin_sec)
        s_l.addSpacing(8)
        s_l.addWidget(self.hz_label)
        gb_sample.setLayout(s_l)
        root.addWidget(gb_sample)

        # ボタン
        btns = QHBoxLayout()
        self.btn_apply = QPushButton("適用")
        self.btn_reset = QPushButton("リセット")
        self.btn_defaults = QPushButton("初期値に戻す")
        btns.addStretch(1)
        btns.addWidget(self.btn_defaults)
        btns.addWidget(self.btn_reset)
        btns.addWidget(self.btn_apply)
        root.addLayout(btns)

        # 接続
        self.btn_browse.clicked.connect(self._browse_dir)
        self.edit_dir.textChanged.connect(self._update_dir_status)
        self.radio_parquet.toggled.connect(self._update_preview)
        self.radio_csv.toggled.connect(self._update_preview)
        self.edit_tmpl.textChanged.connect(self._update_preview)
        self.slider_ms.valueChanged.connect(self._sync_from_slider)
        self.spin_sec.valueChanged.connect(self._sync_from_spin)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_defaults.clicked.connect(self._defaults)

        # 初期表示
        self._update_dir_status()
        self._update_preview()
        self._update_hz()

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択", self.edit_dir.text() or "logs")
        if d:
            self.edit_dir.setText(d)

    def _update_dir_status(self):
        d = self.edit_dir.text().strip()
        if os.path.isdir(d):
            self.dir_status.setText("存在します")
            self.dir_status.setStyleSheet("color:#8BC34A;")
        else:
            self.dir_status.setText("未作成（保存時に作成）")
            self.dir_status.setStyleSheet("color:#FFC107;")

    def _current_ext(self):
        return ".parquet" if self.radio_parquet.isChecked() else ".csv"

    def _update_preview(self):
        try:
            now = datetime.datetime.now()
            tmpl = self.edit_tmpl.text().strip() or "%Y%m%d_%H%M%S"
            name = now.strftime(tmpl) + self._current_ext()
            self.preview_label.setText(f"例: {name}")
        except Exception:
            self.preview_label.setText("例: -")

    def _update_hz(self):
        sec = max(0.001, float(self.spin_sec.value()))
        hz = 1.0 / sec
        self.hz_label.setText(f"{hz:.1f} Hz")

    def _sync_from_slider(self, v: int):
        self.spin_sec.blockSignals(True)
        self.spin_sec.setValue(v / 1000.0)
        self.spin_sec.blockSignals(False)
        self._update_hz()

    def _sync_from_spin(self, v: float):
        val = int(max(1, min(1000, int(round(v * 1000)))))
        self.slider_ms.blockSignals(True)
        self.slider_ms.setValue(val)
        self.slider_ms.blockSignals(False)
        self._update_hz()

    def _apply(self):
        cfg = load_config()
        cfg["log_format"] = "parquet" if self.radio_parquet.isChecked() else "csv"
        cfg["save_dir"] = self.edit_dir.text().strip() or "logs"
        cfg["filename_template"] = self.edit_tmpl.text().strip() or "%Y%m%d_%H%M%S"
        cfg["sample_interval"] = float(self.spin_sec.value())
        try:
            os.makedirs(cfg["save_dir"], exist_ok=True)
        except Exception:
            pass
        save_config(cfg)
        self.saved.emit(cfg)

    def _reset(self):
        cfg = load_config()
        self.radio_parquet.setChecked(cfg.get("log_format", "parquet") == "parquet")
        self.radio_csv.setChecked(cfg.get("log_format", "parquet") == "csv")
        self.edit_dir.setText(cfg.get("save_dir", "logs"))
        self.edit_tmpl.setText(cfg.get("filename_template", "%Y%m%d_%H%M%S"))
        self.spin_sec.setValue(float(cfg.get("sample_interval", 0.02)))
        self._update_preview()
        self._update_dir_status()
        self._update_hz()

    def _defaults(self):
        self.radio_parquet.setChecked(True)
        self.radio_csv.setChecked(False)
        self.edit_dir.setText("logs")
        self.edit_tmpl.setText("%Y%m%d_%H%M%S")
        self.spin_sec.setValue(0.02)
        self._update_preview()
        self._update_dir_status()
        self._update_hz()

class DataFrameModel(QAbstractTableModel):
    def __init__(self, df: "pd.DataFrame|None" = None, parent=None, float_format="{:.3f}".format):
        super().__init__(parent)
        self._df = df if df is not None else pd.DataFrame()
        self._float_format = float_format

    def setDataFrame(self, df: "pd.DataFrame"):
        self.beginResetModel()
        self._df = df
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df.index)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or role != Qt.DisplayRole:
            return None
        val = self._df.iat[index.row(), index.column()]
        if pd.isna(val):
            return ""
        if isinstance(val, float):
            try:
                return self._float_format(val)
            except Exception:
                return str(val)
        return str(val)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if 0 <= section < len(self._df.columns):
                return str(self._df.columns[section])
        else:
            # 1-based row numbers for readability
            return str(section + 1)
        return None

class SettingsPanel(QWidget):
    saved = Signal(dict)

    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self._cfg = dict(cfg) if cfg else {}
        root = QVBoxLayout(self)

        # 記録方式
        gb_format = QGroupBox("記録方式")
        f_l = QHBoxLayout()
        self.radio_parquet = QRadioButton("parquet")
        self.radio_csv = QRadioButton("csv")
        fmt = self._cfg.get("log_format", "parquet")
        (self.radio_parquet if fmt == "parquet" else self.radio_csv).setChecked(True)
        f_l.addWidget(self.radio_parquet)
        f_l.addWidget(self.radio_csv)
        f_l.addStretch(1)
        gb_format.setLayout(f_l)
        root.addWidget(gb_format)

        # 保存先ディレクトリ
        gb_dir = QGroupBox("保存先ディレクトリ")
        d_l = QHBoxLayout()
        self.edit_dir = QLineEdit(self._cfg.get("save_dir", "logs"))
        self.btn_browse = QPushButton("参照")
        self.dir_status = QLabel("")
        self.dir_status.setStyleSheet("color:#B0BEC5;")
        d_l.addWidget(self.edit_dir, 1)
        d_l.addWidget(self.btn_browse)
        d_l.addWidget(self.dir_status)
        gb_dir.setLayout(d_l)
        root.addWidget(gb_dir)

        # ファイル名テンプレート
        gb_tmpl = QGroupBox("ファイル名テンプレート")
        t_l = QVBoxLayout()
        row = QHBoxLayout()
        self.edit_tmpl = QLineEdit(self._cfg.get("filename_template", "%Y%m%d_%H%M%S"))
        self.edit_tmpl.setPlaceholderText("%Y%m%d_%H%M%S")
        self.preview_label = QLabel("例: -")
        self.preview_label.setStyleSheet("color:#B0BEC5;")
        row.addWidget(self.edit_tmpl, 1)
        t_l.addLayout(row)
        t_l.addWidget(self.preview_label)
        gb_tmpl.setLayout(t_l)
        root.addWidget(gb_tmpl)

        # サンプリング間隔
        gb_sample = QGroupBox("サンプリング間隔")
        s_l = QHBoxLayout()
        self.slider_ms = QSlider(Qt.Horizontal)
        self.slider_ms.setRange(1, 1000)  # 1ms - 1000ms
        ms = int(float(self._cfg.get("sample_interval", 0.02)) * 1000)
        self.slider_ms.setValue(max(1, min(1000, ms)))
        self.spin_sec = QDoubleSpinBox()
        self.spin_sec.setRange(0.001, 1.0)
        self.spin_sec.setSingleStep(0.001)
        self.spin_sec.setDecimals(3)
        self.spin_sec.setValue(self.slider_ms.value() / 1000.0)
        self.hz_label = QLabel("")
        self.hz_label.setStyleSheet("color:#B0BEC5;")
        s_l.addWidget(QLabel("ms:"))
        s_l.addWidget(self.slider_ms, 1)
        s_l.addSpacing(8)
        s_l.addWidget(QLabel("sec:"))
        s_l.addWidget(self.spin_sec)
        s_l.addSpacing(8)
        s_l.addWidget(self.hz_label)
        gb_sample.setLayout(s_l)
        root.addWidget(gb_sample)

        # ボタン
        btns = QHBoxLayout()
        self.btn_apply = QPushButton("適用")
        self.btn_reset = QPushButton("リセット")
        self.btn_defaults = QPushButton("初期値に戻す")
        btns.addStretch(1)
        btns.addWidget(self.btn_defaults)
        btns.addWidget(self.btn_reset)
        btns.addWidget(self.btn_apply)
        root.addLayout(btns)

        # 接続
        self.btn_browse.clicked.connect(self._browse_dir)
        self.edit_dir.textChanged.connect(self._update_dir_status)
        self.radio_parquet.toggled.connect(self._update_preview)
        self.radio_csv.toggled.connect(self._update_preview)
        self.edit_tmpl.textChanged.connect(self._update_preview)
        self.slider_ms.valueChanged.connect(self._sync_from_slider)
        self.spin_sec.valueChanged.connect(self._sync_from_spin)
        self.btn_apply.clicked.connect(self._apply)
        self.btn_reset.clicked.connect(self._reset)
        self.btn_defaults.clicked.connect(self._defaults)

        # 初期表示
        self._update_dir_status()
        self._update_preview()
        self._update_hz()

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択", self.edit_dir.text() or "logs")
        if d:
            self.edit_dir.setText(d)

    def _update_dir_status(self):
        d = self.edit_dir.text().strip()
        if os.path.isdir(d):
            self.dir_status.setText("存在します")
            self.dir_status.setStyleSheet("color:#8BC34A;")
        else:
            self.dir_status.setText("未作成（保存時に作成）")
            self.dir_status.setStyleSheet("color:#FFC107;")

    def _current_ext(self):
        return ".parquet" if self.radio_parquet.isChecked() else ".csv"

    def _update_preview(self):
        try:
            now = datetime.datetime.now()
            tmpl = self.edit_tmpl.text().strip() or "%Y%m%d_%H%M%S"
            name = now.strftime(tmpl) + self._current_ext()
            self.preview_label.setText(f"例: {name}")
        except Exception:
            self.preview_label.setText("例: -")

    def _update_hz(self):
        sec = max(0.001, float(self.spin_sec.value()))
        hz = 1.0 / sec
        self.hz_label.setText(f"{hz:.1f} Hz")

    def _sync_from_slider(self, v: int):
        self.spin_sec.blockSignals(True)
        self.spin_sec.setValue(v / 1000.0)
        self.spin_sec.blockSignals(False)
        self._update_hz()

    def _sync_from_spin(self, v: float):
        val = int(max(1, min(1000, int(round(v * 1000)))))
        self.slider_ms.blockSignals(True)
        self.slider_ms.setValue(val)
        self.slider_ms.blockSignals(False)
        self._update_hz()

    def _apply(self):
        cfg = load_config()
        cfg["log_format"] = "parquet" if self.radio_parquet.isChecked() else "csv"
        cfg["save_dir"] = self.edit_dir.text().strip() or "logs"
        cfg["filename_template"] = self.edit_tmpl.text().strip() or "%Y%m%d_%H%M%S"
        cfg["sample_interval"] = float(self.spin_sec.value())
        try:
            os.makedirs(cfg["save_dir"], exist_ok=True)
        except Exception:
            pass
        save_config(cfg)
        self.saved.emit(cfg)

    def _reset(self):
        cfg = load_config()
        self.radio_parquet.setChecked(cfg.get("log_format", "parquet") == "parquet")
        self.radio_csv.setChecked(cfg.get("log_format", "parquet") == "csv")
        self.edit_dir.setText(cfg.get("save_dir", "logs"))
        self.edit_tmpl.setText(cfg.get("filename_template", "%Y%m%d_%H%M%S"))
        self.spin_sec.setValue(float(cfg.get("sample_interval", 0.02)))
        self._update_preview()
        self._update_dir_status()
        self._update_hz()

    def _defaults(self):
        self.radio_parquet.setChecked(True)
        self.radio_csv.setChecked(False)
        self.edit_dir.setText("logs")
        self.edit_tmpl.setText("%Y%m%d_%H%M%S")
        self.spin_sec.setValue(0.02)
        self._update_preview()
        self._update_dir_status()
        self._update_hz()

class SessionListPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._max_preview_rows = 1000

        # 左: ファイル一覧 + 操作
        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.list.itemActivated.connect(self.open_item)
        self.list.itemSelectionChanged.connect(self._on_selection_changed)

        left_box = QWidget()
        left_v = QVBoxLayout(left_box)
        btns = QHBoxLayout()
        self.refresh_btn = QPushButton("更新")
        self.open_dir_btn = QPushButton("フォルダを開く")
        self.open_ext_btn = QPushButton("外部で開く")
        self.delete_btn = QPushButton("削除")
        btns.addWidget(self.refresh_btn)
        btns.addWidget(self.open_dir_btn)
        btns.addWidget(self.open_ext_btn)
        btns.addWidget(self.delete_btn)
        btns.addStretch(1)
        left_v.addLayout(btns)
        left_v.addWidget(self.list, 1)

        # 右: プレビュー
        right_box = QWidget()
        right_v = QVBoxLayout(right_box)
        self.preview_info = QLabel("プレビュー: -")
        self.preview_info.setStyleSheet("color:#B0BEC5;")
        right_v.addWidget(self.preview_info)
        self.table = QTableView()
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setWordWrap(False)
        self.table.setEditTriggers(QTableView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.verticalHeader().setVisible(True)
        self._df_model = DataFrameModel(pd.DataFrame())
        self.table.setModel(self._df_model)
        right_v.addWidget(self.table, 1)

        # スプリッタで左右に配置
        split = QSplitter()
        split.addWidget(left_box)
        split.addWidget(right_box)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(split)

        # イベント
        self.refresh_btn.clicked.connect(self.reload)
        self.open_dir_btn.clicked.connect(self.open_folder)
        self.open_ext_btn.clicked.connect(self._open_selected_external)
        self.delete_btn.clicked.connect(self.delete_selected)

    def set_directory(self, path: str):
        self._dir = path
        self.reload()

    def reload(self):
        self.list.clear()
        d = getattr(self, "_dir", "logs")
        try:
            os.makedirs(d, exist_ok=True)
            files = [f for f in os.listdir(d) if f.lower().endswith((".parquet", ".csv"))]
            files.sort(reverse=True)
            for f in files:
                item = QListWidgetItem(f)
                self.list.addItem(item)
            # 初期選択で即プレビュー
            if self.list.count() > 0:
                self.list.setCurrentRow(0)
        except Exception:
            pass

    def _current_path(self):
        d = getattr(self, "_dir", "logs")
        item = self.list.currentItem()
        if not item:
            return None
        return os.path.join(d, item.text())

    def _on_selection_changed(self):
        self._load_preview(self._current_path())

    def _load_preview(self, path: str | None):
        if not path or not os.path.exists(path):
            self._df_model.setDataFrame(pd.DataFrame())
            self.preview_info.setText("プレビュー: -")
            return
        try:
            ext = os.path.splitext(path)[1].lower()
            if ext == ".csv":
                df = pd.read_csv(path, nrows=self._max_preview_rows)
            elif ext == ".parquet":
                df = pd.read_parquet(path)
                if len(df) > self._max_preview_rows:
                    df = df.head(self._max_preview_rows)
            else:
                df = pd.DataFrame()
            self._df_model.setDataFrame(df)
            note = "(先頭 {}/{} 行表示)".format(len(df), "?" if ext == ".csv" and len(df) == self._max_preview_rows else len(df))
            self.preview_info.setText(f"プレビュー: {os.path.basename(path)} {note}")
        except Exception as e:
            self._df_model.setDataFrame(pd.DataFrame())
            self.preview_info.setText(f"プレビュー失敗: {os.path.basename(path)} ({e})")

    def open_folder(self):
        d = getattr(self, "_dir", "logs")
        if sys.platform.startswith("win"):
            os.startfile(os.path.abspath(d))
        elif sys.platform == "darwin":
            os.system(f'open "{os.path.abspath(d)}"')
        else:
            os.system(f'xdg-open "{os.path.abspath(d)}"')

    def _open_selected_external(self):
        item = self.list.currentItem()
        if item:
            self.open_item(item)

    def delete_selected(self):
        path = self._current_path()
        if not path or not os.path.exists(path):
            return
        name = os.path.basename(path)
        reply = QMessageBox.question(
            self,
            "削除の確認",
            f"{name} を削除しますか？\nこの操作は取り消せません。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                os.remove(path)
            except Exception as e:
                QMessageBox.warning(self, "削除失敗", f"削除に失敗しました:\n{e}")
                return
            # リストとプレビューを更新
            self.reload()
            self._df_model.setDataFrame(pd.DataFrame())
            self.preview_info.setText("プレビュー: -")

    def open_item(self, item: QListWidgetItem):
        d = getattr(self, "_dir", "logs")
        path = os.path.join(d, item.text())
        if os.path.exists(path):
            if sys.platform.startswith("win"):
                os.startfile(os.path.abspath(path))
            elif sys.platform == "darwin":
                os.system(f'open "{os.path.abspath(path)}"')
            else:
                os.system(f'xdg-open "{os.path.abspath(path)}"')

class Sidebar(QWidget):
    collapsed_changed = Signal(bool)
    
    def __init__(self, on_navigate, parent=None):
        super().__init__(parent)
        self.setFixedWidth(240)
        self.setObjectName("Sidebar")
        self._collapsed = False
    
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)
    
        # ヘッダー（アイコン＋タイトル＋設定ショートカット）
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        icon_label = QLabel()
        icon_label.setPixmap(self.style().standardIcon(QStyle.SP_ComputerIcon).pixmap(18, 18))
        self.title_label = QLabel("Controller Logger")
        self.title_label.setObjectName("sidebarTitle")
        self.title_label.setStyleSheet("font-size:15px; font-weight:700;")
        header.addWidget(icon_label)
        header.addSpacing(6)
        header.addWidget(self.title_label, 1)
        self.btn_quick_settings = QPushButton()
        self.btn_quick_settings.setObjectName("sidebarGear")
        self.btn_quick_settings.setToolTip("設定")
        self.btn_quick_settings.setIcon(self.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        self.btn_quick_settings.setCursor(Qt.PointingHandCursor)
        self.btn_quick_settings.setFlat(True)
        self.btn_quick_settings.setFixedSize(28, 24)
        self.btn_quick_settings.clicked.connect(lambda: on_navigate(2))
        header.addWidget(self.btn_quick_settings)
        root.addLayout(header)
    
        # セパレータ
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)
    
        # ナビゲーションボタン（アイコン付き・排他）
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self._nav_buttons = []
    
        def make_btn(text: str, icon: QIcon, idx: int):
            b = QPushButton(text)
            b.setObjectName("navBtn")
            b.setIcon(icon)
            b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.PointingHandCursor)
            b.setCheckable(True)
            b.setToolTip(text)
            b.clicked.connect(lambda: on_navigate(idx))
            self.group.addButton(b, idx)
            root.addWidget(b)
            self._nav_buttons.append(b)
            return b
    
        style = self.style()
        self.btn_live = make_btn("Controller入力", style.standardIcon(QStyle.SP_MediaPlay), 0)
        self.btn_sessions = make_btn("Logファイル", style.standardIcon(QStyle.SP_DirOpenIcon), 1)
        self.btn_settings = make_btn("設定", style.standardIcon(QStyle.SP_FileDialogDetailedView), 2)
    
        # 余白で下に押し下げ
        root.addStretch(1)
    
        # 折りたたみボタン
        self.btn_collapse = QPushButton("サイドバーを折りたたむ")
        self.btn_collapse.setObjectName("navBtn")
        self.btn_collapse.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        self.btn_collapse.setCursor(Qt.PointingHandCursor)
        self.btn_collapse.clicked.connect(self.toggle_collapsed)
        root.addWidget(self.btn_collapse)
    
        # 既定選択
        self.btn_live.setChecked(True)
    
    def set_active(self, idx: int):
        self.btn_live.setChecked(idx == 0)
        self.btn_sessions.setChecked(idx == 1)
        self.btn_settings.setChecked(idx == 2)
    
    def set_collapsed(self, collapsed: bool):
        self._collapsed = bool(collapsed)
        if self._collapsed:
            self.setFixedWidth(64)
            self.title_label.setVisible(False)
            for b in self._nav_buttons:
                b.setText("")
            self.btn_collapse.setText("展開")
            self.btn_collapse.setIcon(self.style().standardIcon(QStyle.SP_ArrowRight))
        else:
            self.setFixedWidth(240)
            self.title_label.setVisible(True)
            self.btn_live.setText("Controller入力")
            self.btn_sessions.setText("Logファイル")
            self.btn_settings.setText("設定")
            self.btn_collapse.setText("サイドバーを折りたたむ")
            self.btn_collapse.setIcon(self.style().standardIcon(QStyle.SP_ArrowLeft))
        self.collapsed_changed.emit(self._collapsed)
    
    def toggle_collapsed(self):
        self.set_collapsed(not self._collapsed)

# メインウィンドウ
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Controller Logger")
        self.setWindowIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self.setMinimumSize(900, 600)
        self._force_quit = False
        self.worker = None

        self.config = load_config()

        # ツールバー
        self.toolbar = QToolBar("Main")
        self.toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        style = self.style()
        self.action_start = QAction(style.standardIcon(QStyle.SP_MediaPlay), "記録開始", self)
        self.action_stop = QAction(style.standardIcon(QStyle.SP_MediaStop), "記録停止", self)
        self.action_stop.setEnabled(False)
        self.action_settings = QAction(style.standardIcon(QStyle.SP_FileDialogDetailedView), "設定", self)

        self.toolbar.addAction(self.action_start)
        self.toolbar.addAction(self.action_stop)
        self.toolbar.addSeparator()
        # ツールボタンの表示とスタイル識別子
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.btn_start = self.toolbar.widgetForAction(self.action_start)
        self.btn_stop = self.toolbar.widgetForAction(self.action_stop)
        if self.btn_start:
            self.btn_start.setObjectName("btnStart")
        if self.btn_stop:
            self.btn_stop.setObjectName("btnStop")

        # ファイル名入力
        self.filename_edit = QLineEdit()
        self.filename_edit.setPlaceholderText("ファイル名（空欄でテンプレ適用）")
        self.filename_edit.setFixedWidth(240)
        self.toolbar.addWidget(QLabel("ファイル名:"))
        self.toolbar.addWidget(self.filename_edit)

        # 保存先
        self.save_dir_btn = QPushButton("保存先…")
        self.toolbar.addSeparator()
        self.toolbar.addWidget(self.save_dir_btn)

        # 記録方式ラベル
        self.format_label = QLabel(f"記録方式: {self.config.get('log_format','parquet')}")
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.format_label)
        self.toolbar.addAction(self.action_settings)

        # サイドバー + タブ
        self.sidebar = Sidebar(self._navigate)
        # 折りたたみ状態の復元
        try:
            self.sidebar.set_collapsed(bool(self.config.get("sidebar_collapsed", False)))
        except Exception:
            pass
        self.sidebar.collapsed_changed.connect(self._on_sidebar_collapsed)

        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)

        # LIVEタブ
        live_tab = QWidget()
        live_layout = QVBoxLayout(live_tab)
        self.status_label = QLabel("待機中")
        self.input_display = InputDisplayView()
        live_layout.addWidget(self.status_label)
        live_layout.addWidget(self.input_display, 1)
        self.tabs.addTab(live_tab, "Controller入力")

        # Logファイルタブ
        self.sessions_panel = SessionListPanel()
        self.sessions_panel.set_directory(self.config.get("save_dir", "logs"))
        self.tabs.addTab(self.sessions_panel, "Logファイル")

        # 設定タブ（リッチ編集UI）
        self.settings_panel = SettingsPanel(self.config)
        self.settings_panel.saved.connect(self._on_settings_saved)
        self.tabs.addTab(self.settings_panel, "設定")

        # スプリッタ
        splitter = QSplitter()
        sidebar_frame = QFrame()
        sidebar_frame.setLayout(QVBoxLayout())
        sidebar_frame.layout().addWidget(self.sidebar)
        splitter.addWidget(sidebar_frame)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        central = QWidget()
        c_layout = QVBoxLayout(central)
        c_layout.addWidget(splitter)
        self.setCentralWidget(central)

        # ステータスバー
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.status_info = QLabel("Ready")
        self.statusbar.addPermanentWidget(self.status_info)

        # システムトレイ
        self.tray = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(self)
            self.tray.setIcon(style.standardIcon(QStyle.SP_ComputerIcon))
            menu = QMenu()
            a_show = QAction("表示", self)
            a_hide = QAction("最小化", self)
            a_start = QAction("記録開始", self)
            a_stop = QAction("記録停止", self)
            a_quit = QAction("終了", self)
            menu.addAction(a_show)
            menu.addAction(a_hide)
            menu.addSeparator()
            menu.addAction(a_start)
            menu.addAction(a_stop)
            menu.addSeparator()
            menu.addAction(a_quit)
            self.tray.setContextMenu(menu)
            self.tray.show()

            a_show.triggered.connect(self.showNormal)
            a_hide.triggered.connect(self.hide)
            a_start.triggered.connect(self._start_from_tray)
            a_stop.triggered.connect(self._stop_from_tray)
            a_quit.triggered.connect(self._quit_app)

        # イベント接続
        self.action_start.triggered.connect(self.start_logging)
        self.action_stop.triggered.connect(self.stop_logging)
        self.action_settings.triggered.connect(lambda: self._navigate(2))
        self.save_dir_btn.clicked.connect(self.choose_save_dir)
        # 設定はインライン編集に変更
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # キーボードショートカット (Ctrl+1/2/3)
        try:
            QShortcut(QKeySequence("Ctrl+1"), self, activated=lambda: self._navigate(0))
            QShortcut(QKeySequence("Ctrl+2"), self, activated=lambda: self._navigate(1))
            QShortcut(QKeySequence("Ctrl+3"), self, activated=lambda: self._navigate(2))
        except Exception:
            pass

        # UI更新タイマーと最新値バッファ
        self.latest_axes = []
        self.latest_buttons = []
        self.latest_status = "待機中"
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(33)  # 約30Hz
        self.ui_timer.setTimerType(Qt.TimerType.CoarseTimer)
        self.ui_timer.timeout.connect(self.on_ui_timer)

        # 終了時のリソースクリーンアップ
        try:
            QGuiApplication.instance().aboutToQuit.connect(self._cleanup_resources)
        except Exception:
            pass

        # 初期反映
        self._update_settings_summary()
        self._apply_styles()

    # 見た目
    def _apply_styles(self):
        self.setStyleSheet("""
            /* 全体の前景色を白寄りにしてコントラスト改善 */
            QWidget { color:#FFFFFF; }
            QMainWindow {
                background:#181A1B;
            }
            /* ツールバー/ステータスバーは少し明るめ */
            QToolBar {
                background:#202225;
                spacing:6px;
                padding:6px;
                border:0;
            }
            QStatusBar {
                background:#202225;
                border:0;
            }
            /* サイドバー */
            QWidget#Sidebar {
                background:#23262A;
            }
            QLabel#sidebarTitle {
                color:#FFFFFF;
            }
            /* サイドバー内ナビボタン */
            QWidget#Sidebar QPushButton#navBtn {
                background:transparent;
                color:#FFFFFF;
                text-align:left;
                padding:10px 12px;
                border:0;
                border-radius:8px;
                margin:2px 0;
            }
            QWidget#Sidebar QPushButton#navBtn:hover {
                background:#2A2E33;
            }
            QWidget#Sidebar QPushButton#navBtn:checked {
                background:#2D3136;
                border-left:3px solid #5E9CFF;
            }
            QWidget#Sidebar QPushButton#navBtn:disabled {
                color:rgba(255,255,255,0.6);
            }
            /* サイドバーのクイック設定アイコン */
            QWidget#Sidebar QPushButton#sidebarGear {
                background:transparent;
                border:0;
                border-radius:6px;
                padding:4px;
            }
            QWidget#Sidebar QPushButton#sidebarGear:hover {
                background:#2A2E33;
            }

            /* ツールバーの開始/停止ボタンにカラー付与 */
            QToolBar QToolButton {
                color:#FFFFFF;
            }
            QToolBar QToolButton#btnStart {
                background:#2E7D32; /* green 800 */
                border:1px solid #1B5E20;
                border-radius:6px;
                padding:6px 10px;
            }
            QToolBar QToolButton#btnStart:hover {
                background:#388E3C;
            }
            QToolBar QToolButton#btnStart:pressed {
                background:#1B5E20;
            }
            QToolBar QToolButton#btnStart:disabled {
                background:#2E7D32;
                color:rgba(255,255,255,0.55);
                border-color:#1B5E20;
            }
            QToolBar QToolButton#btnStop {
                background:#C62828; /* red 800 */
                border:1px solid #8E0000;
                border-radius:6px;
                padding:6px 10px;
            }
            QToolBar QToolButton#btnStop:hover {
                background:#D32F2F;
            }
            QToolBar QToolButton#btnStop:pressed {
                background:#B71C1C;
            }
            QToolBar QToolButton#btnStop:disabled {
                background:#8E3434;
                color:rgba(255,255,255,0.60);
                border-color:#7F1F1F;
            }

            /* 入力系の視認性を改善 */
            QLineEdit {
                background:#2A2D31; color:#FFFFFF; border:1px solid #3A3F44; border-radius:6px; padding:6px;
            }
            QListWidget {
                background:#1E2124; color:#FFFFFF; border:1px solid #2E3338; border-radius:6px;
            }
            QTabBar::tab {
                background:#23262A; color:#FFFFFF; padding:8px 12px; border-top-left-radius:6px; border-top-right-radius:6px;
            }
            QTabBar::tab:selected {
                background:#2D3136;
            }
        """)

    # ナビ
    def _navigate(self, idx: int):
        self.tabs.setCurrentIndex(idx)
        self.sidebar.set_active(idx)

    def _on_tab_changed(self, idx: int):
        self.sidebar.set_active(idx)

    def choose_save_dir(self):
        d = QFileDialog.getExistingDirectory(self, "保存先ディレクトリを選択", self.config.get("save_dir", "logs"))
        if d:
            self.config["save_dir"] = d
            save_config(self.config)
            self.sessions_panel.set_directory(d)

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            # 設定を再読み込みして反映
            self.config = load_config()
            self.format_label.setText(f"記録方式: {self.config.get('log_format','parquet')}")
            self.sessions_panel.set_directory(self.config.get("save_dir", "logs"))
            self._update_settings_summary()

    def _on_settings_saved(self, cfg: dict):
        # 保存された設定を反映
        self.config = dict(cfg)
        self.format_label.setText(f"記録方式: {self.config.get('log_format','parquet')}")
        self.sessions_panel.set_directory(self.config.get("save_dir", "logs"))
        self._update_settings_summary()

    def _update_settings_summary(self):
        # 設定タブは詳細編集UIだが、簡易サマリは保持（ステータス更新用）
        cfg = self.config
        summary = (
            f"記録方式: {cfg.get('log_format','parquet')}\n"
            f"保存先: {cfg.get('save_dir','logs')}\n"
            f"ファイル名テンプレート: {cfg.get('filename_template','%Y%m%d_%H%M%S')}\n"
            f"サンプリング間隔: {cfg.get('sample_interval',0.02)} 秒"
        )
        # ステータスバー右側に表示
        self.status_info.setText(f"{cfg.get('log_format','parquet')} | {cfg.get('save_dir','logs')}")
    
    def _on_sidebar_collapsed(self, collapsed: bool):
        self.config["sidebar_collapsed"] = bool(collapsed)
        save_config(self.config)
    
    def _default_filename(self):
        template = self.config.get("filename_template", "%Y%m%d_%H%M%S")
        ext = ".parquet" if self.config.get("log_format", "parquet") == "parquet" else ".csv"
        return datetime.datetime.now().strftime(template) + ext
    
    def start_logging(self):
        selected_format = self.config.get("log_format", "parquet")
        ext = ".parquet" if selected_format == "parquet" else ".csv"
        filename = self.filename_edit.text().strip()
        if not filename:
            filename = self._default_filename()
        else:
            if not filename.lower().endswith(ext):
                filename += ext
        save_dir = self.config.get("save_dir", "logs")
        try:
            os.makedirs(save_dir, exist_ok=True)
        except Exception:
            pass
        filepath = os.path.join(save_dir, filename)
        interval = float(self.config.get("sample_interval", 0.02))
        self.worker = LoggerWorkerThread(filepath, interval=interval, format=selected_format)
        # 高頻度シグナルはバッファに保存し、UIはタイマーで更新
        self.worker.status.connect(self.on_worker_status)
        self.worker.update.connect(self.on_worker_update)
        self.worker.start()
        # UIタイマー開始（約30Hz）
        self.latest_status = "記録開始"
        self.ui_timer.start()
        self.action_start.setEnabled(False)
        self.action_stop.setEnabled(True)
        self.status_label.setText("記録開始")
        self.status_info.setText(os.path.basename(filepath))

    def stop_logging(self):
        # UIタイマー停止
        self.ui_timer.stop()
        if self.worker:
            self.worker.stop()
            self.worker.wait()
            self.worker = None
        self.action_start.setEnabled(True)
        self.action_stop.setEnabled(False)
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

    # トレイ
    def _start_from_tray(self):
        if self.action_start.isEnabled():
            self.start_logging()

    def _stop_from_tray(self):
        if self.action_stop.isEnabled():
            self.stop_logging()

    def _cleanup_resources(self):
        try:
            if hasattr(self, "ui_timer") and self.ui_timer.isActive():
                self.ui_timer.stop()
        except Exception:
            pass
        if getattr(self, "worker", None):
            try:
                self.worker.stop()
            except Exception:
                pass
            self.worker.wait()
            self.worker = None

    def _quit_app(self):
        self._force_quit = True
        self._cleanup_resources()
        QGuiApplication.instance().quit()

    # 閉じる操作はアプリを終了（トレイには格納しない）
    def closeEvent(self, event):
        self._cleanup_resources()
        super().closeEvent(event)

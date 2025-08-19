import sys
from PySide6.QtWidgets import QApplication, QStyleFactory
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt
from gui import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        app.setStyle(QStyleFactory.create("Fusion"))
    except Exception:
        pass
    dark = QPalette()
    dark.setColor(QPalette.Window, QColor(18, 18, 18))
    dark.setColor(QPalette.WindowText, QColor(236, 239, 241))
    dark.setColor(QPalette.Base, QColor(30, 30, 30))
    dark.setColor(QPalette.AlternateBase, QColor(24, 24, 24))
    dark.setColor(QPalette.ToolTipBase, QColor(236, 239, 241))
    dark.setColor(QPalette.ToolTipText, QColor(33, 33, 33))
    dark.setColor(QPalette.Text, QColor(236, 239, 241))
    dark.setColor(QPalette.Button, QColor(30, 30, 30))
    dark.setColor(QPalette.ButtonText, QColor(236, 239, 241))
    dark.setColor(QPalette.BrightText, QColor(255, 0, 0))
    dark.setColor(QPalette.Highlight, QColor(94, 156, 255))
    dark.setColor(QPalette.HighlightedText, QColor(0, 0, 0))
    app.setPalette(dark)

    window = MainWindow()
    window.resize(1200, 800)
    window.show()
    sys.exit(app.exec())

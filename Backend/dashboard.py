from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import pyqtSignal, QObject, pyqtSlot, QUrl, QTimer
from PyQt5.QtWebChannel import QWebChannel
import os
import json
from .system import SystemMonitor

class Bridge(QObject):
    updateSystemStats = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot()
    def startBot(self):
        self.parent().start_bot()

    @pyqtSlot()
    def stopBot(self):
        self.parent().stop_bot()

    def emitSystemStats(self, stats):
        self.updateSystemStats.emit(json.dumps(stats))

class DashboardScreen(QWidget):
    start_bot_signal = pyqtSignal()
    stop_bot_signal = pyqtSignal()

    def __init__(self, console_callback=None):
        super().__init__()
        self.console_callback = console_callback
        self.system_monitor = SystemMonitor()
        self.initUi()

    def initUi(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.view = QWebEngineView()
        self.channel = QWebChannel()
        self.bridge = Bridge(self)
        self.channel.registerObject("pybridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(current_dir, '..', 'Frontend', 'dashboard.html')
        with open(html_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        base_url = QUrl.fromLocalFile(os.path.dirname(html_path) + '/')
        self.view.setHtml(html_content, base_url) 
        layout.addWidget(self.view)
        self.setGeometry(100, 100, 800, 600)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_system_stats)
        self.timer.start(10000)

    def log_to_console(self, log_type, message):
        if self.console_callback:
            self.console_callback(log_type, message)
        else:
            print(f"[{log_type}] {message}")

    @pyqtSlot()
    def start_bot(self):
        self.log_to_console("INFO", "MassDM Bot Started")
        self.start_bot_signal.emit()

    @pyqtSlot()
    def stop_bot(self):
        self.log_to_console("INFO", "MassDM Bot Stopped")
        self.stop_bot_signal.emit()

    def update_system_stats(self):
        try:
            stats = self.system_monitor.get_all_metrics()
            self.system_monitor.save_to_json(stats)
            self.bridge.emitSystemStats(stats)
        except Exception as e:
            self.log_to_console("ERROR", f"Failed to update system stats: {str(e)}")
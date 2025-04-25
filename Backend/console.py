import sys
from datetime import datetime
from collections import deque
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                            QScrollArea, QFrame)
from PyQt5.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QColor, QPalette
import asyncio 

class LogEntry(QWidget):
    animation_finished = pyqtSignal()
    
    def __init__(self, timestamp, log_type, message, parent=None):
        super().__init__(parent)
        self.setup_ui(timestamp, log_type, message)
        
    def setup_ui(self, timestamp, log_type, message):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(0)
        colors = {
            'INFO': '#60A5FA',
            'SUCCESS': '#34D399',
            'WARNING': '#FBBF24',
            'ERROR': '#EF4444',
            'DEBUG': '#A78BFA',
            'SKIP': '#D1D5DB',
            'RATELIMIT': '#F87171'
        }
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(5)
        timestamp_label = QLabel(timestamp.strftime('%Y-%m-%d %H:%M:%S'))
        timestamp_label.setFixedWidth(200)
        timestamp_label.setStyleSheet('color: #666666; font-family: Consolas; font-size: 14px;')
        timestamp_label.setFont(QFont("Consolas", 14))
        container_layout.addWidget(timestamp_label)
        type_label = QLabel(f"[{log_type}]")
        type_label.setFixedWidth(90)
        type_label.setStyleSheet(f'color: {colors[log_type]}; font-family: Consolas; font-size: 14px;')
        type_label.setFont(QFont("Consolas", 14))
        container_layout.addWidget(type_label)
        msg_label = QLabel(message)
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet('color: #E2E8F0; font-family: Consolas; font-size: 14px;')
        msg_label.setFont(QFont("Consolas", 14))
        container_layout.addWidget(msg_label, 1)
        layout.addWidget(container)
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(800)
        self.anim.setStartValue(QPoint(-self.width(), 0))
        self.anim.setEndValue(QPoint(0, 0))
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.anim.finished.connect(self.animation_finished)

class ConsoleWindow(QMainWindow):
    otp_requested = pyqtSignal(str)
    otp_entered = pyqtSignal(str, str)
    
    def __init__(self):
        super().__init__()
        self.log_queue = deque()
        self.is_processing = False
        self.setup_ui()
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self.process_log_queue)
        self.process_timer.start(300)
        
    def setup_ui(self):
        self.setWindowTitle("Console Logger")
        self.resize(1100, 650)
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        container = QFrame()
        container.setObjectName("logContainer")
        container.setStyleSheet("""
            #logContainer {
                background-color: #121212;
                border-radius: 15px;
            }
        """)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                border: none;
                background: #3A3A3A;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #4A4A4A;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #5A5A5A;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                border: none;
                background: none;
            }
        """)
        self.log_container = QWidget()
        self.log_container.setStyleSheet("background: transparent;")
        self.log_layout = QVBoxLayout(self.log_container)
        self.log_layout.setSpacing(2)
        self.log_layout.setContentsMargins(0, 12, 0, 12)
        self.log_layout.addStretch()
        scroll.setWidget(self.log_container)
        container_layout = QVBoxLayout(container)
        container_layout.addWidget(scroll)
        main_layout.addWidget(container)
        self.console = Console(self.queue_log)
        
    def queue_log(self, log_type, message):
        self.log_queue.append((log_type, message))
        
    def process_log_queue(self):
        if self.is_processing or not self.log_queue:
            return
        self.is_processing = True
        log_type, message = self.log_queue.popleft()
        current_time = datetime.now()
        log_entry = LogEntry(current_time, log_type, message)
        self.log_layout.insertWidget(0, log_entry)
        log_entry.animation_finished.connect(self.on_animation_finished)
        log_entry.anim.start()
        self.cleanup_old_logs()
        
    def on_animation_finished(self):
        self.is_processing = False
        
    def cleanup_old_logs(self):
        while self.log_layout.count() > 101:
            item = self.log_layout.itemAt(self.log_layout.count() - 2)
            if item and item.widget():
                item.widget().deleteLater()

    def handle_otp_request(self, account_name):
        from .otp import OTPDialog
        dialog = OTPDialog(account_name)
        dialog.otp_submitted.connect(self._handle_otp_submitted)
        dialog.show()

    def _handle_otp_submitted(self, otp, account_name):
        self.console.log("INFO", f"OTP entered for {account_name}")
        asyncio.create_task(self._process_otp(otp, account_name))

    async def _process_otp(self, otp, account_name):
        try:
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'handle_otp_entered'):
                main_window = main_window.parent()
                
            if main_window and hasattr(main_window, 'handle_otp_entered'):
                await main_window.handle_otp_entered(account_name, otp)
            else:
                self.console.log("ERROR", "Could not find main window to handle OTP")
        except Exception as e:
            self.console.log("ERROR", f"Error processing OTP: {str(e)}")

class Console:
    def __init__(self, append_callback):
        self.append_callback = append_callback
    
    def log(self, log_type, message):
        self.append_callback(log_type, message)
    
    def error(self, message):
        self.log("ERROR", message)
    
    def success(self, message):
        self.log("SUCCESS", message)
    
    def debug(self, message):
        self.log("DEBUG", message)
    
    def warning(self, message):
        self.log("WARNING", message)

def create_console_window():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(25, 25, 25))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)
    window = ConsoleWindow()
    window.setStyleSheet("QMainWindow { background-color: #1A1A1A; }")
    return window, app
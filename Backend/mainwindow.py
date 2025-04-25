from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                           QPushButton, QHBoxLayout, QStackedWidget, QProgressBar)
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtCore import QSize, pyqtSlot
from qasync import asyncSlot
import asyncio
from .dashboard import DashboardScreen
from .console import ConsoleWindow
from .account import AccountManagementScreen
from .support import HelpSupportScreen
from .config import MainConfigurationScreen
from .massdm import TelegramMassDM
from .session import SessionManager
from .aio import TelegramAio
from .tos import TermsOfService
from .docs import HowToUseScreen

class IconButton(QPushButton):
    def __init__(self, icon_path, text):
        super().__init__(QIcon(icon_path), text)
        self.setFont(QFont("Arial", 12))
        self.setStyleSheet("""
            QPushButton {
                background-color: #1A1A1A;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px;
                text-align: left;
                margin: 5px 0px;
            }
            QPushButton:hover {
                background-color: #2A2A2A;
            }
            QPushButton:checked {
                background-color: #2A2A2A;
                border-left: 4px solid #00AA00;
            }
        """)
        self.setCheckable(True)
        self.setIconSize(QSize(24, 24))

class ModernTelegramGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.telegram_mass_dm = TelegramMassDM()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Telegram Mass DM Panel')
        self.setGeometry(100, 100, 1200, 800)
        self.setStyleSheet("background-color: #000000;")
        main_layout = QVBoxLayout()
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)
        sidebar = self.create_sidebar()
        content_layout.addWidget(sidebar)
        self.stacked_widget = QStackedWidget()
        content_layout.addWidget(self.stacked_widget)
        self.console_window = ConsoleWindow()
        self.dashboard = DashboardScreen(console_callback=self.log_to_console)
        self.config_screen = MainConfigurationScreen(console_window=self.console_window)
        self.account_screen = AccountManagementScreen(console_window=self.console_window)
        self.help_screen = HelpSupportScreen()
        self.session_manager = SessionManager()
        self.aio_screen = TelegramAio()
        self.tos_screen = TermsOfService()
        self.docs_screen = HowToUseScreen()
        self.stacked_widget.addWidget(self.dashboard)
        self.stacked_widget.addWidget(self.config_screen)
        self.stacked_widget.addWidget(self.account_screen)
        self.stacked_widget.addWidget(self.console_window)
        self.stacked_widget.addWidget(self.help_screen)
        self.stacked_widget.addWidget(self.session_manager)
        self.stacked_widget.addWidget(self.aio_screen)
        self.stacked_widget.addWidget(self.tos_screen)
        self.stacked_widget.addWidget(self.docs_screen)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #2A2A2A;
                border-radius: 5px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background-color: #00AA00;
            }
        """)
        main_layout.addWidget(self.progress_bar)
        self.telegram_mass_dm.set_console_callback(self.log_to_console)
        self.telegram_mass_dm.scraping_progress_signal.connect(self.update_progress)
        self.dashboard.start_bot_signal.connect(self.start_mass_dm)
        self.dashboard.stop_bot_signal.connect(self.stop_mass_dm)

    def create_sidebar(self):
        sidebar = QWidget()
        sidebar.setStyleSheet("""
            background-color: transparent;
            margin: 10px;
            max-width: 250px;
        """)
        sidebar_layout = QVBoxLayout()
        options = [
            ('Icons/dashboard.svg', 'Dashboard'),
            ('Icons/config.svg', 'Config Management'),
            ('Icons/account.svg', 'Account Management'),
            ('Icons/session.svg', 'Session Management'),
            ('Icons/telegram.svg', 'Telegram Aio'),
            ('Icons/terminal.svg', 'Console Logging'),
            ('Icons/help.svg', 'Help and Support'),
            ('Icons/tos.svg', 'Terms of Service'),
            ('Icons/docs.svg', 'How to Use')
        ]
        self.option_buttons = []
        for icon_path, text in options:
            button = IconButton(icon_path, text)
            button.clicked.connect(self.on_sidebar_button_clicked)
            sidebar_layout.addWidget(button)
            self.option_buttons.append(button)
        self.option_buttons[0].setChecked(True)
        sidebar_layout.addStretch()
        sidebar.setLayout(sidebar_layout)
        return sidebar

    def on_sidebar_button_clicked(self):
        sender = self.sender()
        for button in self.option_buttons:
            button.setChecked(button == sender)
        screens = {
            "Dashboard": self.dashboard,
            "Config Management": self.config_screen,
            "Account Management": self.account_screen,
            "Session Management": self.session_manager,
            "Telegram Aio": self.aio_screen,
            "Console Logging": self.console_window,
            "Help and Support": self.help_screen,
            "Terms of Service": self.tos_screen,
            "How to Use": self.docs_screen
        }
        if screen := screens.get(sender.text()):
            self.stacked_widget.setCurrentWidget(screen)

    def log_to_console(self, log_type, message):
        self.console_window.queue_log(log_type, message)
    
    @pyqtSlot(int, int)
    def update_progress(self, current, total):
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(current)
            self.progress_bar.setVisible(True)
        else:
            self.progress_bar.setMaximum(0)
            self.progress_bar.setVisible(True)

    @asyncSlot()
    async def start_mass_dm(self):
        if self.telegram_mass_dm.is_running:
            self.log_to_console("WARNING", "Process is already running")
            return
        self.log_to_console("INFO", "Starting MassDM Bot...")
        self.progress_bar.setVisible(True)
        await self.telegram_mass_dm.run()
        self.progress_bar.setVisible(False)

    @asyncSlot()
    async def stop_mass_dm(self):
        if not self.telegram_mass_dm.is_running:
            self.log_to_console("WARNING", "No process is currently running")
            return
        self.log_to_console("INFO", "Stopping Mass DM process...")
        await self.telegram_mass_dm.stop()
        self.progress_bar.setVisible(False)

    def closeEvent(self, event):
        if self.telegram_mass_dm.is_running:
            asyncio.get_event_loop().create_task(self.telegram_mass_dm.stop())
        event.accept()
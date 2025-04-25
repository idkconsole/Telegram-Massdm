from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt5.QtCore import Qt, pyqtSignal

class ScrapedMembersDialog(QDialog):
    result_signal = pyqtSignal(bool)
    
    def __init__(self, member_count):
        super().__init__()
        self.setWindowTitle("Scraped Members")
        self.setModal(True)
        self.resize(400, 150)
        layout = QVBoxLayout()
        message = QLabel(f"{member_count} members have been scraped. Do you want to start sending DMs?")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)
        layout.addWidget(message)
        button_layout = QHBoxLayout()
        yes_button = QPushButton("Yes")
        no_button = QPushButton("No")
        yes_button.clicked.connect(self.on_yes_clicked)
        no_button.clicked.connect(self.on_no_clicked)
        button_layout.addWidget(yes_button)
        button_layout.addWidget(no_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def on_yes_clicked(self):
        self.result_signal.emit(True)
        self.accept()
    
    def on_no_clicked(self):
        self.result_signal.emit(False)
        self.reject()

class ExistingMembersDialog(QDialog):
    result_signal = pyqtSignal(bool)
    
    def __init__(self, member_count):
        super().__init__()
        self.setWindowTitle("Existing Members Found")
        self.setModal(True)
        self.resize(400, 150)
        layout = QVBoxLayout()
        message = QLabel(f"{member_count} members found in scraped.json. Do you want to send DMs to them?")
        message.setWordWrap(True)
        message.setAlignment(Qt.AlignCenter)
        layout.addWidget(message)
        button_layout = QHBoxLayout()
        yes_button = QPushButton("Yes")
        no_button = QPushButton("No")
        yes_button.clicked.connect(self.on_yes_clicked)
        no_button.clicked.connect(self.on_no_clicked)
        button_layout.addWidget(yes_button)
        button_layout.addWidget(no_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def on_yes_clicked(self):
        self.result_signal.emit(True)
        self.accept()
    
    def on_no_clicked(self):
        self.result_signal.emit(False)
        self.reject()
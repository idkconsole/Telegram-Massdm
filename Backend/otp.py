from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLineEdit, QPushButton, QLabel)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QRegExpValidator
import pyperclip
from PyQt5.QtCore import QRegExp

class OTPDialog(QMainWindow):
    otp_submitted = pyqtSignal(str, str)
    
    def __init__(self, account_name): 
        super().__init__()
        self.account_name = account_name
        self.setWindowTitle(f"OTP Verification - {account_name}")
        self.setFixedSize(450, 300)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2A2A2A;
            }
            QLineEdit {
                padding: 10px;
                border: 2px solid #4A4A4A;
                border-radius: 8px;
                font-size: 18px;
                background-color: #3A3A3A;
                color: white;
            }
            QLineEdit:focus {
                border-color: #5A5A5A;
            }
            QPushButton {
                padding: 12px 20px;
                background-color: #4A4A4A;
                color: white;
                border: none;
                border-radius: 25px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #5A5A5A;
            }
            QLabel {
                font-size: 14px;
                color: white;
            }
        """)
        title = QLabel(f"Enter OTP for {account_name}")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 18))
        layout.addWidget(title)
        otp_container = QWidget()
        otp_layout = QHBoxLayout(otp_container)
        otp_layout.setSpacing(10)
        self.otp_inputs = []
        for i in range(5):
            otp_field = QLineEdit()
            otp_field.setFixedSize(50, 50)
            otp_field.setAlignment(Qt.AlignCenter)
            otp_field.setMaxLength(1)
            validator = QRegExpValidator(QRegExp("[0-9]"))
            otp_field.setValidator(validator)
            otp_field.textChanged.connect(lambda text, index=i: self.on_text_changed(text, index))
            self.otp_inputs.append(otp_field)
            otp_layout.addWidget(otp_field)
        layout.addWidget(otp_container)
        buttons_container = QWidget()
        buttons_layout = QHBoxLayout(buttons_container)
        buttons_layout.setSpacing(10)
        paste_btn = QPushButton("Paste OTP")
        paste_btn.clicked.connect(self.paste_otp)
        buttons_layout.addWidget(paste_btn)
        submit_btn = QPushButton("Submit OTP")
        submit_btn.clicked.connect(self.submit_otp)
        buttons_layout.addWidget(submit_btn)
        layout.addWidget(buttons_container)
        self.message_label = QLabel()
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)
        
    def on_text_changed(self, text, current_index):
        if text and current_index < len(self.otp_inputs) - 1:
            self.otp_inputs[current_index + 1].setFocus()
        elif not text and current_index > 0:
            self.otp_inputs[current_index - 1].setFocus()
    
    def paste_otp(self):
        try:
            clipboard_text = pyperclip.paste()
            otp = ''.join(filter(str.isdigit, clipboard_text))[:5]
            for i, digit in enumerate(otp):
                if i < len(self.otp_inputs):
                    self.otp_inputs[i].setText(digit)
        except Exception as e:
            self.show_message("Failed to paste OTP", error=True)

    def submit_otp(self):
        otp = ''.join(input_field.text() for input_field in self.otp_inputs)
        if len(otp) == 5:
            self.otp_submitted.emit(otp, self.account_name)
            self.show_message("OTP Submitted Successfully!", error=False)
            self.close()
        else:
            self.show_message("Please enter a valid OTP", error=True)

    def show_message(self, message, error=False):
        self.message_label.setText(message)
        self.message_label.setStyleSheet(f"color: {'red' if error else 'green'};")
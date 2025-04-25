from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView

class TermsOfService(QWidget):
    def __init__(self):
        super().__init__()
        self.initUi()

    def initUi(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.view = QWebEngineView()
        with open("Frontend/tos.html", "r") as file:
            html_content = file.read()
        self.view.setHtml(html_content)
        layout.addWidget(self.view)
        self.setGeometry(100, 100, 800, 600)
        self.show()
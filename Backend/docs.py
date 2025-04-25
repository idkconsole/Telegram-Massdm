import sys
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtCore import QUrl

class WebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        pass

class HowToUseScreen(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram AdBot Documentation")
        self.setGeometry(100, 100, 1024, 768)
        self.web_view = QWebEngineView()
        self.web_view.setPage(WebEnginePage(self.web_view.page().profile(), self.web_view))
        self.setCentralWidget(self.web_view)
        with open('Frontend/docs.html', 'r', encoding='utf-8') as file:
            html_content = file.read()
        html_content += """
        <style>
        body {
            overflow: hidden;
        }
        </style>
        """
        self.web_view.setHtml(html_content, QUrl("file://"))
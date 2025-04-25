from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot
import webbrowser

class JSBridge(QObject):
    @pyqtSlot(str)
    def openExternalLink(self, url):
        webbrowser.open(url)

class CustomWebPage(QWebEnginePage):
    def __init__(self, parent=None):
        super().__init__(parent)

    def acceptNavigationRequest(self, url, _type, isMainFrame):
        if _type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
            webbrowser.open(url.toString())
            return False
        return super().acceptNavigationRequest(url, _type, isMainFrame)
    
class HelpSupportScreen(QWidget):
    def __init__(self):
        super().__init__()
        self.initUi()

    def initUi(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.view = QWebEngineView()
        self.bridge = JSBridge()
        self.channel = QWebChannel()
        self.channel.registerObject('bridge', self.bridge)
        self.page = CustomWebPage(self.view)
        self.page.setWebChannel(self.channel)
        self.view.setPage(self.page)
        with open('Frontend/support.html', 'r', encoding='utf-8') as file:
            html_content = file.read()
        html_content += """
        <style>
        body {
            overflow: hidden;
        }
        </style>
        """
        self.view.setHtml(html_content)
        layout.addWidget(self.view)
        self.setGeometry(100, 100, 800, 600)
        self.setWindowTitle('Help & Support')
        self.show()
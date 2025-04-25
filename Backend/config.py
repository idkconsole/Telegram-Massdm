import os
import json
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot, QUrl
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView

class Bridge(QObject):
    def __init__(self, console_window):
        super().__init__()
        self.config_file = 'ConfigData/config.json'
        self.console_window = console_window
        self.initialize_config()

    def initialize_config(self):
        os.makedirs('ConfigData', exist_ok=True)
        if not os.path.exists(self.config_file):
            self.save_config(self.get_default_config())
        else:
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                if not data:
                    self.save_config(self.get_default_config())
            except:
                self.save_config(self.get_default_config())

    def save_config(self, data):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=4)

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return self.get_default_config()

    def get_default_config(self):
        return {
            "api_id": "",
            "api_hash": "",
            "phone_number": "",
            "password": "",
            "group_url": "",
            "message_url": "",
            "messages_per_session": 0,
            "delay_between_messages": 0,
            "send_image": False,
            "discord_logging": False,
            "discord_webhook_url": ""
        }

    @pyqtSlot(str, result=str)
    def saveChanges(self, data):
        try:
            config_data = json.loads(data)
            self.save_config(config_data)
            self.console_window.console.log("SUCCESS", "Changes saved successfully")
            return json.dumps({"success": True, "message": "Changes saved successfully"})
        except Exception as e:
            self.console_window.console.log("ERROR", f"Error saving changes: {str(e)}")
            return json.dumps({"success": False, "message": f"Error saving changes: {str(e)}"})

    @pyqtSlot(result=str)
    def resetChanges(self):
        try:
            self.save_config(self.get_default_config())
            self.console_window.console.log("SUCCESS", "Configuration reset successfully")
            return json.dumps({"success": True, "message": "Configuration reset successfully"})
        except Exception as e:
            self.console_window.console.log("ERROR", f"Error resetting configuration: {str(e)}")
            return json.dumps({"success": False, "message": f"Error resetting configuration: {str(e)}"})

    @pyqtSlot(result=str)
    def loadData(self):
        try:
            config_data = self.load_config()
            return json.dumps(config_data)
        except Exception as e:
            self.console_window.console.log("ERROR", f"Error loading configuration: {str(e)}")
            return json.dumps(self.get_default_config())

class MainConfigurationScreen(QWidget):
    def __init__(self, console_window):
        super().__init__()
        self.console_window = console_window
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.view = QWebEngineView()
        self.channel = QWebChannel()
        self.bridge = Bridge(self.console_window)
        self.channel.registerObject('bridge', self.bridge)
        self.view.page().setWebChannel(self.channel)
        with open('Frontend/config.html', 'r', encoding='utf-8') as file:
            html_content = file.read()
        self.view.setHtml(html_content, QUrl("file://"))
        layout.addWidget(self.view)
        self.setGeometry(100, 100, 800, 600)
        self.show()
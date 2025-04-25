import os
import json
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot, QUrl
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtWebEngineWidgets import QWebEngineView

class Bridge(QObject):
    def __init__(self, console_window):
        super().__init__()
        self.config_file = 'DataBase/Accounts.json'
        self.max_accounts = 999
        self.console_window = console_window
        self.initialize_config()

    def initialize_config(self):
        os.makedirs('DataBase', exist_ok=True)
        if not os.path.exists(self.config_file):
            self.save_config({"Accounts Database": {"Account 1": self.get_default_account_data()}})
        else:
            try:
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                if not data or not data.get("Accounts Database"):
                    self.save_config({"Accounts Database": {"Account 1": self.get_default_account_data()}})
            except:
                self.save_config({"Accounts Database": {"Account 1": self.get_default_account_data()}})

    def save_config(self, data):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=4)

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return [self.get_default_account_data("Account 1")]

    def get_default_account_data(self):
        return {
            "api_id": "",
            "api_hash": "",
            "phone_number": "",
            "password": "",
        }

    @pyqtSlot(str, result=str)
    def saveChanges(self, data):
        try:
            accounts_data = json.loads(data)
            formatted_data = {"Accounts Database": {}}
            for account in accounts_data:
                account_data = dict(account)
                account_name = account_data.pop('name')
                formatted_account = {
                    "api_id": account_data.get('api_id', ''),
                    "api_hash": account_data.get('api_hash', ''),
                    "phone_number": account_data.get('phone_number', ''),
                    "password": account_data.get('password', ''),
                }   
                formatted_data["Accounts Database"][account_name] = formatted_account
            self.save_config(formatted_data)
            self.console_window.console.log("SUCCESS", "Changes saved successfully")
            return json.dumps({"success": True, "message": "Changes saved successfully"})
        except Exception as e:
            self.console_window.console.log("ERROR", f"Error saving changes: {str(e)}")
            return json.dumps({"success": False, "message": f"Error saving changes: {str(e)}"})

    @pyqtSlot(result=str)
    def addAccount(self):
        try:
            config_data = self.load_config()
            accounts = config_data["Accounts Database"]
            if len(accounts) >= self.max_accounts:
                self.console_window.console.log("ERROR", "Maximum number of accounts reached")
                return json.dumps({"success": False, "message": "Maximum number of accounts reached"})
            new_account_number = len(accounts) + 1
            new_account_name = f"Account {new_account_number}"
            accounts[new_account_name] = self.get_default_account_data()
            self.save_config(config_data)
            self.console_window.console.log("SUCCESS", f"Account {new_account_name} added successfully")
            return json.dumps({"success": True, "message": f"Account {new_account_name} added successfully"})
        except Exception as e:
            self.console_window.console.log("ERROR", f"Error adding account: {str(e)}")
            return json.dumps({"success": False, "message": f"Error adding account: {str(e)}"})

    @pyqtSlot(str, result=str)
    def deleteAccount(self, account_name):
        try:
            if account_name == "Account 1":
                self.console_window.console.log("ERROR", "Cannot delete Account 1")
                return json.dumps({"success": False, "message": "Cannot delete Account 1"})
            config_data = self.load_config()
            if account_name in config_data["Accounts Database"]:
                del config_data["Accounts Database"][account_name]
                self.save_config(config_data)
                self.console_window.console.log("SUCCESS", f"Account {account_name} deleted successfully")
            return json.dumps({"success": True, "message": f"Account {account_name} deleted successfully"})
        except Exception as e:
            self.console_window.console.log("ERROR", f"Error deleting account: {str(e)}")
            return json.dumps({"success": False, "message": f"Error deleting account: {str(e)}"})

    @pyqtSlot(str, result=str)
    def resetChanges(self, account_name):
        try:
            config_data = self.load_config()
            if account_name in config_data["Accounts Database"]:
                config_data["Accounts Database"][account_name] = self.get_default_account_data()
                self.save_config(config_data)
                self.console_window.console.log("SUCCESS", f"Account {account_name} reset successfully")
            return json.dumps({"success": True, "message": "Account reset successfully"})
        except Exception as e:
            self.console_window.console.log("ERROR", f"Error resetting account: {str(e)}")
            return json.dumps({"success": False, "message": f"Error resetting account: {str(e)}"})

    @pyqtSlot(result=str)
    def loadData(self):
        try:
            config_data = self.load_config()
            accounts = []
            for account_name, account_data in config_data["Accounts Database"].items():
                accounts.append({"name": account_name, **account_data})
            return json.dumps({"accounts": accounts})
        except Exception as e:
            return json.dumps({"accounts": [{"name": "Account 1", **self.get_default_account_data()}]})

class AccountManagementScreen(QWidget):
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
        with open('Frontend/account.html', 'r', encoding='utf-8') as file:
            html_content = file.read()
        self.view.setHtml(html_content, QUrl("file://"))
        layout.addWidget(self.view)
        self.setGeometry(100, 100, 800, 600)
        self.show()
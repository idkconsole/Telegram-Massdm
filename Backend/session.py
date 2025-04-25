import os
import json
import base64
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QObject, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel

class SessionFileHandler:
    def __init__(self):
        self.base_path = os.path.join(os.getcwd(), "SessionData")
        self.ensure_directory()

    def ensure_directory(self):
        os.makedirs(self.base_path, exist_ok=True)

    def save_session(self, file_data: dict) -> bool:
        try:
            file_name = file_data.get('name')
            file_content = file_data.get('content')
            if not file_name or not file_content:
                print("Missing file name or content")
                return False
            dest_path = os.path.join(self.base_path, file_name)
            try:
                file_content = base64.b64decode(file_content.split(',')[1])
                with open(dest_path, 'wb') as f:
                    f.write(file_content)
                return True
            except Exception as e:
                print(f"Error writing file: {e}")
                return False
        except Exception as e:
            print(f"Error saving session: {e}")
            return False

    def load_sessions(self) -> list:
        sessions = []
        try:
            for file_name in os.listdir(self.base_path):
                if file_name.endswith('.session'):
                    file_path = os.path.join(self.base_path, file_name)
                    sessions.append({
                        'name': file_name,
                        'size': os.path.getsize(file_path),
                        'lastModified': os.path.getmtime(file_path) * 1000,
                        'path': file_path
                    })
        except Exception as e:
            print(f"Error loading sessions: {e}")
        return sessions

    def delete_session(self, file_name: str) -> bool:
        try:
            file_path = os.path.join(self.base_path, file_name)
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
        except Exception as e:
            print(f"Error deleting session: {e}")
        return False

class Bridge(QObject):
    def __init__(self):
        super().__init__()
        self.file_handler = SessionFileHandler()

    @pyqtSlot(str, result=bool)
    def save_changes(self, files_data):
        try:
            data = json.loads(files_data)
            success = True
            for file_data in data:
                if not self.file_handler.save_session(file_data):
                    success = False
            return success
        except Exception as e:
            print(f"Error saving changes: {e}")
            return False

    @pyqtSlot(str, result=bool)
    def delete_file(self, file_name):
        return self.file_handler.delete_session(file_name)

    @pyqtSlot(result=str)
    def load_sessions(self):
        sessions = self.file_handler.load_sessions()
        return json.dumps(sessions)

class SessionManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.web_view = QWebEngineView(self)
        self.setCentralWidget(self.web_view)
        self.channel = QWebChannel()
        self.bridge = Bridge()
        self.channel.registerObject('bridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        html_path = os.path.join('Frontend', 'session.html')
        self.web_view.setUrl(QUrl.fromLocalFile(os.path.abspath(html_path)))
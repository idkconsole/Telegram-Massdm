import os
import json
import base64
import time
import sys
import asyncio
import qasync
from typing import List, Dict
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QObject, pyqtSlot
from PyQt5.QtWebChannel import QWebChannel
from telethon import TelegramClient
from telethon.tl.functions.account import UpdateProfileRequest
from telethon.sessions import StringSession
from telethon.tl.functions.photos import UploadProfilePhotoRequest

class AccountManager:
    def __init__(self):
        self.PROJECT_ROOT = os.getcwd()
        self.config = self.load_config()
        self.active_clients = {}
        self.operation_stats = {'success': 0, 'fails': 0, 'start_time': 0}

    def load_config(self) -> Dict:
        try:
            config_path = os.path.join(self.PROJECT_ROOT, "ConfigData", "config.json")
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {"api_id": "", "api_hash": ""}

    def reset_stats(self):
        self.operation_stats = {'success': 0, 'fails': 0, 'start_time': time.time()}

    def get_operation_summary(self) -> Dict:
        time_taken = time.time() - self.operation_stats['start_time']
        return {
            'success': self.operation_stats['success'],
            'fails': self.operation_stats['fails'],
            'time_taken': f"{time_taken:.2f} seconds"
        }

    def get_session_files(self) -> List[Dict]:
        session_files = []
        session_dir = os.path.join(self.PROJECT_ROOT, "SessionData")
        try:
            for file_name in os.listdir(session_dir):
                if file_name.endswith('.session'):
                    file_path = os.path.join(session_dir, file_name)
                    session_files.append({
                        'id': len(session_files) + 1,
                        'name': file_name,
                        'path': file_path,
                        'size': os.path.getsize(file_path)
                    })
        except Exception as e:
            print(f"Error loading sessions: {e}")
        return session_files

    async def detect_session_type(self, session_file: str) -> str:
        try:
            session_path = os.path.join(self.PROJECT_ROOT, "SessionData", session_file)
            try:
                with open(session_path, 'r') as f:
                    content = f.read(100)
                    if content.startswith('1:') and '.' not in session_file:
                        return 'string'
            except UnicodeDecodeError:
                return 'sqlite'
            except Exception:
                return None
            return 'string' if len(content.strip()) > 50 else 'sqlite'
        except Exception as e:
            print(f"Error detecting session type: {e}")
            return None

    async def get_client(self, session_file: str) -> TelegramClient:
        try:
            if session_file in self.active_clients and self.active_clients[session_file].is_connected():
                return self.active_clients[session_file]
            session_path = os.path.join(self.PROJECT_ROOT, "SessionData", session_file)
            session_type = await self.detect_session_type(session_file)
            if session_type == 'string':
                try:
                    with open(session_path, 'r') as f:
                        session_string = f.read().strip()
                    client = TelegramClient(StringSession(session_string), 
                                         self.config["api_id"], 
                                         self.config["api_hash"])
                except Exception as e:
                    raise Exception(f"Failed to read string session: {str(e)}")
            elif session_type == 'sqlite':
                session_name = os.path.join(self.PROJECT_ROOT, "SessionData", os.path.splitext(session_file)[0])
                client = TelegramClient(session_name,
                                     self.config["api_id"],
                                     self.config["api_hash"])
            else:
                raise Exception(f"Unknown session type for {session_file}")
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                raise Exception(f"Session {session_file} is not authorized")
            self.active_clients[session_file] = client
            return client
        except Exception as e:
            if 'client' in locals():
                await client.disconnect()
            raise Exception(f"Failed to initialize client: {str(e)}")

    async def change_display_name(self, session_file: str, first_name: str, last_name: str = "") -> bool:
        try:
            client = await self.get_client(session_file)
            await client(UpdateProfileRequest(
                first_name=first_name,
                last_name=last_name
            ))
            self.operation_stats['success'] += 1
            return True
        except Exception as e:
            self.operation_stats['fails'] += 1
            raise Exception(f"Failed to change name: {str(e)}")

    async def change_profile_picture(self, session_file: str, image_data: str) -> bool:
        try:
            client = await self.get_client(session_file)
            try:
                images = json.loads(image_data)
                if isinstance(images, list) and images:
                    current_image = images[self.operation_stats['success'] % len(images)]
                    image_data_raw = current_image.split(',')[1]
                else:
                    raise ValueError("Invalid image array")
            except (json.JSONDecodeError, ValueError):
                image_data_raw = image_data.split(',')[1]
            image_format = None
            if 'data:image/jpeg' in image_data.split(',')[0]:
                image_format = 'jpeg'
            elif 'data:image/png' in image_data.split(',')[0]:
                image_format = 'png'
            else:
                raise Exception("Unsupported image format. Please use JPEG or PNG.")
            image_bytes = base64.b64decode(image_data_raw)
            if image_format == 'png':
                from io import BytesIO
                from PIL import Image
                img = Image.open(BytesIO(image_bytes))
                output = BytesIO()
                img = img.convert('RGB')
                img.save(output, format='JPEG')
                image_bytes = output.getvalue()
            file = await client.upload_file(image_bytes, file_name="photo.jpg")
            await client(UploadProfilePhotoRequest(file=file))
            self.operation_stats['success'] += 1
            return True
        except Exception as e:
            self.operation_stats['fails'] += 1
            raise Exception(f"Failed to change photo: {str(e)}")

    async def cleanup(self):
        for client in self.active_clients.values():
            try:
                await client.disconnect()
            except:
                pass
        self.active_clients.clear()

class Bridge(QObject):
    def __init__(self):
        super().__init__()
        self.account_manager = AccountManager()
        self.web_view = None
        self._tasks = set()

    def set_web_view(self, web_view):
        self.web_view = web_view

    def send_log(self, message, type='info'):
        if self.web_view:
            message = message.replace('"', '\\"').replace('\n', '\\n').replace('\r', '\\r')
            js_code = f'updateLog("{message}", "{type}");'
            self.web_view.page().runJavaScript(js_code)

    @pyqtSlot(result=str)
    def get_sessions(self):
        sessions = self.account_manager.get_session_files()
        return json.dumps(sessions)

    def _create_task(self, coro):
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    @pyqtSlot(str, str, str, result=bool)
    def change_name(self, session_files, first_name, last_name=""):
        try:
            sessions = json.loads(session_files)
            self.account_manager.reset_stats()
            async def process_sessions():
                try:
                    for session in sessions:
                        try:
                            session_type = await self.account_manager.detect_session_type(session)
                            self.send_log(f"Detected session type for {session}: {session_type}", "info")
                            success = await self.account_manager.change_display_name(session, first_name, last_name)
                            if success:
                                self.send_log(f"Changed display name for {session}", "success")
                            else:
                                self.send_log(f"Failed to change display name for {session}", "error")
                        except Exception as e:
                            self.send_log(f"Error with {session}: {str(e)}", "error")
                finally:
                    summary = self.account_manager.get_operation_summary()
                    summary_msg = f"Operation Complete - Success: {summary['success']}, Fails: {summary['fails']}, Time: {summary['time_taken']}"
                    self.send_log(summary_msg, "info")
            self._create_task(process_sessions())
            return True
        except Exception as e:
            self.send_log(f"Error in change_name: {str(e)}", "error")
            return False

    @pyqtSlot(str, str, result=bool)
    def change_photo(self, session_files, image_data):
        try:
            sessions = json.loads(session_files)
            self.account_manager.reset_stats()
            async def process_sessions():
                try:
                    try:
                        images = json.loads(image_data)
                        if isinstance(images, list):
                            self.send_log(f"Processing {len(images)} images in cycle mode", "info")
                    except json.JSONDecodeError:
                        self.send_log("Processing single image mode", "info")
                    for session in sessions:
                        try:
                            session_type = await self.account_manager.detect_session_type(session)
                            self.send_log(f"Detected session type for {session}: {session_type}", "info")
                            success = await self.account_manager.change_profile_picture(session, image_data)
                            if success:
                                self.send_log(f"Changed profile picture for {session}", "success")
                            else:
                                self.send_log(f"Failed to change profile picture for {session}", "error")
                        except Exception as e:
                            self.send_log(f"Error with {session}: {str(e)}", "error")
                finally:
                    summary = self.account_manager.get_operation_summary()
                    summary_msg = f"Operation Complete - Success: {summary['success']}, Fails: {summary['fails']}, Time: {summary['time_taken']}"
                    self.send_log(summary_msg, "info")
            self._create_task(process_sessions())
            return True
        except Exception as e:
            self.send_log(f"Error in change_photo: {str(e)}", "error")
            return False

    async def cleanup(self):
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self.account_manager.cleanup()

class TelegramAio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Telegram Account Manager")
        self.setGeometry(100, 100, 800, 600)
        self.init_ui()

    def init_ui(self):
        self.web_view = QWebEngineView(self)
        self.setCentralWidget(self.web_view)
        self.channel = QWebChannel()
        self.bridge = Bridge()
        self.bridge.set_web_view(self.web_view)
        self.channel.registerObject('bridge', self.bridge)
        self.web_view.page().setWebChannel(self.channel)
        with open('Frontend/aio.html', 'r', encoding='utf-8') as file:
            html_content = file.read()
        html_content += """
        <style>
        body {
            overflow: hidden;
        }
        </style>
        """
        self.web_view.setHtml(html_content, QUrl('http://localhost'))

    async def cleanup(self):
        await self.bridge.cleanup()

    def closeEvent(self, event):
        asyncio.create_task(self.cleanup())
        event.accept()
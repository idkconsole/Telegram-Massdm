from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QApplication
from PyQt5.QtCore import Qt, QObject, pyqtSignal, QEventLoop
from telethon import TelegramClient, events, errors
from telethon.tl.functions.channels import GetParticipantsRequest
from telethon.tl.types import ChannelParticipantsSearch, InputPeerChannel, InputPeerChat, Channel
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from telethon.sessions import StringSession
from aiohttp import ClientSession
from Backend.otp import OTPDialog
from .dialogs import ScrapedMembersDialog, ExistingMembersDialog
import os
import json
import asyncio
import sys
import aiohttp

class DiscordLogger(QObject):
    log_to_console_signal = pyqtSignal(str, str)
    
    def __init__(self, webhook_url):
        super().__init__()
        self.webhook_url = webhook_url
        
    async def log(self, message, level="INFO"):
        if not self.webhook_url:
            return
        payload = {"content": f"**[{level}]** {message}"}
        headers = {"Content-Type": "application/json"}
        try:
            async with ClientSession() as session:
                async with session.post(self.webhook_url, json=payload, headers=headers) as response:
                    if response.status == 204:
                        return
        except Exception:
            pass

class TelegramMassDM(QObject):
    otp_requested_signal = pyqtSignal(str)
    group_link_submitted = pyqtSignal(str)
    scraping_progress_signal = pyqtSignal(int, int)

    def __init__(self):
        super().__init__()
        self.PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config = None
        self.accounts = None
        self.members = []
        self.sent_to = set()
        self.otp_dialog = None
        self.discord_logger = None
        self.group_link = None
        self.is_running = False
        self.stop_requested = False
        self.console_callback = None
        self.update_dashboard_status = None
        self.config_client = None
        self.config_user_id = None
        self._create_directories()

    def _create_directories(self):
        directories = [
            "ConfigData", "DataBase", "ConfigSession", "SessionData",
            "AccountSession", "ScrapedData", "InvalidSession"
        ]
        for directory in directories:
            os.makedirs(os.path.join(self.PROJECT_ROOT, directory), exist_ok=True)

    def set_console_callback(self, callback):
        self.console_callback = callback

    def set_dashboard_status_callback(self, callback):
        self.update_dashboard_status = callback

    async def move_to_invalid_session(self, session_file, session_dir="SessionData"):
        try:
            src = os.path.join(self.PROJECT_ROOT, session_dir, session_file)
            dst = os.path.join(self.PROJECT_ROOT, "InvalidSession", session_file)
            import shutil
            shutil.move(src, dst)
            await self.log_to_console("INFO", f"Moved invalid session {session_file} to InvalidSession directory")
        except Exception as e:
            await self.log_to_console("ERROR", f"Failed to move invalid session {session_file}: {str(e)}")

    async def load_config(self):
        config_path = os.path.join(self.PROJECT_ROOT, "ConfigData", "config.json")
        try:
            if not os.path.exists(config_path):
                await self.log_to_console("ERROR", "config.json not found in ConfigData directory")
                return None 
            with open(config_path, 'r') as f:
                config = json.load(f)
            required_fields = ['api_id', 'api_hash', 'phone_number', 'message_url', 'messages_per_session', 
                             'delay_between_messages', 'group_url']
            empty_fields = [field for field in required_fields if not config.get(field)]
            if empty_fields:
                error_msg = f"The following required fields are empty in config.json: {', '.join(empty_fields)}"
                await self.log_to_console("ERROR", error_msg)
                return None
            return config
        except json.JSONDecodeError:
            await self.log_to_console("ERROR", "Invalid JSON format in config.json")
            return None
        except Exception as e:
            await self.log_to_console("ERROR", f"Failed to load configuration: {str(e)}")
            return None
        
    async def initialize_config(self):
        self.config = await self.load_config()
        if not self.config:
            await self.log_to_console("ERROR", "Failed to load configuration")
            return False
        self.accounts = await self.load_accounts()
        if not self.accounts:
            await self.log_to_console("ERROR", "Failed to load accounts")
            return False
        if self.config.get('discord_webhook_url'):
            self.discord_logger = DiscordLogger(self.config['discord_webhook_url'])
        return True
    
    async def initialize_config_client(self):
        try:
            config_session = self.load_config_session()
            self.config_client = TelegramClient(
                StringSession(config_session) if config_session else StringSession(),
                self.config['api_id'],
                self.config['api_hash']
            )
            await self.config_client.connect()
            if not await self.config_client.is_user_authorized():
                await self.log_to_console("INFO", "Config account needs authentication. Starting login process...")
                try:
                    phone_number = self.config['phone_number']
                    sent_code = await self.config_client.send_code_request(phone_number)
                    await self.log_to_console("INFO", f"OTP sent to {phone_number}")
                    self.otp_requested_signal.emit("config")
                    otp = await self.wait_for_otp("config")
                    try:
                        await self.config_client.sign_in(
                            phone=phone_number,
                            code=otp,
                            phone_code_hash=sent_code.phone_code_hash
                        )
                    except errors.SessionPasswordNeededError:
                        if 'password' in self.config and self.config['password']:
                            await self.config_client.sign_in(password=self.config['password'])
                        else:
                            await self.log_to_console("ERROR", "2FA required for config account but no password provided")
                            return False
                    except errors.PhoneCodeExpiredError:
                        await self.log_to_console("ERROR", "OTP code expired. Please try again.")
                        return False
                    except errors.PhoneCodeInvalidError:
                        await self.log_to_console("ERROR", "Invalid OTP provided. Please try again.")
                        return False
                    session_string = self.config_client.session.save()
                    self.save_config_session(session_string)
                    await self.log_to_console("SUCCESS", "Config account authenticated and session saved")
                except Exception as e:
                    await self.log_to_console("ERROR", f"Failed to authenticate config account: {str(e)}")
                    return False
            me = await self.config_client.get_me()
            self.config_user_id = me.id
            await self.log_to_console("SUCCESS", f"Config client initialized as {me.first_name} ({me.phone})")
            return True
        except Exception as e:
            await self.log_to_console("ERROR", f"Failed to initialize config client: {str(e)}")
            if self.config_client:
                await self.config_client.disconnect()
            return False
        
    async def load_accounts(self):
        accounts_path = os.path.join(self.PROJECT_ROOT, "DataBase", "accounts.json")
        try:
            if not os.path.exists(accounts_path):
                await self.log_to_console("ERROR", "accounts.json not found in DataBase directory")
                return None
            with open(accounts_path, 'r') as f:
                accounts = json.load(f)
            if 'Accounts Database' not in accounts:
                await self.log_to_console("ERROR", "Invalid accounts.json format: missing 'Accounts Database' key")
                return None
            return accounts['Accounts Database']
        except json.JSONDecodeError:
            await self.log_to_console("ERROR", "Invalid JSON format in accounts.json")
            return None
        except Exception as e:
            await self.log_to_console("ERROR", f"Failed to load accounts: {str(e)}")
            return None
        
    def save_session(self, account_name, session_string, session_type="AccountSession"):
        sessions_dir = os.path.join(self.PROJECT_ROOT, session_type)
        os.makedirs(sessions_dir, exist_ok=True)
        session_path = os.path.join(sessions_dir, f"{account_name}.session")
        try:
            with open(session_path, "w") as session_file:
                session_file.write(session_string)
            self.log_to_console("SUCCESS", f"Session saved for {account_name}")
        except Exception as e:
            self.log_to_console("ERROR", f"Failed to save session for {account_name}: {str(e)}")

    def load_session(self, account_name, session_type="SessionData"):
        session_path = os.path.join(self.PROJECT_ROOT, session_type, f"{account_name}.session")
        try:
            with open(session_path, "r") as session_file:
                return session_file.read().strip()
        except FileNotFoundError:
            return ""
        except Exception as e:
            self.log_to_console("ERROR", f"Failed to load session for {account_name}: {str(e)}")
            return ""

    def load_config_session(self):
        config_session_path = os.path.join(self.PROJECT_ROOT, "ConfigSession", "config.session")
        try:
            with open(config_session_path, "r") as session_file:
                return session_file.read().strip()
        except FileNotFoundError:
            return ""
        except Exception as e:
            self.log_to_console("ERROR", f"Failed to load config session: {str(e)}")
            return ""

    def save_config_session(self, session_string):
        config_session_dir = os.path.join(self.PROJECT_ROOT, "ConfigSession")
        os.makedirs(config_session_dir, exist_ok=True)
        config_session_path = os.path.join(config_session_dir, "config.session")
        try:
            with open(config_session_path, "w") as session_file:
                session_file.write(session_string)
        except Exception as e:
            self.log_to_console("ERROR", f"Failed to save config session: {str(e)}")

    async def connect(self, account_name, account_data):
        try:
            await self.log_to_console("INFO", f"{account_name}: Connecting to Telegram...")
            session_string = self.load_session(account_name) if account_name != "config" else self.load_config_session()
            if session_string:
                client = TelegramClient(StringSession(session_string), account_data['api_id'], account_data['api_hash'])
                await client.connect()
                if await client.is_user_authorized():
                    await self.log_to_console("SUCCESS", f"{account_name}: Successfully connected using existing session")
                    return client, True
                else:
                    await self.log_to_console("WARNING", f"{account_name}: Session exists but is not valid, starting fresh login")
                    await client.disconnect()
            client = TelegramClient(StringSession(), account_data['api_id'], account_data['api_hash'])
            await client.connect()
            await self.log_to_console("INFO", f"{account_name}: Starting fresh login process...")
            return client, False
        except ValueError as e:
            await self.log_to_console("ERROR", f"{account_name}: Invalid API ID or Hash: {str(e)}")
            raise
        except Exception as e:
            await self.log_to_console("ERROR", f"{account_name}: Failed to connect to Telegram: {str(e)}")
            raise

    async def authenticate(self, client, account_name, account_data):
        try:
            phone_number = account_data['phone_number'] if account_name != "config" else self.config['phone_number']
            password = account_data.get('password', '') if account_name != "config" else self.config.get('password', '')
            await client.send_code_request(phone_number)
            await self.log_to_console("INFO", f"OTP sent to {phone_number}")
            self.otp_requested_signal.emit(account_name)
            otp = await self.wait_for_otp(account_name)
            await client.sign_in(phone_number, otp)
            if account_name == "config":
                await self.log_to_console("SUCCESS", "Config account authenticated successfully")
                self.save_config_session(client.session.save())
            else:
                session_string = client.session.save()
                self.save_session(account_name, session_string)
                await self.log_to_console("SUCCESS", f"{account_name}: Authentication successful")
            return True
        except errors.SessionPasswordNeededError:
            return await self.handle_2fa(client, account_name, password)
        except errors.PhoneCodeInvalidError:
            return await self.handle_invalid_code(client, account_name, phone_number)
        except Exception as e:
            await self.log_to_console("ERROR", f"{account_name}: Authentication failed: {str(e)}")
            return False

    async def handle_2fa(self, client, account_name, password):
        try:
            await client.sign_in(password=password)
            if account_name == "config":
                await self.log_to_console("SUCCESS", "Config account authenticated successfully")
                self.save_config_session(client.session.save())
            else:
                session_string = client.session.save()
                self.save_session(account_name, session_string)
                await self.log_to_console("SUCCESS", f"{account_name}: 2FA authentication successful")
            return True
        except Exception as e:
            await self.log_to_console("ERROR", f"{account_name}: 2FA authentication failed: {str(e)}")
            return False

    async def handle_invalid_code(self, client, account_name, phone_number):
        await self.log_to_console("ERROR", f"{account_name}: Invalid OTP entered. Please try again.")
        self.otp_requested_signal.emit(account_name)
        otp = await self.wait_for_otp(account_name)
        try:
            await client.sign_in(phone_number, otp)
            if account_name == "config":
                await self.log_to_console("SUCCESS", "Config account authenticated successfully")
                self.save_config_session(client.session.save())
            else:
                session_string = client.session.save()
                self.save_session(account_name, session_string)
                await self.log_to_console("SUCCESS", f"{account_name}: Logged in successfully")
            return True
        except Exception as e:
            await self.log_to_console("ERROR", f"{account_name}: Authentication failed: {str(e)}")
            return False
        
    async def wait_for_otp(self, account_name):
        future = asyncio.Future()
        def handle_otp_submitted(otp, acc_name):
            if not future.done() and acc_name == account_name:
                future.set_result(otp)
        self.otp_dialog = OTPDialog(account_name=account_name)
        self.otp_dialog.otp_submitted.connect(handle_otp_submitted)
        self.otp_dialog.show()
        try:
            otp = await future
            return str(otp)
        except Exception as e:
            await self.log_to_console("ERROR", f"Error in OTP dialog: {str(e)}")
            return None

    async def create_new_sessions(self):
        for account_name, account_data in self.accounts.items():
            if not account_data.get('phone_number') or not account_data.get('api_id') or not account_data.get('api_hash'):
                await self.log_to_console("ERROR", f"Account {account_name} has missing credentials. Skipping.")
                continue
            try:
                client = TelegramClient(StringSession(), account_data['api_id'], account_data['api_hash'])
                await client.connect()
                if not await client.is_user_authorized():
                    await self.log_to_console("INFO", f"Creating new session for {account_name}")
                    sent_code = await client.send_code_request(account_data['phone_number'])
                    self.otp_requested_signal.emit(account_name)
                    otp = await self.wait_for_otp(account_name)
                    try:
                        await client.sign_in(phone=account_data['phone_number'], code=otp, phone_code_hash=sent_code.phone_code_hash)
                    except errors.SessionPasswordNeededError:
                        if 'password' in account_data and account_data['password']:
                            await client.sign_in(password=account_data['password'])
                        else:
                            await self.log_to_console("ERROR", f"2FA required for {account_name} but no password provided")
                            continue
                    session_string = client.session.save()
                    self.save_session(account_name, session_string, "AccountSession")
                    await self.log_to_console("SUCCESS", f"Session created and saved for {account_name}")
                else:
                    await self.log_to_console("SUCCESS", f"Session already exists for {account_name}")
                await client.disconnect()
            except Exception as e:
                await self.log_to_console("ERROR", f"Failed to create session for {account_name}: {str(e)}")

    async def fetch_message(self, url):
        try:
            from bs4 import BeautifulSoup
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        message = soup.find('meta', {'name': 'description'}) or soup.find('meta', {'property': 'og:description'}) or soup.find('meta', {'property': 'twitter:description'})
                        if message and message.get('content'):
                            text = message.get('content')
                            if len(text) > 4096:
                                text = text[:4093] + "..."
                            return text
                        text = soup.get_text()[:4096]
                        return text
                    else:
                        await self.log_to_console("ERROR", f"Failed to fetch message from {url}")
                        return None
        except Exception as e:
            await self.log_to_console("ERROR", f"Error parsing message: {str(e)}")
            return None

    async def resolve_peer(self, client, group_username):
        try:
            entity = await client.get_entity(group_username)
            if isinstance(entity, Channel):
                return entity
            result = await client(GetDialogsRequest(offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(), limit=100, hash=0))
            for dialog in result.dialogs:
                try:
                    dialog_entity = await client.get_entity(dialog.peer)
                    if hasattr(dialog_entity, 'username') and dialog_entity.username == group_username.split('/')[-1]:
                        return dialog_entity
                except:
                    continue
            return None
        except Exception as e:
            await self.log_to_console("ERROR", f"Failed to resolve peer: {str(e)}")
            return None

    async def scrape_members(self, group_username):
        self.stop_requested = False
        try:
            if 't.me/' in group_username:
                group_username = group_username.split('t.me/')[1]
            if '+' in group_username:
                group_username = group_username.replace('+', '')
            if 'joinchat/' in group_username:
                group_username = group_username.split('joinchat/')[1]
            await self.log_to_console("INFO", f"Connecting to group {group_username}")
            entity = await self.resolve_peer(self.config_client, group_username)
            if not entity:
                await self.log_to_console("ERROR", "Could not find or access the group. Make sure the link is correct and you have joined the group.")
                return
            if not isinstance(entity, Channel):
                await self.log_to_console("ERROR", "This link is not a supergroup or channel. Please provide a supergroup/channel link.")
                return
            try:
                offset = 0
                limit = 100
                all_participants = []
                while not self.stop_requested:
                    try:
                        participants = await self.config_client(GetParticipantsRequest(
                            channel=entity,
                            filter=ChannelParticipantsSearch(''),
                            offset=offset,
                            limit=limit,
                            hash=0
                        ))
                        if not participants.users:
                            break
                        all_participants.extend(participants.users)              
                        for user in participants.users:
                            if not (user.bot or user.deleted or user.id == self.config_user_id):
                                self.members.append({
                                    'id': user.id,
                                    'username': user.username,
                                    'phone': user.phone
                                })
                        await self.log_to_console("INFO", f'Scraping in progress: {len(self.members)} members found')
                        self.scraping_progress_signal.emit(len(self.members), 0)
                        if len(participants.users) < limit:
                            break
                        offset += len(participants.users)
                        await asyncio.sleep(2)
                    except errors.FloodWaitError as e:
                        wait_time = int(str(e).split('of ')[1].split(' ')[0])
                        await self.log_to_console("WARNING", f"Rate limited, waiting {wait_time} seconds")
                        await asyncio.sleep(wait_time)
                    except Exception as e:
                        await self.log_to_console("ERROR", f"Error during scraping: {str(e)}")
                        break
                if self.members:
                    await self.log_to_console("INFO", f"Saving {len(self.members)} scraped members to ScrapedData/scraped.json")
                    self.save_members()
                    await self.log_to_console("SUCCESS", f"Successfully saved {len(self.members)} members")
                else:
                    await self.log_to_console("WARNING", "No members were scraped")
            except errors.ChatAdminRequiredError:
                await self.log_to_console("ERROR", "Admin rights are required to scrape members from this group")
            except errors.ChannelPrivateError:
                await self.log_to_console("ERROR", "This group/channel is private. Please make sure you have joined it")
            except Exception as e:
                await self.log_to_console("ERROR", f"Failed to scrape members: {str(e)}")
        except Exception as e:
            await self.log_to_console("ERROR", f"Connection error: {str(e)}")

    def save_members(self):
        os.makedirs(os.path.join(self.PROJECT_ROOT, "ScrapedData"), exist_ok=True)
        file_path = os.path.join(self.PROJECT_ROOT, "ScrapedData", "scraped.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.members, f, ensure_ascii=False, indent=2)

    async def detect_session_type(self, session_file, directory="SessionData"):
        try:
            session_path = os.path.join(self.PROJECT_ROOT, directory, session_file)
            with open(session_path, 'r') as f:
                content = f.read(100)
                if content.startswith('1:') and '.' not in session_file:
                    return 'string'
                if len(content.strip()) > 50:
                    return 'string'
                return 'sqlite'
        except UnicodeDecodeError:
            return 'sqlite'
        except Exception as e:
            await self.log_to_console("WARNING", f"Error detecting session type for {session_file} in {directory}: {str(e)}")
            return None

    async def log_to_console(self, log_type, message):
        if self.console_callback:
            self.console_callback(log_type, message)
        else:
            print(f"[{log_type}] {message}")
        if self.discord_logger and self.config and self.config.get('discord_logging'):
            try:
                await self.discord_logger.log(message, log_type)
            except Exception as e:
                print(f"[ERROR] Failed to send Discord log: {str(e)}")

    async def get_group_link(self):
        try:
            group_link = self.config.get('group_url', '')
            if not group_link:
                await self.log_to_console("ERROR", "Group URL not found in config.json")
                return None
            await self.log_to_console("INFO", f"Using group link from config: {group_link}")
            return group_link
        except Exception as e:
            await self.log_to_console("ERROR", f"Error getting group link from config: {str(e)}")
            return None
        
    async def send_messages(self):
        try:
            scraped_path = os.path.join(self.PROJECT_ROOT, "ScrapedData", "scraped.json")
            if not os.path.exists(scraped_path):
                await self.log_to_console("ERROR", "No scraped members found. Please scrape members first.")
                return
            with open(scraped_path, 'r') as f:
                self.members = json.load(f)
            image_path = None
            if self.config.get('send_image', False):
                image_dir = os.path.join(self.PROJECT_ROOT, "Image")
                if not os.path.exists(image_dir):
                    os.makedirs(image_dir, exist_ok=True)
                    await self.log_to_console("WARNING", "Image directory created but no images found.")
                    return
                supported_formats = ('.jpg', '.jpeg', '.png', '.gif')
                images = [f for f in os.listdir(image_dir) if f.lower().endswith(supported_formats)]
                if not images:
                    await self.log_to_console("ERROR", "No supported images found in Image directory.")
                    return
                image_path = os.path.join(image_dir, images[0])
                await self.log_to_console("INFO", f"Using image: {images[0]}")
            session_dir = os.path.join(self.PROJECT_ROOT, "SessionData")
            session_files = [f for f in os.listdir(session_dir) if f.endswith('.session') or '.' not in f]
            if not session_files:
                await self.log_to_console("INFO", "No sessions found in SessionData, checking AccountSession...")
                account_session_dir = os.path.join(self.PROJECT_ROOT, "AccountSession")
                if os.path.exists(account_session_dir):
                    account_sessions = [f for f in os.listdir(account_session_dir) if f.endswith('.session') or '.' not in f]
                    if account_sessions:
                        await self.log_to_console("INFO", f"Found {len(account_sessions)} sessions in AccountSession. Moving to SessionData...")
                        for session_file in account_sessions:
                            try:
                                session_type = await self.detect_session_type(session_file, "AccountSession")
                                if session_type:
                                    src = os.path.join(account_session_dir, session_file)
                                    dst = os.path.join(session_dir, session_file)
                                    import shutil
                                    shutil.copy2(src, dst)
                                    await self.log_to_console("SUCCESS", f"Copied {session_type} session {session_file} to SessionData")
                                else:
                                    await self.log_to_console("WARNING", f"Could not determine session type for {session_file}, skipping...")
                            except Exception as e:
                                await self.log_to_console("ERROR", f"Failed to move session {session_file}: {str(e)}")
                        session_files = [f for f in os.listdir(session_dir) if f.endswith('.session') or '.' not in f]
            if not session_files:
                await self.log_to_console("INFO", "No sessions found in AccountSession, creating new sessions from accounts.json...")
                try:
                    await self.create_new_sessions()
                    account_session_dir = os.path.join(self.PROJECT_ROOT, "AccountSession")
                    if os.path.exists(account_session_dir):
                        new_sessions = [f for f in os.listdir(account_session_dir) if f.endswith('.session') or '.' not in f]
                        for session_file in new_sessions:
                            try:
                                session_type = await self.detect_session_type(session_file)
                                if session_type:
                                    src = os.path.join(account_session_dir, session_file)
                                    dst = os.path.join(session_dir, session_file)
                                    import shutil
                                    shutil.copy2(src, dst)
                                    await self.log_to_console("SUCCESS", f"Moved new {session_type} session {session_file} to SessionData")
                                else:
                                    await self.log_to_console("WARNING", f"Could not determine session type for new session {session_file}, skipping...")
                            except Exception as e:
                                await self.log_to_console("ERROR", f"Failed to move new session {session_file}: {str(e)}")
                        session_files = [f for f in os.listdir(session_dir) if f.endswith('.session') or '.' not in f]
                except Exception as e:
                    await self.log_to_console("ERROR", f"Failed to create new sessions: {str(e)}")
            if not session_files:
                await self.log_to_console("ERROR", "No valid sessions found in any location. Please add sessions or check account credentials.")
                return
            delay = self.config.get('delay_between_messages', 30)
            max_messages = self.config.get('messages_per_session', 10)
            remaining_members = [m for m in self.members if (m.get('username') or m.get('id')) not in self.sent_to]
            while remaining_members and not self.stop_requested:
                valid_sessions = session_files.copy()
                for session_file in session_files[:]:
                    if self.stop_requested or not remaining_members:
                        break
                    session_name = os.path.splitext(session_file)[0]
                    session_type = await self.detect_session_type(session_file)
                    if not session_type:
                        await self.log_to_console("ERROR", f"Could not determine session type for {session_name}, moving to invalid sessions...")
                        await self.move_to_invalid_session(session_file)
                        valid_sessions.remove(session_file)
                        continue
                    try:
                        await self.log_to_console("INFO", f"Attempting to use {session_type} session: {session_name}")                      
                        if session_type == 'sqlite':
                            session_path = os.path.join(session_dir, session_name)
                            client = TelegramClient(session_path, self.config['api_id'], self.config['api_hash'])
                        else:
                            try:
                                with open(os.path.join(session_dir, session_file), 'r') as f:
                                    session_string = f.read().strip()
                                client = TelegramClient(StringSession(session_string), self.config['api_id'], self.config['api_hash'])
                            except Exception as e:
                                await self.log_to_console("ERROR", f"Failed to read string session {session_name}: {str(e)}")
                                continue
                        try:
                            await client.connect()
                            if not await client.is_user_authorized():
                                await self.log_to_console("ERROR", f"Session {session_name} is not authorized, moving to invalid sessions...")
                                await self.move_to_invalid_session(session_file)
                                valid_sessions.remove(session_file)
                                await client.disconnect()
                                continue
                            me = await client.get_me()
                            await self.log_to_console("SUCCESS", f"Successfully logged in as {me.first_name} ({me.phone})")                         
                            messages_sent = 0
                            while messages_sent < max_messages and remaining_members and not self.stop_requested:
                                member = remaining_members[0]
                                user_id = member.get('username') or member.get('id')
                                try:
                                    message = await self.fetch_message(self.config['message_url'])
                                    if not message:
                                        await self.log_to_console("ERROR", "Failed to fetch message content")
                                        break
                                    if image_path and self.config.get('send_image'):
                                        try:
                                            await client.send_file(user_id, image_path, caption=message)
                                        except errors.PhotoInvalidDimensionsError:
                                            await self.log_to_console("ERROR", f"Invalid image dimensions for {user_id}, sending message only")
                                            await client.send_message(user_id, message)
                                        except Exception as e:
                                            await self.log_to_console("ERROR", f"Failed to send image to {user_id}, sending message only: {str(e)}")
                                            await client.send_message(user_id, message)
                                    else:
                                        await client.send_message(user_id, message)
                                    messages_sent += 1
                                    self.sent_to.add(user_id)
                                    remaining_members.pop(0)
                                    await self.log_to_console("SUCCESS", f"Message{' and image' if image_path and self.config.get('send_image') else ''} sent to {user_id}")
                                    await asyncio.sleep(delay)
                                except errors.FloodWaitError as e:
                                    wait_time = int(str(e).split('of ')[1].split(' ')[0])
                                    await self.log_to_console("WARNING", f"Rate limit hit, waiting {wait_time} seconds")
                                    await asyncio.sleep(wait_time)
                                except Exception as e:
                                    await self.log_to_console("ERROR", f"Failed to send to {user_id}: {str(e)}")
                                    remaining_members.pop(0)
                                    continue
                            await self.log_to_console("INFO", f"Session {session_name} completed. Sent {messages_sent} messages. {len(remaining_members)} members remaining")
                        except errors.SessionRevokedError:
                            await self.log_to_console("ERROR", f"Session {session_name} has been revoked, moving to invalid sessions...")
                            await self.move_to_invalid_session(session_file)
                            valid_sessions.remove(session_file)
                            continue
                        except errors.SessionExpiredError:
                            await self.log_to_console("ERROR", f"Session {session_name} has expired, moving to invalid sessions...")
                            await self.move_to_invalid_session(session_file)
                            valid_sessions.remove(session_file)
                            continue
                        finally:
                            await client.disconnect()
                    except Exception as e:
                        await self.log_to_console("ERROR", f"Error with session {session_name}: {str(e)}")
                        if "auth_key" in str(e).lower() or "session" in str(e).lower():
                            await self.log_to_console("ERROR", f"Session appears to be invalid, moving to invalid sessions...")
                            await self.move_to_invalid_session(session_file)
                            valid_sessions.remove(session_file)
                        continue
                session_files = valid_sessions
                if not session_files:
                    await self.log_to_console("ERROR", "No valid sessions remaining. Stopping process...")
                    break
                if remaining_members and not self.stop_requested:
                    await self.log_to_console("INFO", "All valid sessions used. Starting new cycle with remaining members...")
                    await asyncio.sleep(delay)
            if not remaining_members:
                await self.log_to_console("SUCCESS", "All members have been messaged successfully")
            elif self.stop_requested:
                await self.log_to_console("INFO", f"Process stopped. {len(remaining_members)} members remaining")
        except Exception as e:
            await self.log_to_console("ERROR", f"Error in send_messages: {str(e)}")
        
    async def run(self):
        if self.is_running:
            await self.log_to_console("WARNING", "Process is already running")
            return
        if not await self.initialize_config():
            return
        self.is_running = True
        self.stop_requested = False
        try:
            if self.update_dashboard_status:
                self.update_dashboard_status("running")         
            await self.log_to_console("INFO", "Starting MassDM Bot...")
            scraped_path = os.path.join(self.PROJECT_ROOT, "ScrapedData", "scraped.json")
            if os.path.exists(scraped_path):
                try:
                    with open(scraped_path, 'r') as f:
                        existing_members = json.load(f)
                    if existing_members:
                        future = asyncio.Future()
                        dialog = ExistingMembersDialog(len(existing_members))
                        def on_existing_result(result):
                            future.set_result(result)
                        dialog.result_signal.connect(on_existing_result)
                        dialog.show()
                        use_existing = await future
                        if use_existing:
                            self.members = existing_members
                            await self.send_messages()
                            return
                        else:
                            os.remove(scraped_path)
                            self.members = []
                except Exception as e:
                    await self.log_to_console("ERROR", f"Error checking existing members: {str(e)}")
                    return
            if not await self.initialize_config_client():
                await self.log_to_console("ERROR", "Failed to initialize config client. Stopping process.")
                return
            group_link = await self.get_group_link()
            if not group_link:
                await self.log_to_console("ERROR", "No group link provided")
                return
            await self.scrape_members(group_link)
            if not self.members:
                await self.log_to_console("WARNING", "No members were scraped")
                return
            await self.log_to_console("SUCCESS", f"Successfully scraped {len(self.members)} members")
            future = asyncio.Future()
            dialog = ScrapedMembersDialog(len(self.members))
            def on_scrape_result(result):
                future.set_result(result)
            dialog.result_signal.connect(on_scrape_result)
            dialog.show()
            start_sending = await future
            if start_sending:
                await self.send_messages()
        except Exception as e:
            await self.log_to_console("ERROR", f"Error in Mass DM process: {str(e)}")
        finally:
            self.is_running = False
            if self.update_dashboard_status:
                self.update_dashboard_status("stopped")
            if hasattr(self, 'config_client') and self.config_client:
                await self.config_client.disconnect()
            await self.log_to_console("INFO", "MassDM Bot process finished")

    async def stop(self):
        self.stop_requested = True
        await self.log_to_console("INFO", "Stopping Mass DM process...")
        while self.is_running:
            await asyncio.sleep(0.1)
        await self.log_to_console("INFO", "Mass DM process stopped.")
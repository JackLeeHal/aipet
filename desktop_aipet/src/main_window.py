import sys
import os
import asyncio
import datetime
import uuid
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton,
                             QLabel, QDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QDateTimeEdit,
                             QMenu, QFileDialog, QSizeGrip, QFormLayout)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPalette, QPainter, QBrush, QPen, QAction, QPixmap

from .agent_core import ChatAgent
from .scheduler_service import set_alert_callback, get_all_reminders, delete_reminder, update_reminder
from .memory_service import load_config, save_config, get_all_sessions, create_session, get_session_messages

class WorkerSignals(QObject):
    response_received = pyqtSignal(str) # Deprecated
    response_start = pyqtSignal()
    response_chunk = pyqtSignal(str)
    response_finished = pyqtSignal()

class PetLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.drag_start_pos = None
        self.window_start_pos = None
        self.is_dragging = False

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
                font-size: 12px;
                color: #333;
            }
            QMenu::item:selected {
                background-color: #0078d7;
                color: white;
            }
        """)

        settings_action = QAction("Modify AI Config", self)
        settings_action.triggered.connect(self.window().open_settings)
        menu.addAction(settings_action)

        image_action = QAction("Change Pet Image", self)
        image_action.triggered.connect(self.window().change_avatar)
        menu.addAction(image_action)

        menu.addSeparator()

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.window().exit_app)
        menu.addAction(exit_action)

        menu.exec(event.globalPos())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.globalPosition().toPoint()
            self.window_start_pos = self.window().frameGeometry().topLeft()
            self.is_dragging = False
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_start_pos:
            current_pos = event.globalPosition().toPoint()
            if (current_pos - self.drag_start_pos).manhattanLength() > 5:
                self.is_dragging = True

            if self.is_dragging:
                delta = current_pos - self.drag_start_pos
                self.window().move(self.window_start_pos + delta)
                event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.is_dragging:
                self.clicked.emit()
            self.drag_start_pos = None
            self.is_dragging = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI Configuration")
        self.resize(400, 200)
        layout = QFormLayout()

        self.config = load_config()
        llm_config = self.config.get('llm', {})

        self.api_key_edit = QLineEdit(llm_config.get('api_key', ''))
        self.base_url_edit = QLineEdit(llm_config.get('base_url', ''))
        self.model_edit = QLineEdit(llm_config.get('model', 'gpt-3.5-turbo'))

        layout.addRow("API Key:", self.api_key_edit)
        layout.addRow("Base URL:", self.base_url_edit)
        layout.addRow("Model:", self.model_edit)

        btns = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(save_btn)
        btns.addWidget(cancel_btn)
        layout.addRow(btns)

        self.setLayout(layout)

    def save_settings(self):
        if 'llm' not in self.config:
            self.config['llm'] = {}

        self.config['llm']['api_key'] = self.api_key_edit.text()
        self.config['llm']['base_url'] = self.base_url_edit.text()
        self.config['llm']['model'] = self.model_edit.text()

        save_config(self.config)
        QMessageBox.information(self, "Success", "Settings saved successfully.")
        self.accept()

class EditReminderDialog(QDialog):
    def __init__(self, msg, time_iso, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Reminder")
        layout = QVBoxLayout()

        self.msg_edit = QLineEdit(msg)
        self.time_edit = QDateTimeEdit()
        self.time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.time_edit.setCalendarPopup(True)

        try:
            dt = datetime.datetime.fromisoformat(time_iso)
            self.time_edit.setDateTime(dt)
        except ValueError:
            self.time_edit.setDateTime(datetime.datetime.now())

        layout.addWidget(QLabel("Message:"))
        layout.addWidget(self.msg_edit)
        layout.addWidget(QLabel("Time:"))
        layout.addWidget(self.time_edit)

        btns = QHBoxLayout()
        ok = QPushButton("Save")
        ok.clicked.connect(self.accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(ok)
        btns.addWidget(cancel)
        layout.addLayout(btns)
        self.setLayout(layout)

    def get_data(self):
        # Return ISO string
        return self.msg_edit.text(), self.time_edit.dateTime().toPyDateTime().isoformat()

class ReminderManager(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Reminders")
        self.resize(500, 300)
        self.layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Time", "Message", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_reminders)
        btn_layout.addWidget(refresh_btn)

        edit_btn = QPushButton("Edit Selected")
        edit_btn.clicked.connect(self.edit_selected)
        btn_layout.addWidget(edit_btn)

        delete_btn = QPushButton("Delete Selected")
        delete_btn.clicked.connect(self.delete_selected)
        btn_layout.addWidget(delete_btn)

        self.layout.addLayout(btn_layout)
        self.setLayout(self.layout)

        self.refresh_reminders()

    def refresh_reminders(self):
        asyncio.create_task(self._load_reminders())

    async def _load_reminders(self):
        reminders = await get_all_reminders()
        self.table.setRowCount(0)
        for r in reminders:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(str(r['run_date'])))
            self.table.setItem(row, 1, QTableWidgetItem(r['message']))
            self.table.setItem(row, 2, QTableWidgetItem(r['status']))
            # Store ID in the first item's user data
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, r['id'])

    def delete_selected(self):
        rows = set(index.row() for index in self.table.selectedIndexes())
        if not rows: return

        ids = []
        for row in rows:
            item = self.table.item(row, 0)
            ids.append(item.data(Qt.ItemDataRole.UserRole))

        asyncio.create_task(self._delete_reminders(ids))

    async def _delete_reminders(self, ids):
        for r_id in ids:
            await delete_reminder(r_id)
        await self._load_reminders()

    def edit_selected(self):
        rows = set(index.row() for index in self.table.selectedIndexes())
        if len(rows) != 1:
            QMessageBox.warning(self, "Edit", "Please select exactly one reminder to edit.")
            return

        row = list(rows)[0]
        r_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        current_time = self.table.item(row, 0).text()
        current_msg = self.table.item(row, 1).text()

        dialog = EditReminderDialog(current_msg, current_time, self)
        if dialog.exec():
            new_msg, new_time = dialog.get_data()
            asyncio.create_task(self._update_reminder(r_id, new_msg, new_time))

    async def _update_reminder(self, r_id, msg, time):
        success = await update_reminder(r_id, msg, time)
        if success:
            await self._load_reminders()
        else:
            QMessageBox.critical(self, "Error", "Failed to update reminder. Check if time is in the future.")

class AlertDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reminder")
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
                border-radius: 10px;
            }
            QLabel {
                font-size: 14px;
                color: #333;
                padding: 10px;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border-radius: 5px;
                padding: 5px 15px;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        layout = QVBoxLayout()
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
        self.setLayout(layout)

class SessionManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chat History")
        self.resize(400, 300)
        self.layout = QVBoxLayout()

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Title", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self.open_session)
        btn_layout.addWidget(open_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        self.layout.addLayout(btn_layout)
        self.setLayout(self.layout)

        self.selected_session_id = None
        self.refresh_sessions()

    def refresh_sessions(self):
        asyncio.create_task(self._load_sessions())

    async def _load_sessions(self):
        sessions = await get_all_sessions()
        self.table.setRowCount(0)
        for s in sessions:
            # s: id, title, created_at
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(s[1] if s[1] else "New Chat"))
            self.table.setItem(row, 1, QTableWidgetItem(s[2]))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, s[0])

    def open_session(self):
        rows = self.table.selectedIndexes()
        if not rows:
            return

        # Get ID from first column of selected row
        row_idx = rows[0].row()
        self.selected_session_id = self.table.item(row_idx, 0).data(Qt.ItemDataRole.UserRole)
        self.accept()

class ChatOverlay(QWidget):
    def __init__(self, agent: ChatAgent, parent=None):
        super().__init__(parent)
        self.agent = agent

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            ChatOverlay {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                border: 1px solid #ccc;
            }
            QTextEdit {
                background-color: transparent;
                border: none;
                font-family: Arial;
                font-size: 14px;
            }
            QLineEdit {
                border: 1px solid #ccc;
                border-radius: 15px;
                padding: 8px;
                background-color: white;
            }
            QPushButton {
                background-color: #0078d7;
                color: white;
                border-radius: 15px;
                padding: 8px 15px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)

        self.layout = QVBoxLayout()

        # Top Bar
        top_bar = QHBoxLayout()
        history_btn = QPushButton("📜 History")
        history_btn.clicked.connect(self.open_history)
        top_bar.addWidget(history_btn)

        new_chat_btn = QPushButton("➕ New Chat")
        new_chat_btn.clicked.connect(self.new_chat)
        top_bar.addWidget(new_chat_btn)

        top_bar.addStretch()
        self.layout.addLayout(top_bar)

        self.history = QTextEdit()
        self.history.setReadOnly(True)
        self.layout.addWidget(self.history)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)

        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send_message)
        input_layout.addWidget(send_btn)

        reminders_btn = QPushButton("⏰")
        reminders_btn.clicked.connect(self.open_reminders)
        input_layout.addWidget(reminders_btn)

        self.layout.addLayout(input_layout)

        # Resize Grip
        grip_layout = QHBoxLayout()
        grip_layout.addStretch()
        self.size_grip = QSizeGrip(self)
        grip_layout.addWidget(self.size_grip)
        self.layout.addLayout(grip_layout)
        # Remove margins from grip layout to keep it tight
        grip_layout.setContentsMargins(0, 0, 0, 0)

        self.setLayout(self.layout)

        # Signals for async handling
        self.signals = WorkerSignals()
        self.signals.response_start.connect(self.on_response_start)
        self.signals.response_chunk.connect(self.on_response_chunk)
        self.signals.response_finished.connect(self.on_response_finished)

        # State for streaming
        self.current_ai_text = ""
        self.ai_message_anchor_pos = 0

        # Start default session
        self.new_chat()

    def new_chat(self):
        new_id = str(uuid.uuid4())
        asyncio.create_task(self._init_session(new_id))

    async def _init_session(self, session_id):
        await create_session(session_id, None) # Title will be generated later
        await self.agent.start_session(session_id)
        self.history.clear()

    def open_history(self):
        dialog = SessionManagerDialog(self)
        if dialog.exec():
            session_id = dialog.selected_session_id
            if session_id:
                asyncio.create_task(self.load_session(session_id))

    async def load_session(self, session_id):
        await self.agent.start_session(session_id)
        msgs = await get_session_messages(session_id)
        self.history.clear()
        for role, content, _ in msgs:
            if role == 'user':
                self.append_user_message_html(content)
            elif role == 'assistant':
                self.append_ai_message_html(content)

    def format_user_html(self, msg):
        return f"""
        <table width="100%" border="0" cellpadding="5">
            <tr>
                <td width="20%"></td>
                <td align="right">
                    <div style="background-color: #DCF8C6; color: black; padding: 10px; border-radius: 10px;">
                        {msg}
                    </div>
                </td>
            </tr>
        </table>
        """

    def format_ai_html(self, msg):
        return f"""
        <table width="100%" border="0" cellpadding="5">
            <tr>
                <td align="left">
                    <div style="background-color: #F0F0F0; color: black; padding: 10px; border-radius: 10px;">
                        {msg}
                    </div>
                </td>
                <td width="20%"></td>
            </tr>
        </table>
        """

    def append_user_message_html(self, msg):
        self.history.append(self.format_user_html(msg))

    def append_ai_message_html(self, msg):
        self.history.append(self.format_ai_html(msg))

    def send_message(self):
        msg = self.input_field.text()
        if not msg: return

        self.append_user_message_html(msg)
        self.input_field.clear()

        # Async call to agent
        asyncio.create_task(self.process_message(msg))

    async def process_message(self, msg):
        self.signals.response_start.emit()
        async for chunk in self.agent.chat_stream(msg):
            self.signals.response_chunk.emit(chunk)
        self.signals.response_finished.emit()

    def on_response_start(self):
        self.current_ai_text = "..."
        # Append placeholder
        self.history.append(self.format_ai_html(self.current_ai_text))
        # Store position?
        # Actually, since we just appended, the cursor is at the end.
        # But we need to replace the *last block* repeatedly.

    def on_response_chunk(self, chunk):
        if self.current_ai_text == "...":
            self.current_ai_text = ""

        self.current_ai_text += chunk
        self._update_last_message(self.format_ai_html(self.current_ai_text))

    def on_response_finished(self):
        # Final update to ensure everything is correct
        self._update_last_message(self.format_ai_html(self.current_ai_text))

    def _update_last_message(self, html):
        cursor = self.history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        cursor.select(cursor.SelectionType.BlockUnderCursor)
        # Wait, if we appended a table, is it one block?
        # HTML might create multiple blocks if it has newlines.
        # But our format string is one block usually.
        # If it fails, we might be overwriting wrongly.

        # Alternative: Remove from end until we hit the previous user message?
        # No, that's dangerous.

        # Let's assume append created a block.
        # If we select BlockUnderCursor at End, we get the last block.
        cursor.removeSelectedText()
        cursor.insertHtml(html)
        # Move cursor to end again to be safe
        self.history.moveCursor(cursor.MoveOperation.End)

    def open_reminders(self):
        manager = ReminderManager(self)
        manager.exec()

class MainWindow(QMainWindow):
    alert_signal = pyqtSignal(str)

    def __init__(self, agent):
        super().__init__()
        self.agent = agent

        # Transparent window setup
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Pet representation (Placeholder Label)
        self.pet_label = PetLabel("🤖")
        self.pet_label.setStyleSheet("font-size: 64px; color: white; background-color: rgba(0,0,0,100); border-radius: 10px;")
        self.pet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pet_label.clicked.connect(self.toggle_chat)
        self.layout.addWidget(self.pet_label)

        # Chat Overlay
        self.chat_overlay = ChatOverlay(self.agent)
        self.chat_overlay.hide()
        self.layout.addWidget(self.chat_overlay)

        self.alert_signal.connect(self.show_alert)
        set_alert_callback(self.alert_signal.emit)

        self.update_pet_avatar()

    def toggle_chat(self):
        if self.chat_overlay.isVisible():
            self.chat_overlay.hide()
        else:
            self.chat_overlay.show()

    def show_alert(self, message):
        dialog = AlertDialog(message, self)
        dialog.show()

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    def change_avatar(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Pet Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            # Verify image
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "Error", "Failed to load image. Please select a valid image file.")
                return

            config = load_config()
            if 'pet' not in config:
                config['pet'] = {}
            config['pet']['avatar_path'] = file_path
            save_config(config)
            self.update_pet_avatar()

    def update_pet_avatar(self):
        config = load_config()
        avatar_path = config.get('pet', {}).get('avatar_path')

        if avatar_path:
            if not os.path.exists(avatar_path):
                print(f"Error: Avatar file not found at {avatar_path}")
            else:
                pixmap = QPixmap(avatar_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.pet_label.setPixmap(scaled_pixmap)
                    self.pet_label.setText("") # Clear text if image is set
                    return
                else:
                    print(f"Error: Failed to load avatar from {avatar_path}")

        # Fallback
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_pet_path = os.path.join(base_dir, 'assets', 'pet.png')
        if os.path.exists(default_pet_path):
            pixmap = QPixmap(default_pet_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(128, 128, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.pet_label.setPixmap(scaled_pixmap)
                self.pet_label.setText("")
                return

        self.pet_label.setText("🤖")
        self.pet_label.setPixmap(QPixmap()) # Clear pixmap

    def exit_app(self):
        QApplication.quit()

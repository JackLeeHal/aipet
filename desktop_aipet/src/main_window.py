import sys
import asyncio
import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton,
                             QLabel, QDialog, QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView, QDateTimeEdit)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPalette, QPainter, QBrush, QPen

from .agent_core import ChatAgent
from .scheduler_service import set_alert_callback, get_all_reminders, delete_reminder, update_reminder

class WorkerSignals(QObject):
    response_received = pyqtSignal(str)

class PetLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.drag_start_pos = None
        self.window_start_pos = None
        self.is_dragging = False

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
        self.setLayout(self.layout)

        # Signals for async handling
        self.signals = WorkerSignals()
        self.signals.response_received.connect(self.append_response)

    def send_message(self):
        msg = self.input_field.text()
        if not msg: return

        # HTML formatting for User
        user_html = f"""
        <p align="right" style="margin: 5px;">
            <span style="background-color: #DCF8C6; color: black; padding: 10px;">
                {msg}
            </span>
        </p>
        """
        self.history.append(user_html)
        self.input_field.clear()

        # Async call to agent
        asyncio.create_task(self.process_message(msg))

    async def process_message(self, msg):
        response = await self.agent.chat(msg)
        self.signals.response_received.emit(response)

    def append_response(self, response):
        # HTML formatting for Pet
        pet_html = f"""
        <p align="left" style="margin: 5px;">
             <span style="background-color: #F0F0F0; color: black; padding: 10px;">
                {response}
            </span>
        </p>
        """
        self.history.append(pet_html)

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

    def toggle_chat(self):
        if self.chat_overlay.isVisible():
            self.chat_overlay.hide()
        else:
            self.chat_overlay.show()

    def show_alert(self, message):
        dialog = AlertDialog(message, self)
        dialog.show()

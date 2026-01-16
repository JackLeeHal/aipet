import sys
import asyncio
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QTextEdit, QLineEdit, QPushButton,
                             QLabel, QDialog, QMessageBox)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QColor, QPalette, QPainter, QBrush, QPen

from .agent_core import ChatAgent
from .scheduler_service import set_alert_callback

class WorkerSignals(QObject):
    response_received = pyqtSignal(str)

class AlertDialog(QDialog):
    def __init__(self, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reminder")
        layout = QVBoxLayout()
        layout.addWidget(QLabel(message))
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)
        self.setLayout(layout)

class ChatOverlay(QWidget):
    def __init__(self, agent: ChatAgent, parent=None):
        super().__init__(parent)
        self.agent = agent
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

        self.layout.addLayout(input_layout)
        self.setLayout(self.layout)

        # Signals for async handling
        self.signals = WorkerSignals()
        self.signals.response_received.connect(self.append_response)

    def send_message(self):
        msg = self.input_field.text()
        if not msg: return

        self.history.append(f"You: {msg}")
        self.input_field.clear()

        # Async call to agent
        asyncio.create_task(self.process_message(msg))

    async def process_message(self, msg):
        response = await self.agent.chat(msg)
        self.signals.response_received.emit(response)

    def append_response(self, response):
        self.history.append(f"Pet: {response}")

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
        self.pet_label = QLabel("🤖")
        self.pet_label.setStyleSheet("font-size: 64px; color: white; background-color: rgba(0,0,0,100); border-radius: 10px;")
        self.pet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.pet_label)

        # Chat Overlay
        self.chat_overlay = ChatOverlay(self.agent)
        self.chat_overlay.hide()
        self.layout.addWidget(self.chat_overlay)

        # Toggle chat on click (requires subclassing QLabel or event filter,
        # but for simplicity we can just add mousePressEvent to central widget or label)
        self.pet_label.mousePressEvent = self.toggle_chat

        self.alert_signal.connect(self.show_alert)
        set_alert_callback(self.alert_signal.emit)

    def toggle_chat(self, event):
        if self.chat_overlay.isVisible():
            self.chat_overlay.hide()
        else:
            self.chat_overlay.show()

    def show_alert(self, message):
        dialog = AlertDialog(message, self)
        dialog.show()

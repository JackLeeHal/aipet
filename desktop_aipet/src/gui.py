import tkinter as tk
import tkinter.messagebox
from tkinter import ttk, simpledialog
from PIL import Image, ImageTk
import threading

class ChatWindow(tk.Toplevel):
    def __init__(self, parent, core):
        super().__init__(parent)
        self.title("Chat with RoboPet")
        self.geometry("400x500")
        self.core = core

        # Chat history area
        self.history_area = tk.Text(self, state='disabled', wrap='word')
        self.history_area.pack(expand=True, fill='both', padx=5, pady=5)

        # Input area
        input_frame = ttk.Frame(self)
        input_frame.pack(fill='x', padx=5, pady=5)

        self.input_entry = ttk.Entry(input_frame)
        self.input_entry.pack(side='left', expand=True, fill='x')
        self.input_entry.bind("<Return>", self.send_message)

        send_btn = ttk.Button(input_frame, text="Send", command=self.send_message)
        send_btn.pack(side='right')

        self.load_history()

    def load_history(self):
        # Load recent history
        from desktop_aipet.src import database
        history = database.get_history(limit=20, db_path=self.core.db_path)
        self.history_area.config(state='normal')
        for role, content, _ in history:
            tag = 'user' if role == 'user' else 'bot'
            self.history_area.insert('end', f"{role}: {content}\n", tag)
        self.history_area.config(state='disabled')
        self.history_area.see('end')

    def send_message(self, event=None):
        msg = self.input_entry.get()
        if not msg.strip():
            return

        self.input_entry.delete(0, 'end')
        self.append_text(f"user: {msg}\n")

        # Run in thread to not block GUI
        def process():
            response = self.core.send_user_message(msg)
            self.after(0, lambda: self.append_text(f"assistant: {response}\n"))

        threading.Thread(target=process).start()

    def append_text(self, text):
        self.history_area.config(state='normal')
        self.history_area.insert('end', text)
        self.history_area.config(state='disabled')
        self.history_area.see('end')

class PetWindow(tk.Tk):
    def __init__(self, core):
        super().__init__()
        self.core = core
        self.core.set_notification_callback(self.show_notification)

        # Window configuration
        self.overrideredirect(True) # Frameless
        self.attributes('-topmost', True)
        self.wm_attributes('-transparentcolor', 'white') # Assuming white background in image is transparent

        # Load image
        try:
            self.image = Image.open('desktop_aipet/assets/pet.png')
            self.photo = ImageTk.PhotoImage(self.image)
        except Exception as e:
            print(f"Error loading image: {e}")
            self.photo = None

        self.label = tk.Label(self, image=self.photo, bg='white')
        self.label.pack()

        # Positioning (Bottom Right)
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        self.geometry(f"+{screen_width - 150}+{screen_height - 150}")

        # Dragging functionality
        self.label.bind('<Button-1>', self.start_move)
        self.label.bind('<B1-Motion>', self.do_move)

        # Context Menu
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Chat", command=self.open_chat)
        self.menu.add_command(label="Quit", command=self.quit_app)
        self.label.bind('<Button-3>', self.show_menu)

        self.chat_window = None

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def show_menu(self, event):
        self.menu.post(event.x_root, event.y_root)

    def open_chat(self):
        if not self.chat_window or not self.chat_window.winfo_exists():
            self.chat_window = ChatWindow(self, self.core)
        else:
            self.chat_window.lift()

    def show_notification(self, message):
        # Simple popup for now, or could be a speech bubble on the pet
        # For thread safety, use after
        self.after(0, lambda: tk.messagebox.showinfo("Notification", message))

    def quit_app(self):
        self.core.stop()
        self.destroy()

def run_gui():
    from desktop_aipet.src.core import PetCore
    core = PetCore()
    core.start()

    app = PetWindow(core)
    app.mainloop()

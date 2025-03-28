import customtkinter as ctk
import socket
import threading
import random
import subprocess
import sys
import os

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000

class ListItemWindow(ctk.CTkToplevel):
    """
    A pop-up window for a Seller to enter item info:
      - Item Name
      - Description
      - Start Price
      - Duration (in seconds)
      - A "List Item" button
    """
    def __init__(self, user_window):
        super().__init__()
        self.user_window = user_window  # reference to the parent user window
        self.title("List an Item for Auction")
        self.geometry("300x320")
        self.resizable(False, False)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Item Name
        ctk.CTkLabel(main_frame, text="Item Name:").pack(anchor="w")
        self.item_name_var = ctk.StringVar()
        self.item_name_entry = ctk.CTkEntry(main_frame, textvariable=self.item_name_var)
        self.item_name_entry.pack(pady=5, fill="x")

        # Description
        ctk.CTkLabel(main_frame, text="Description:").pack(anchor="w")
        self.item_desc_var = ctk.StringVar()
        self.item_desc_entry = ctk.CTkEntry(main_frame, textvariable=self.item_desc_var)
        self.item_desc_entry.pack(pady=5, fill="x")

        # Start Price
        ctk.CTkLabel(main_frame, text="Start Price:").pack(anchor="w")
        self.start_price_var = ctk.StringVar()
        self.start_price_entry = ctk.CTkEntry(main_frame, textvariable=self.start_price_var)
        self.start_price_entry.pack(pady=5, fill="x")

        # Duration (in seconds)
        ctk.CTkLabel(main_frame, text="Duration (in seconds):").pack(anchor="w")
        self.duration_var = ctk.StringVar()
        self.duration_entry = ctk.CTkEntry(main_frame, textvariable=self.duration_var)
        self.duration_entry.pack(pady=5, fill="x")

        # "List Item" button
        self.submit_btn = ctk.CTkButton(main_frame, text="List Item", command=self.submit_item)
        self.submit_btn.pack(pady=10)

    def submit_item(self):
        """Gather fields and send a LIST_ITEM request via the parent user window."""
        item_name = self.item_name_var.get().strip()
        item_desc = self.item_desc_var.get().strip()
        start_price = self.start_price_var.get().strip()
        duration = self.duration_var.get().strip()

        if not item_name or not start_price or not duration:
            self.user_window.add_log("ERROR: Please fill out all required fields.")
            return

        # Call the user window's send_list_item with 4 arguments.
        self.user_window.send_list_item(item_name, item_desc, start_price, duration)
        self.destroy()


class UserWindow(ctk.CTkToplevel):
    """
    A window for a logged-in or registered user.
    - Shows user info, de-register button, log area.
    - If seller, shows a "List Item" button and "Your Listed Items" area.
    """
    def __init__(self, master_app, name, role, udp_port, tcp_port):
        super().__init__()
        self.master_app = master_app  # reference to the main client app
        self.name = name
        self.role = role
        self.udp_port = udp_port
        self.tcp_port = tcp_port

        self.title(f"User: {self.name}")
        self.geometry("400x400")
        self.resizable(False, False)

        self.my_items = []  # track items listed by this user

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Info label
        info_text = (
            f"Name: {self.name}\n"
            f"Role: {self.role}\n"
            f"UDP Port: {self.udp_port}\n"
            f"TCP Port: {self.tcp_port}"
        )
        self.info_label = ctk.CTkLabel(main_frame, text=info_text)
        self.info_label.pack(pady=5)

        # De-register button
        self.dereg_button = ctk.CTkButton(main_frame, text="De-register", command=self.request_deregister)
        self.dereg_button.pack(pady=5)

        # If Seller, show "List Item" button
        if self.role.lower() == "seller":
            self.list_item_button = ctk.CTkButton(main_frame, text="List Item", command=self.open_list_item_window)
            self.list_item_button.pack(pady=5)

        # Log area
        self.log_text = ctk.CTkTextbox(main_frame, width=360, height=80)
        self.log_text.pack(pady=5)

        # "Your Listed Items" area for sellers
        if self.role.lower() == "seller":
            ctk.CTkLabel(main_frame, text="Your Listed Items:").pack(anchor="w")
            self.my_items_text = ctk.CTkTextbox(main_frame, width=360, height=80)
            self.my_items_text.pack(pady=5)
        else:
            self.my_items_text = None

    def add_log(self, message: str):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def request_deregister(self):
        self.master_app.send_deregister(self.name, self)

    def open_list_item_window(self):
        """Open the ListItemWindow pop-up for sellers."""
        ListItemWindow(self)

    def send_list_item(self, item_name, item_desc, start_price, duration):
        """
        Called by ListItemWindow.
        Automatically uses self.name as the user name and passes self as the user window.
        """
        self.master_app.send_list_item(self.name, item_name, item_desc, start_price, duration, self)
        self.add_log(f"Sent LIST_ITEM for item '{item_name}'.")

    def add_my_item(self, item_name):
        self.my_items.append(item_name)
        if self.my_items_text:
            self.my_items_text.insert("end", f"{item_name}\n")
            self.my_items_text.see("end")

    def close_window(self):
        self.destroy()


class ClientApp(ctk.CTk):
    """
    Main client window.
    - Provides Name entry, Role dropdown, Register and Login buttons, and a log area.
    - On successful register/login, opens a UserWindow.
    - Automatically spawns the server as a subprocess.
    """
    def __init__(self):
        super().__init__()
        self.title("Client Main Page")
        self.geometry("500x300")
        self.resizable(False, False)

        # Automatically launch server.py as a subprocess
        script_dir = os.path.dirname(os.path.abspath(__file__))
        server_script = os.path.join(script_dir, "server.py")
        self.server_process = subprocess.Popen([sys.executable, server_script])

        # Create a UDP socket for the entire client
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SERVER_IP, 0))  # bind to a random local UDP port
        self.local_udp_port = self.sock.getsockname()[1]

        # For tracking in-flight requests
        self.requests = {}
        # For tracking open user windows by name
        self.user_windows = {}

        # Start a background thread to listen for server responses
        self.listening = True
        threading.Thread(target=self.listen_server, daemon=True).start()

        # Build the main UI
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(main_frame, text="Name:").pack(anchor="w")
        self.name_var = ctk.StringVar()
        self.name_entry = ctk.CTkEntry(main_frame, textvariable=self.name_var, width=200)
        self.name_entry.pack(pady=5)

        ctk.CTkLabel(main_frame, text="Role:").pack(anchor="w")
        self.role_var = ctk.StringVar(value="Buyer")
        self.role_menu = ctk.CTkOptionMenu(main_frame, values=["Buyer", "Seller"], variable=self.role_var)
        self.role_menu.pack(pady=5)

        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(pady=5)

        self.register_button = ctk.CTkButton(button_frame, text="Register", command=self.register_user)
        self.register_button.pack(side="left", padx=5)

        self.login_button = ctk.CTkButton(button_frame, text="Login", command=self.login_user)
        self.login_button.pack(side="left", padx=5)

        self.log_text = ctk.CTkTextbox(main_frame, width=450, height=80)
        self.log_text.pack(pady=5)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        self.listening = False
        self.sock.close()
        for w in list(self.user_windows.values()):
            w.close_window()
        if self.server_process:
            self.server_process.terminate()
        self.destroy()

    def add_log(self, msg: str):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    # -------------------------------
    # Sending Requests to the Server
    # -------------------------------

    def register_user(self):
        name = self.name_var.get().strip()
        role = self.role_var.get().strip()
        if not name:
            self.add_log("ERROR: Name cannot be empty.")
            return
        rq = str(random.randint(1000, 9999))
        tcp_port = str(random.randint(40001, 50000))
        msg = f"REGISTER {rq} {name} {role} {SERVER_IP} {self.local_udp_port} {tcp_port}"
        self.sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
        self.requests[rq] = {"type": "register", "name": name, "role": role, "tcp_port": tcp_port}
        self.add_log(f"Sent REGISTER (RQ={rq}) for {name} ({role}).")

    def login_user(self):
        name = self.name_var.get().strip()
        role = self.role_var.get().strip()
        if not name:
            self.add_log("ERROR: Name cannot be empty.")
            return
        rq = str(random.randint(1000, 9999))
        msg = f"LOGIN {rq} {name} {role}"
        self.sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
        self.requests[rq] = {"type": "login", "name": name, "role": role}
        self.add_log(f"Sent LOGIN (RQ={rq}) for {name} ({role}).")

    def send_deregister(self, name, user_window):
        rq = str(random.randint(1000, 9999))
        msg = f"DE-REGISTER {rq} {name}"
        self.sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
        self.requests[rq] = {"type": "deregister", "name": name, "window": user_window}
        self.add_log(f"Sent DE-REGISTER (RQ={rq}) for {name}.")

    def send_list_item(self, user_name, item_name, item_desc, start_price, duration, user_window):
        rq = str(random.randint(1000, 9999))
        # Note: The username is now included in the message.
        msg = f"LIST_ITEM {rq} {user_name} {item_name} {item_desc} {start_price} {duration}"
        self.sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
        self.requests[rq] = {"type": "list_item", "user_name": user_name, "item_name": item_name, "window": user_window}
        self.add_log(f"Sent LIST_ITEM (RQ={rq}) for item '{item_name}'.")

    # -------------------------------
    # Receiving Responses from the Server
    # -------------------------------

    def listen_server(self):
        while self.listening:
            try:
                data, addr = self.sock.recvfrom(1024)
                response = data.decode()
                self.handle_server_response(response)
            except:
                break

    def handle_server_response(self, response: str):
        self.add_log(f"Received: {response}")
        parts = response.split()
        if len(parts) < 2:
            return

        cmd = parts[0].upper()
        rq = parts[1]
        request_info = self.requests.pop(rq, None)

        if cmd == "REGISTERED" and request_info is not None:
            if request_info["type"] == "register":
                name = request_info["name"]
                role = request_info["role"]
                tcp_port = request_info["tcp_port"]
                self.open_user_window(name, role, tcp_port)

        elif cmd == "REGISTER-DENIED":
            # Handle register failure if needed.
            pass

        elif cmd == "LOGIN_OK" and request_info is not None:
            if request_info["type"] == "login":
                name = request_info["name"]
                role = request_info["role"]
                tcp_port = str(random.randint(40001, 50000))
                self.open_user_window(name, role, tcp_port)

        elif cmd == "LOGIN_FAIL":
            pass

        elif cmd == "DE-REGISTERED" and request_info is not None:
            if request_info["type"] == "deregister":
                name = request_info["name"]
                user_window = request_info["window"]
                user_window.add_log("De-registered successfully. Closing window.")
                user_window.close_window()
                if name in self.user_windows:
                    del self.user_windows[name]

        elif cmd == "ITEM_LISTED" and request_info is not None:
            if request_info["type"] == "list_item":
                item_name = request_info["item_name"]
                user_window = request_info["window"]
                user_window.add_log(f"Item '{item_name}' listed successfully.")
                user_window.add_my_item(item_name)

        elif cmd == "LIST-DENIED" and request_info is not None:
            if request_info["type"] == "list_item":
                reason = " ".join(parts[2:]) if len(parts) > 2 else "UnknownReason"
                user_window = request_info["window"]
                user_window.add_log(f"Item listing denied: {reason}")

    def open_user_window(self, name, role, tcp_port):
        if name in self.user_windows:
            self.user_windows[name].close_window()
            del self.user_windows[name]

        uw = UserWindow(master_app=self, name=name, role=role, udp_port=self.local_udp_port, tcp_port=tcp_port)
        self.user_windows[name] = uw
        uw.add_log(f"Welcome {name} ({role})! Registered/Login success.")

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ClientApp()
    app.mainloop()

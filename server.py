import customtkinter as ctk
import socket
import threading
import json
import os

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000
MAX_USERS = 4

USERS_DATA_FILE = "users_data.json"
ITEMS_DATA_FILE = "items_data.json"

# ----------------------------
# Data Structures in Memory
# ----------------------------
active_registrations = []  # List of dicts: {"name":..., "role":..., "ip":..., "udp_port":..., "tcp_port":...}
listed_items = []          # List of dicts: {"seller_name":..., "item_name":..., "description":..., "start_price":..., "duration":...}

# ----------------------------
# Persistence Functions
# ----------------------------
def load_users():
    global active_registrations
    if os.path.exists(USERS_DATA_FILE):
        try:
            with open(USERS_DATA_FILE, "r") as f:
                active_registrations = json.load(f)
        except:
            active_registrations = []

def save_users():
    with open(USERS_DATA_FILE, "w") as f:
        json.dump(active_registrations, f, indent=2)

def load_items():
    global listed_items
    if os.path.exists(ITEMS_DATA_FILE):
        try:
            with open(ITEMS_DATA_FILE, "r") as f:
                listed_items = json.load(f)
        except:
            listed_items = []

def save_items():
    with open(ITEMS_DATA_FILE, "w") as f:
        json.dump(listed_items, f, indent=2)

# ----------------------------
# Server Application Class
# ----------------------------
class ServerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Server UI")
        self.geometry("700x500")
        self.resizable(False, False)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.log_text = ctk.CTkTextbox(main_frame, width=680, height=140)
        self.log_text.pack(pady=5)

        container_frame = ctk.CTkFrame(main_frame)
        container_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Active Users Frame
        users_frame = ctk.CTkFrame(container_frame)
        users_frame.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(users_frame, text="Active Users (Max 4)").pack()
        self.active_users_list = ctk.CTkScrollableFrame(users_frame, width=300, height=250)
        self.active_users_list.pack(pady=5, fill="both", expand=True)

        # Listed Items Frame
        items_frame = ctk.CTkFrame(container_frame)
        items_frame.pack(side="right", fill="both", expand=True, padx=5)
        ctk.CTkLabel(items_frame, text="Listed Items").pack()
        self.listed_items_list = ctk.CTkScrollableFrame(items_frame, width=300, height=250)
        self.listed_items_list.pack(pady=5, fill="both", expand=True)

        load_users()
        load_items()
        self.refresh_active_list()
        self.refresh_items_list()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SERVER_IP, SERVER_PORT))
        self.add_log(f"Server listening on {SERVER_IP}:{SERVER_PORT}")

        threading.Thread(target=self.listen_udp, daemon=True).start()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        save_users()
        save_items()
        self.destroy()

    def add_log(self, message: str):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def refresh_active_list(self):
        for widget in self.active_users_list.winfo_children():
            widget.destroy()
        for reg in active_registrations:
            frame = ctk.CTkFrame(self.active_users_list)
            frame.pack(fill="x", pady=2)
            text = f"{reg['name']} ({reg['role']})  UDP:{reg['udp_port']}  TCP:{reg['tcp_port']}"
            ctk.CTkLabel(frame, text=text).pack(side="left", padx=5)

    def refresh_items_list(self):
        for widget in self.listed_items_list.winfo_children():
            widget.destroy()
        for item in listed_items:
            frame = ctk.CTkFrame(self.listed_items_list)
            frame.pack(fill="x", pady=2)
            text = (f"{item['item_name']} by {item['seller_name']} | Price: {item['start_price']} | "
                    f"Duration: {item['duration']}")
            ctk.CTkLabel(frame, text=text).pack(side="left", padx=5)

    def listen_udp(self):
        while True:
            data, addr = self.sock.recvfrom(1024)
            message = data.decode()
            self.add_log(f"Received from {addr}: {message}")
            parts = message.split()
            if len(parts) < 2:
                continue
            cmd = parts[0].upper()
            rq = parts[1]

            if cmd == "REGISTER" and len(parts) >= 7:
                name = parts[2]
                role = parts[3]
                ip = parts[4]
                udp_port = parts[5]
                tcp_port = parts[6]
                self.handle_register(rq, name, role, ip, udp_port, tcp_port, addr)

            elif cmd == "LOGIN" and len(parts) >= 4:
                name = parts[2]
                role = parts[3]
                self.handle_login(rq, name, role, addr)

            elif cmd == "DE-REGISTER" and len(parts) >= 3:
                name = parts[2]
                self.handle_deregister(rq, name, addr)

            elif cmd == "LIST_ITEM" and len(parts) >= 7:
                # LIST_ITEM RQ# userName itemName itemDesc startPrice duration
                user_name = parts[2]
                item_name = parts[3]
                item_desc = parts[4]
                start_price = parts[5]
                duration = parts[6]
                self.handle_list_item(rq, user_name, item_name, item_desc, start_price, duration, addr)

    def handle_register(self, rq, name, role, ip, udp_port, tcp_port, addr):
        for user in active_registrations:
            if user["name"] == name:
                resp = f"REGISTER-DENIED {rq} NameInUse"
                self.sock.sendto(resp.encode(), addr)
                self.add_log(f"Denied registration (duplicate name): {name}")
                return
        if len(active_registrations) >= MAX_USERS:
            resp = f"REGISTER-DENIED {rq} ServerFull"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("Denied registration (server full).")
            return
        new_user = {"name": name, "role": role, "ip": ip, "udp_port": udp_port, "tcp_port": tcp_port}
        active_registrations.append(new_user)
        save_users()
        self.refresh_active_list()
        resp = f"REGISTERED {rq}"
        self.sock.sendto(resp.encode(), addr)
        self.add_log(f"Registered new user: {name} ({role})")

    def handle_login(self, rq, name, role, addr):
        found = False
        for user in active_registrations:
            if user["name"] == name and user["role"] == role:
                found = True
                break
        if found:
            resp = f"LOGIN_OK {rq}"
            self.sock.sendto(resp.encode(), addr)
            self.add_log(f"Login success for {name} ({role})")
        else:
            resp = f"LOGIN_FAIL {rq} NotFound"
            self.sock.sendto(resp.encode(), addr)
            self.add_log(f"Login fail for {name} ({role})")

    def handle_deregister(self, rq, name, addr):
        removed = False
        for user in active_registrations:
            if user["name"] == name:
                active_registrations.remove(user)
                removed = True
                break
        resp = f"DE-REGISTERED {rq}"
        self.sock.sendto(resp.encode(), addr)
        if removed:
            save_users()
            self.refresh_active_list()
            self.add_log(f"De-registered user: {name}")
        else:
            self.add_log(f"De-register requested but user not found: {name}")

    def handle_list_item(self, rq, user_name, item_name, item_desc, start_price, duration, addr):
        user = None
        for u in active_registrations:
            if u["name"] == user_name:
                user = u
                break
        if user is None:
            resp = f"LIST-DENIED {rq} UserNotFound"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("LIST_ITEM denied (username not found).")
            return
        if user["role"].lower() != "seller":
            resp = f"LIST-DENIED {rq} NotSeller"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("LIST_ITEM denied (user not a seller).")
            return
        new_item = {
            "seller_name": user["name"],
            "item_name": item_name,
            "description": item_desc,
            "start_price": start_price,
            "duration": duration
        }
        listed_items.append(new_item)
        save_items()
        self.refresh_items_list()
        resp = f"ITEM_LISTED {rq}"
        self.sock.sendto(resp.encode(), addr)
        self.add_log(f"Item listed: {item_name} by {user['name']}")

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ServerApp()
    app.mainloop()

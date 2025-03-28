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
active_registrations = []  # [{"name":..., "role":..., "ip":..., "udp_port":..., "tcp_port":...}]
listed_items = []          # [{"seller_name":..., "item_name":..., "description":..., "start_price":..., "duration":...}]

# ----------------------------
# Persistence
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
                # Ensure duration and price are of proper types
                for item in listed_items:
                    item["duration"] = int(item["duration"])
                    item["start_price"] = float(item["start_price"])
        except:
            listed_items = []

def save_items():
    with open(ITEMS_DATA_FILE, "w") as f:
        json.dump(listed_items, f, indent=2)

# ----------------------------
# ServerApp
# ----------------------------
class ServerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Server UI")
        self.geometry("700x500")
        self.resizable(False, False)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Log area (read-only)
        self.log_text = ctk.CTkTextbox(main_frame, width=680, height=140, state="disabled")
        self.log_text.pack(pady=5)

        # Two scrollable frames: Active Users and Listed Items
        container_frame = ctk.CTkFrame(main_frame)
        container_frame.pack(fill="both", expand=True, padx=5, pady=5)

        users_frame = ctk.CTkFrame(container_frame)
        users_frame.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(users_frame, text="Active Users (Max 4)").pack()
        self.active_users_list = ctk.CTkScrollableFrame(users_frame, width=300, height=250)
        self.active_users_list.pack(pady=5, fill="both", expand=True)

        items_frame = ctk.CTkFrame(container_frame)
        items_frame.pack(side="right", fill="both", expand=True, padx=5)
        ctk.CTkLabel(items_frame, text="Listed Items").pack()
        self.listed_items_list = ctk.CTkScrollableFrame(items_frame, width=300, height=250)
        self.listed_items_list.pack(pady=5, fill="both", expand=True)

        # Load existing data
        load_users()
        load_items()
        self.refresh_active_list()
        self.refresh_items_list()

        # Create the UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SERVER_IP, SERVER_PORT))
        self.add_log(f"(UDP) Server listening on {SERVER_IP}:{SERVER_PORT}")

        threading.Thread(target=self.listen_udp, daemon=True).start()
        # Start the countdown updater
        self.update_items_countdown()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        save_users()
        save_items()
        self.destroy()

    def add_log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def refresh_active_list(self):
        for widget in self.active_users_list.winfo_children():
            widget.destroy()
        for user in active_registrations:
            frame = ctk.CTkFrame(self.active_users_list)
            frame.pack(fill="x", pady=2)
            text = f"{user['name']} ({user['role']})  UDP:{user['udp_port']}  TCP:{user['tcp_port']}"
            ctk.CTkLabel(frame, text=text).pack(side="left", padx=5)

    def refresh_items_list(self):
        for widget in self.listed_items_list.winfo_children():
            widget.destroy()
        for item in listed_items:
            frame = ctk.CTkFrame(self.listed_items_list)
            frame.pack(fill="x", pady=2)
            text = (f"{item['item_name']} by {item['seller_name']} | "
                    f"Price: {item['start_price']} | Duration: {item['duration']}s")
            ctk.CTkLabel(frame, text=text).pack(side="left", padx=5)

    def update_items_countdown(self):
        """Decrement duration for each listed item every second, remove expired items, and refresh UI."""
        changed = False
        for item in listed_items[:]:
            # Decrement duration
            try:
                item["duration"] = int(item["duration"])
            except:
                continue
            item["duration"] -= 1
            if item["duration"] <= 0:
                listed_items.remove(item)
                changed = True
        # Always refresh the listed items display to show updated countdowns
        self.refresh_items_list()
        if changed:
            save_items()
        self.after(1000, self.update_items_countdown)

    def listen_udp(self):
        while True:
            data, addr = self.sock.recvfrom(1024)
            message = data.decode()
            self.add_log(f"(UDP) Received from {addr}: {message}")
            parts = message.split()
            if len(parts) < 2:
                continue

            cmd = parts[0].upper()
            rq = parts[1]

            if cmd == "REGISTER" and len(parts) >= 7:
                # REGISTER RQ# Name Role IP UDP_port TCP_port
                name = parts[2]
                role = parts[3]
                ip = parts[4]
                udp_port = parts[5]
                tcp_port = parts[6]
                self.handle_register(rq, name, role, ip, udp_port, tcp_port, addr)

            elif cmd == "LOGIN" and len(parts) >= 4:
                # LOGIN RQ# Name Role
                name = parts[2]
                role = parts[3]
                self.handle_login(rq, name, role, addr)

            elif cmd == "DE-REGISTER" and len(parts) >= 3:
                # DE-REGISTER RQ# Name
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

    # ---------------------------------------------------------------------
    # Handlers
    # ---------------------------------------------------------------------

    def handle_register(self, rq, name, role, ip, udp_port, tcp_port, addr):
        # Check duplicates
        for user in active_registrations:
            if user["name"] == name:
                resp = f"REGISTER-DENIED {rq} NameInUse"
                self.sock.sendto(resp.encode(), addr)
                self.add_log(f"(UDP) Denied registration (duplicate name): {name}")
                return
        # Check capacity
        if len(active_registrations) >= MAX_USERS:
            resp = f"REGISTER-DENIED {rq} ServerFull"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("(UDP) Denied registration (server full).")
            return

        # Accept
        new_user = {
            "name": name,
            "role": role,
            "ip": ip,
            "udp_port": udp_port,
            "tcp_port": tcp_port
        }
        active_registrations.append(new_user)
        save_users()
        self.refresh_active_list()
        resp = f"REGISTERED {rq}"
        self.sock.sendto(resp.encode(), addr)
        self.add_log(f"(UDP) Registered new user: {name} ({role})")

    def handle_login(self, rq, name, role, addr):
        found_user = None
        for user in active_registrations:
            if user["name"] == name and user["role"] == role:
                found_user = user
                break
        if found_user:
            resp = f"LOGIN_OK {rq}"
            self.sock.sendto(resp.encode(), addr)
            self.add_log(f"(UDP) Login success for {name} ({role})")
            # After login success, send user items so they see previously listed items
            self.send_user_items(rq, found_user, addr)
        else:
            resp = f"LOGIN_FAIL {rq} NotFound"
            self.sock.sendto(resp.encode(), addr)
            self.add_log(f"(UDP) Login fail for {name} ({role})")

    def send_user_items(self, rq, user, addr):
        """Send the user all their previously listed items."""
        user_name = user["name"]
        # Filter items by seller_name == user_name
        user_list = [i for i in listed_items if i["seller_name"] == user_name]
        count = len(user_list)
        # Format: ITEMS RQ# userName count itemName startPrice duration itemName startPrice duration...
        parts = ["ITEMS", rq, user_name, str(count)]
        for it in user_list:
            parts.append(it["item_name"])
            parts.append(str(it["start_price"]))
            parts.append(str(it["duration"]))
        msg = " ".join(parts)
        self.sock.sendto(msg.encode(), addr)
        self.add_log(f"(UDP) Sent user items for {user_name}, total {count} item(s).")

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
            self.add_log(f"(UDP) De-registered user: {name}")
        else:
            self.add_log(f"(UDP) De-register requested but user not found: {name}")

    def handle_list_item(self, rq, user_name, item_name, item_desc, start_price, duration, addr):
        # Find user by name
        user = None
        for u in active_registrations:
            if u["name"] == user_name:
                user = u
                break
        if user is None:
            resp = f"LIST-DENIED {rq} UserNotFound"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("(UDP) LIST_ITEM denied (username not found).")
            return

        if user["role"].lower() != "seller":
            resp = f"LIST-DENIED {rq} NotSeller"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("(UDP) LIST_ITEM denied (user not a seller).")
            return

        # Validate the input:
        # - item_name must be a non-empty string that is not purely numeric.
        if not item_name or item_name.isdigit():
            resp = f"LIST-DENIED {rq} InvalidName"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("(UDP) LIST_ITEM denied (invalid name).")
            return
        try:
            price = float(start_price)
        except:
            resp = f"LIST-DENIED {rq} InvalidPrice"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("(UDP) LIST_ITEM denied (invalid price).")
            return
        try:
            dur = int(duration)
        except:
            resp = f"LIST-DENIED {rq} InvalidDuration"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("(UDP) LIST_ITEM denied (invalid duration).")
            return

        # Check how many items this user already has
        user_items_count = sum(1 for i in listed_items if i["seller_name"] == user_name)
        if user_items_count >= 4:
            resp = f"LIST-DENIED {rq} SellerAtCapacity"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("(UDP) LIST_ITEM denied (seller at capacity).")
            return

        # Accept the listing
        new_item = {
            "seller_name": user["name"],
            "item_name": item_name,
            "description": item_desc,
            "start_price": price,
            "duration": dur
        }
        listed_items.append(new_item)
        save_items()
        self.refresh_items_list()
        resp = f"ITEM_LISTED {rq}"
        self.sock.sendto(resp.encode(), addr)
        self.add_log(f"(UDP) Item listed: {item_name} by {user['name']}")

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ServerApp()
    app.mainloop()

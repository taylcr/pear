import customtkinter as ctk
import socket
import threading
import json
import os
import random
import time

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000
MAX_USERS = 4

USERS_DATA_FILE = "users_data.json"
ITEMS_DATA_FILE = "items_data.json"
SUBSCRIPTIONS_DATA_FILE = "subscriptions_data.json"

# ----------------------------
# Data Structures in Memory
# ----------------------------
active_registrations = []  # [ { "name":..., "role":..., "ip":..., "udp_port":..., "tcp_port":... } ]
listed_items = []          # [ { "item_id":..., "seller_name":..., "item_name":..., "description":..., "start_price":..., "duration":... } ]
subscriptions = []         # [ { "buyer_name":..., "item_name":... } ]

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
                loaded = json.load(f)
                for item in loaded:
                    # Ensure fields are correct types
                    item["item_id"] = item.get("item_id", str(random.randint(10000,99999)))
                    item["start_price"] = float(item["start_price"])
                    item["duration"] = int(item["duration"])
                listed_items = loaded
        except:
            listed_items = []

def save_items():
    with open(ITEMS_DATA_FILE, "w") as f:
        json.dump(listed_items, f, indent=2)

def load_subscriptions():
    global subscriptions
    if os.path.exists(SUBSCRIPTIONS_DATA_FILE):
        try:
            with open(SUBSCRIPTIONS_DATA_FILE, "r") as f:
                subscriptions = json.load(f)
        except:
            subscriptions = []

def save_subscriptions():
    with open(SUBSCRIPTIONS_DATA_FILE, "w") as f:
        json.dump(subscriptions, f, indent=2)

# ----------------------------
# ServerApp
# ----------------------------
class ServerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Server UI")
        self.geometry("900x600")
        self.resizable(False, False)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Log area (read-only)
        self.log_text = ctk.CTkTextbox(main_frame, width=880, height=150, state="disabled")
        self.log_text.pack(pady=5)

        # Three scrollable frames: Active Users, Listed Items, Subscriptions
        container_frame = ctk.CTkFrame(main_frame)
        container_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Active Users
        users_frame = ctk.CTkFrame(container_frame)
        users_frame.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(users_frame, text="Active Users (Max 4)").pack()
        self.active_users_list = ctk.CTkScrollableFrame(users_frame, width=250, height=300)
        self.active_users_list.pack(pady=5, fill="both", expand=True)

        # Listed Items (wider)
        items_frame = ctk.CTkFrame(container_frame)
        items_frame.pack(side="left", fill="both", expand=True, padx=5)
        ctk.CTkLabel(items_frame, text="Listed Items").pack()
        self.listed_items_list = ctk.CTkScrollableFrame(items_frame, width=350, height=300)
        self.listed_items_list.pack(pady=5, fill="both", expand=True)

        # Subscriptions
        subs_frame = ctk.CTkFrame(container_frame)
        subs_frame.pack(side="right", fill="both", expand=True, padx=5)
        ctk.CTkLabel(subs_frame, text="Subscriptions (Buyer -> Item)").pack()
        self.subscriptions_list = ctk.CTkScrollableFrame(subs_frame, width=250, height=300)
        self.subscriptions_list.pack(pady=5, fill="both", expand=True)

        # Load data
        load_users()
        load_items()
        load_subscriptions()

        self.refresh_active_list()
        self.refresh_items_list()
        self.refresh_subscriptions_list()

        # Create the UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SERVER_IP, SERVER_PORT))
        self.add_log(f"(UDP) Server listening on {SERVER_IP}:{SERVER_PORT}")

        # Start listening, item countdown, and announcements
        threading.Thread(target=self.listen_udp, daemon=True).start()
        self.update_items_countdown()
        self.start_announcement_publisher()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        save_users()
        save_items()
        save_subscriptions()
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
            text = (f"ID:{item['item_id']} | {item['item_name']} by {item['seller_name']} | "
                    f"Price: {item['start_price']} | TimeLeft: {item['duration']}")
            ctk.CTkLabel(frame, text=text).pack(side="left", padx=5)

    def refresh_subscriptions_list(self):
        for widget in self.subscriptions_list.winfo_children():
            widget.destroy()
        for sub in subscriptions:
            frame = ctk.CTkFrame(self.subscriptions_list)
            frame.pack(fill="x", pady=2)
            text = f"{sub['buyer_name']} -> {sub['item_name']}"
            ctk.CTkLabel(frame, text=text).pack(side="left", padx=5)

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
                self.handle_register(rq, parts[2], parts[3], parts[4], parts[5], parts[6], addr)
            elif cmd == "LOGIN" and len(parts) >= 4:
                self.handle_login(rq, parts[2], parts[3], addr)
            elif cmd == "DE-REGISTER" and len(parts) >= 3:
                self.handle_deregister(rq, parts[2], addr)
            elif cmd == "LIST_ITEM" and len(parts) >= 7:
                self.handle_list_item(rq, parts[2], parts[3], parts[4], parts[5], parts[6], addr)
            elif cmd == "SUBSCRIBE" and len(parts) >= 4:
                self.handle_subscribe(rq, parts[2], parts[3], addr)
            elif cmd == "DE-SUBSCRIBE" and len(parts) >= 4:
                self.handle_de_subscribe(rq, parts[2], parts[3], addr)

    # ----- Handlers -----

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
        else:
            resp = f"LOGIN_FAIL {rq} NotFound"
            self.sock.sendto(resp.encode(), addr)
            self.add_log(f"(UDP) Login fail for {name} ({role})")

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

        # Validate
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

        # Check capacity
        user_items_count = sum(1 for i in listed_items if i["seller_name"] == user_name)
        if user_items_count >= 4:
            resp = f"LIST-DENIED {rq} SellerAtCapacity"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("(UDP) LIST_ITEM denied (seller at capacity).")
            return

        new_id = str(random.randint(10000,99999))
        new_item = {
            "item_id": new_id,
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

    def handle_subscribe(self, rq, buyer_name, item_name, addr):
        buyer = None
        for user in active_registrations:
            if user["name"] == buyer_name:
                buyer = user
                break
        if not buyer or buyer["role"].lower() != "buyer":
            resp = f"SUBSCRIPTION-DENIED {rq} NotBuyerOrNotFound"
            self.sock.sendto(resp.encode(), addr)
            self.add_log(f"(UDP) SUBSCRIBE denied for {buyer_name}, not a buyer or not found.")
            return

        # Already subscribed?
        already = any((sub["buyer_name"] == buyer_name and sub["item_name"] == item_name) for sub in subscriptions)
        if already:
            resp = f"SUBSCRIPTION-DENIED {rq} AlreadySubscribed"
            self.sock.sendto(resp.encode(), addr)
            self.add_log(f"(UDP) SUBSCRIBE denied, already subscribed: {buyer_name} -> {item_name}")
            return

        new_sub = { "buyer_name": buyer_name, "item_name": item_name }
        subscriptions.append(new_sub)
        save_subscriptions()
        self.refresh_subscriptions_list()

        resp = f"SUBSCRIBED {rq}"
        self.sock.sendto(resp.encode(), addr)
        self.add_log(f"(UDP) SUBSCRIBE success: {buyer_name} -> {item_name}")

    def handle_de_subscribe(self, rq, buyer_name, item_name, addr):
        found = None
        for sub in subscriptions:
            if sub["buyer_name"] == buyer_name and sub["item_name"] == item_name:
                found = sub
                break
        if not found:
            resp = f"SUBSCRIPTION-DENIED {rq} NoSubscription"
            self.sock.sendto(resp.encode(), addr)
            self.add_log(f"(UDP) DE-SUBSCRIBE denied, not subscribed: {buyer_name} -> {item_name}")
            return

        subscriptions.remove(found)
        save_subscriptions()
        self.refresh_subscriptions_list()

        resp = f"SUBSCRIBED {rq}"
        self.sock.sendto(resp.encode(), addr)
        self.add_log(f"(UDP) DE-SUBSCRIBE success: {buyer_name} -> {item_name}")

    # ----- Background tasks -----

    def update_items_countdown(self):
        changed = False
        for item in listed_items[:]:
            item["duration"] = max(0, int(item["duration"]) - 1)
            if item["duration"] <= 0:
                listed_items.remove(item)
                changed = True
        if changed:
            save_items()
        self.refresh_items_list()
        self.after(1000, self.update_items_countdown)

    def start_announcement_publisher(self):
        t = threading.Thread(target=self.publish_announcements_loop, daemon=True)
        t.start()

    def publish_announcements_loop(self):
        while True:
            # For each listed item, find all buyers subscribed to item["item_name"]
            for item in listed_items:
                subs_for_item = [s for s in subscriptions if s["item_name"] == item["item_name"]]
                for s in subs_for_item:
                    buyer_reg = next((b for b in active_registrations if b["name"] == s["buyer_name"]), None)
                    if not buyer_reg:
                        continue
                    # Build announcement
                    msg = (f"AUCTION_ANNOUNCE {item['item_id']} {item['item_name']} "
                           f"{item['description']} {item['start_price']} {item['duration']}")
                    self.sock.sendto(msg.encode(), (buyer_reg["ip"], int(buyer_reg["udp_port"])))
            time.sleep(5)

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ServerApp()
    app.mainloop()

import customtkinter as ctk
import socket
import threading
import random
import subprocess
import sys
import os

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000

# ----------------------------------------------------------------------
# BuyerSubscriptionFrame: handles "subscribe/unsubscribe" to item names
# ----------------------------------------------------------------------
class BuyerSubscriptionFrame(ctk.CTkFrame):
    """
    For buyers:
    - Input to type an item name
    - Subscribe button
    - Scrollable list of subscribed items with Unsubscribe buttons
    """
    def __init__(self, master, user_window):
        super().__init__(master)
        self.user_window = user_window
        self.subscribed_items = []

        top_frame = ctk.CTkFrame(self)
        top_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(top_frame, text="Item to Subscribe:").pack(side="left", padx=5)
        self.item_name_var = ctk.StringVar()
        self.item_name_entry = ctk.CTkEntry(top_frame, textvariable=self.item_name_var, width=120)
        self.item_name_entry.pack(side="left", padx=5)

        self.subscribe_btn = ctk.CTkButton(top_frame, text="Subscribe", command=self.subscribe_item)
        self.subscribe_btn.pack(side="left", padx=5)

        # Subscribed items list
        self.list_frame = ctk.CTkScrollableFrame(self, width=300, height=100)
        self.list_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self.refresh_subscribed_list()

    def subscribe_item(self):
        item_name = self.item_name_var.get().strip()
        if not item_name:
            self.user_window.add_log("ERROR: Please enter an item name to subscribe.")
            return
        self.user_window.send_subscribe(item_name)

    def add_subscription(self, item_name):
        if item_name not in self.subscribed_items:
            self.subscribed_items.append(item_name)
            self.refresh_subscribed_list()

    def remove_subscription(self, item_name):
        if item_name in self.subscribed_items:
            self.subscribed_items.remove(item_name)
            self.refresh_subscribed_list()

    def refresh_subscribed_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()
        for itm in self.subscribed_items:
            row_frame = ctk.CTkFrame(self.list_frame)
            row_frame.pack(fill="x", pady=2)
            ctk.CTkLabel(row_frame, text=itm).pack(side="left", padx=5)

            def unsub_callback(name=itm):
                return lambda: self.user_window.send_de_subscribe(name)
            unsub_btn = ctk.CTkButton(row_frame, text="Unsubscribe", command=unsub_callback())
            unsub_btn.pack(side="right", padx=5)

# ----------------------------------------------------------------------
# BuyerSubscribedAnnouncementsFrame: displays "AUCTION_ANNOUNCE" items
# ----------------------------------------------------------------------
class BuyerSubscribedAnnouncementsFrame(ctk.CTkFrame):
    """
    Shows each AUCTION_ANNOUNCE as a row:
    RQ# item_id | item_name | description | Price: X | TimeLeft: Y
    """
    def __init__(self, master, user_window):
        super().__init__(master)
        self.user_window = user_window

        # If we want to update existing items by item_id, store them here
        self.announced_items = {}

        ctk.CTkLabel(self, text="Subscribed Items Announcements:").pack(anchor="w", padx=5, pady=2)
        self.list_frame = ctk.CTkScrollableFrame(self, width=300, height=150)
        self.list_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def update_announcement(self, item_id, item_name, description, current_price, time_left):
        """
        If the item_id is already displayed, remove or update it.
        Then create a new row or refresh existing.
        """
        # If you want to remove the old row each time:
        if item_id in self.announced_items:
            old_frame = self.announced_items[item_id]
            old_frame.destroy()

        row_frame = ctk.CTkFrame(self.list_frame)
        row_frame.pack(fill="x", pady=2)

        text = (f"RQ# {item_id} | {item_name} | {description} "
                f"| Price: {current_price} | TimeLeft: {time_left}")
        ctk.CTkLabel(row_frame, text=text).pack(side="left", padx=5)

        self.announced_items[item_id] = row_frame

# ----------------------------------------------------------------------
# ListItemWindow: pop-up for sellers to list items
# ----------------------------------------------------------------------
class ListItemWindow(ctk.CTkToplevel):
    def __init__(self, user_window):
        super().__init__()
        self.user_window = user_window
        self.title("List an Item for Auction")
        self.geometry("300x320")
        self.resizable(False, False)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(main_frame, text="Item Name:").pack(anchor="w")
        self.item_name_var = ctk.StringVar()
        self.item_name_entry = ctk.CTkEntry(main_frame, textvariable=self.item_name_var)
        self.item_name_entry.pack(pady=5, fill="x")

        ctk.CTkLabel(main_frame, text="Description:").pack(anchor="w")
        self.item_desc_var = ctk.StringVar()
        self.item_desc_entry = ctk.CTkEntry(main_frame, textvariable=self.item_desc_var)
        self.item_desc_entry.pack(pady=5, fill="x")

        ctk.CTkLabel(main_frame, text="Start Price:").pack(anchor="w")
        self.start_price_var = ctk.StringVar()
        self.start_price_entry = ctk.CTkEntry(main_frame, textvariable=self.start_price_var)
        self.start_price_entry.pack(pady=5, fill="x")

        ctk.CTkLabel(main_frame, text="Duration (in seconds):").pack(anchor="w")
        self.duration_var = ctk.StringVar()
        self.duration_entry = ctk.CTkEntry(main_frame, textvariable=self.duration_var)
        self.duration_entry.pack(pady=5, fill="x")

        self.submit_btn = ctk.CTkButton(main_frame, text="List Item", command=self.submit_item)
        self.submit_btn.pack(pady=10)

    def submit_item(self):
        item_name = self.item_name_var.get().strip()
        item_desc = self.item_desc_var.get().strip()
        start_price = self.start_price_var.get().strip()
        duration = self.duration_var.get().strip()

        if not item_name or not start_price or not duration:
            self.user_window.add_log("ERROR: Please fill out all required fields.")
            return
        if item_name.isdigit():
            self.user_window.add_log("ERROR: Item name must contain letters.")
            return
        try:
            float(start_price)
        except:
            self.user_window.add_log("ERROR: Start Price must be a number.")
            return
        try:
            int(duration)
        except:
            self.user_window.add_log("ERROR: Duration must be an integer.")
            return

        self.user_window.send_list_item(item_name, item_desc, start_price, duration)
        self.destroy()

# ----------------------------------------------------------------------
# UserWindow: opened for each registered/logged-in user
# ----------------------------------------------------------------------
class UserWindow(ctk.CTkToplevel):
    def __init__(self, master_app, name, role, udp_port, tcp_port):
        super().__init__()
        self.master_app = master_app
        self.name = name
        self.role = role
        self.udp_port = udp_port
        self.tcp_port = tcp_port

        self.title(f"User: {self.name}")
        self.geometry("500x500")
        self.resizable(False, False)

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        info_text = (
            f"Name: {self.name}\n"
            f"Role: {self.role}\n"
            f"UDP Port: {self.udp_port}\n"
            f"TCP Port: {self.tcp_port}"
        )
        ctk.CTkLabel(main_frame, text=info_text).pack(pady=5)

        self.dereg_button = ctk.CTkButton(main_frame, text="De-register", command=self.request_deregister)
        self.dereg_button.pack(pady=5)

        # Log area (read-only)
        self.log_text = ctk.CTkTextbox(main_frame, width=360, height=80, state="disabled")
        self.log_text.pack(pady=5)

        if self.role.lower() == "seller":
            # Seller UI
            self.list_item_button = ctk.CTkButton(main_frame, text="List Item", command=self.open_list_item_window)
            self.list_item_button.pack(pady=5)

            ctk.CTkLabel(main_frame, text="Your Listed Items:").pack(anchor="w")
            self.my_items_frame = ctk.CTkScrollableFrame(main_frame, width=360, height=100)
            self.my_items_frame.pack(pady=5, fill="both", expand=True)

            self.my_items = []
            self.update_countdown()
        else:
            # Buyer UI
            self.subscription_frame = BuyerSubscriptionFrame(main_frame, self)
            self.subscription_frame.pack(fill="x", padx=5, pady=5)

            # The new announcements area
            self.subscribed_announcements_frame = BuyerSubscribedAnnouncementsFrame(main_frame, self)
            self.subscribed_announcements_frame.pack(fill="both", expand=True, padx=5, pady=5)

    # --- Common functions ---
    def add_log(self, message: str):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def request_deregister(self):
        self.master_app.send_deregister(self.name, self)

    def close_window(self):
        self.destroy()

    # --- Seller functions ---
    def open_list_item_window(self):
        ListItemWindow(self)

    def send_list_item(self, item_name, item_desc, start_price, duration):
        self.master_app.send_list_item(self.name, item_name, item_desc, start_price, duration, self)
        self.add_log(f"Sent LIST_ITEM for item '{item_name}'.")

    def add_my_item(self, item_name, start_price, duration):
        try:
            duration = int(duration)
        except:
            duration = 0
        self.my_items.append({
            "item_name": item_name,
            "start_price": start_price,
            "duration": duration
        })
        self.update_my_items_list()

    def update_my_items_list(self):
        if not self.my_items_frame:
            return
        for widget in self.my_items_frame.winfo_children():
            widget.destroy()
        for item in self.my_items:
            text = f"{item['item_name']} | Price: {item['start_price']} | Duration: {item['duration']}s"
            ctk.CTkLabel(self.my_items_frame, text=text).pack(anchor="w", padx=5, pady=2)

    def update_countdown(self):
        for item in self.my_items[:]:
            if item["duration"] > 0:
                item["duration"] -= 1
            if item["duration"] <= 0:
                self.my_items.remove(item)
        self.update_my_items_list()
        self.after(1000, self.update_countdown)

    # --- Buyer functions ---
    def send_subscribe(self, item_name):
        self.master_app.send_subscribe(self.name, item_name)

    def send_de_subscribe(self, item_name):
        self.master_app.send_de_subscribe(self.name, item_name)

    def add_subscription(self, item_name):
        # add to the subscription frame's list
        if hasattr(self, "subscription_frame"):
            self.subscription_frame.add_subscription(item_name)

    def remove_subscription(self, item_name):
        if hasattr(self, "subscription_frame"):
            self.subscription_frame.remove_subscription(item_name)

    def add_subscribed_announcement(self, item_id, item_name, description, current_price, time_left):
        """
        Called by client when an AUCTION_ANNOUNCE arrives. We forward it
        to the 'BuyerSubscribedAnnouncementsFrame'.
        """
        if hasattr(self, "subscribed_announcements_frame"):
            self.subscribed_announcements_frame.update_announcement(
                item_id, item_name, description, current_price, time_left
            )

# ----------------------------------------------------------------------
# ClientApp
# ----------------------------------------------------------------------
class ClientApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Client Main Page")
        self.geometry("500x300")
        self.resizable(False, False)

        # Launch server.py automatically (optional)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        server_script = os.path.join(script_dir, "server.py")
        self.server_process = subprocess.Popen([sys.executable, server_script])

        # Create a UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SERVER_IP, 0))
        self.local_udp_port = self.sock.getsockname()[1]

        self.requests = {}      # in-flight requests
        self.user_windows = {}  # name -> UserWindow

        self.listening = True
        threading.Thread(target=self.listen_server, daemon=True).start()

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

        self.log_text = ctk.CTkTextbox(main_frame, width=450, height=80, state="disabled")
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
        self.log_text.configure(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # ----- Sending (UDP) -----
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
        self.add_log(f"(UDP) Sent REGISTER (RQ={rq}) for {name} ({role}).")

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
        self.add_log(f"(UDP) Sent LOGIN (RQ={rq}) for {name} ({role}).")

    def send_deregister(self, name, user_window):
        rq = str(random.randint(1000, 9999))
        msg = f"DE-REGISTER {rq} {name}"
        self.sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
        self.requests[rq] = {"type": "deregister", "name": name, "window": user_window}
        self.add_log(f"(UDP) Sent DE-REGISTER (RQ={rq}) for {name}.")

    def send_list_item(self, user_name, item_name, item_desc, start_price, duration, user_window):
        rq = str(random.randint(1000, 9999))
        msg = f"LIST_ITEM {rq} {user_name} {item_name} {item_desc} {start_price} {duration}"
        self.sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
        self.requests[rq] = {
            "type": "list_item",
            "user_name": user_name,
            "item_name": item_name,
            "start_price": start_price,
            "duration": duration,
            "window": user_window
        }
        self.add_log(f"(UDP) Sent LIST_ITEM (RQ={rq}) for item '{item_name}'.")

    def send_subscribe(self, buyer_name, item_name):
        rq = str(random.randint(1000, 9999))
        msg = f"SUBSCRIBE {rq} {buyer_name} {item_name}"
        self.sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
        self.requests[rq] = {
            "type": "subscribe",
            "buyer_name": buyer_name,
            "item_name": item_name
        }
        self.add_log(f"(UDP) Sent SUBSCRIBE (RQ={rq}) for {buyer_name} -> {item_name}.")

    def send_de_subscribe(self, buyer_name, item_name):
        rq = str(random.randint(1000, 9999))
        msg = f"DE-SUBSCRIBE {rq} {buyer_name} {item_name}"
        self.sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
        self.requests[rq] = {
            "type": "unsubscribe",
            "buyer_name": buyer_name,
            "item_name": item_name
        }
        self.add_log(f"(UDP) Sent DE-SUBSCRIBE (RQ={rq}) for {buyer_name} -> {item_name}.")

    # ----- Receiving (UDP) -----
    def listen_server(self):
        while self.listening:
            try:
                data, addr = self.sock.recvfrom(2048)
                response = data.decode()
                self.handle_server_response(response)
            except:
                break

    def handle_server_response(self, response: str):
        self.add_log(f"(UDP) Received: {response}")
        parts = response.split()
        if len(parts) < 2:
            return

        cmd = parts[0].upper()
        rq = parts[1]
        request_info = self.requests.pop(rq, None)

        if cmd == "REGISTERED" and request_info:
            if request_info["type"] == "register":
                name = request_info["name"]
                role = request_info["role"]
                tcp_port = request_info["tcp_port"]
                self.open_user_window(name, role, tcp_port)

        elif cmd == "REGISTER-DENIED":
            pass

        elif cmd == "LOGIN_OK" and request_info:
            if request_info["type"] == "login":
                name = request_info["name"]
                role = request_info["role"]
                tcp_port = str(random.randint(40001, 50000))
                self.open_user_window(name, role, tcp_port)

        elif cmd == "LOGIN_FAIL":
            pass

        elif cmd == "DE-REGISTERED" and request_info:
            if request_info["type"] == "deregister":
                name = request_info["name"]
                user_window = request_info["window"]
                user_window.add_log("De-registered successfully. Closing window.")
                user_window.close_window()
                if name in self.user_windows:
                    del self.user_windows[name]

        elif cmd == "ITEM_LISTED" and request_info:
            if request_info["type"] == "list_item":
                item_name = request_info["item_name"]
                start_price = request_info["start_price"]
                duration = request_info["duration"]
                user_window = request_info["window"]
                user_window.add_log(f"Item '{item_name}' listed successfully.")
                user_window.add_my_item(item_name, start_price, duration)

        elif cmd == "LIST-DENIED" and request_info:
            if request_info["type"] == "list_item":
                reason = " ".join(parts[2:]) if len(parts) > 2 else "UnknownReason"
                user_window = request_info["window"]
                user_window.add_log(f"Item listing denied: {reason}")

        elif cmd == "SUBSCRIBED" and request_info:
            # Could be subscribe or unsubscribe
            if request_info["type"] == "subscribe":
                buyer_name = request_info["buyer_name"]
                item_name = request_info["item_name"]
                user_window = self.user_windows.get(buyer_name)
                if user_window:
                    user_window.add_log(f"Subscribed to {item_name} successfully.")
                    user_window.add_subscription(item_name)
            elif request_info["type"] == "unsubscribe":
                buyer_name = request_info["buyer_name"]
                item_name = request_info["item_name"]
                user_window = self.user_windows.get(buyer_name)
                if user_window:
                    user_window.add_log(f"De-subscribed from {item_name} successfully.")
                    user_window.remove_subscription(item_name)

        elif cmd == "SUBSCRIPTION-DENIED" and request_info:
            reason = " ".join(parts[2:]) if len(parts) > 2 else "UnknownReason"
            if request_info["type"] in ["subscribe", "unsubscribe"]:
                buyer_name = request_info["buyer_name"]
                item_name = request_info["item_name"]
                user_window = self.user_windows.get(buyer_name)
                if user_window:
                    user_window.add_log(f"Subscription command denied: {reason}")

        elif cmd == "AUCTION_ANNOUNCE":
            # e.g. AUCTION_ANNOUNCE <item_id> <item_name> <description> <current_price> <time_left>
            if len(parts) < 6:
                return
            item_id = parts[1]
            item_name = parts[2]
            description = parts[3]
            current_price = parts[4]
            time_left = parts[5]

            # Typically the server sends this only to the correct buyer,
            # but we can loop over all buyers if needed:
            for uw in self.user_windows.values():
                if uw.role.lower() == "buyer":
                    uw.add_subscribed_announcement(item_id, item_name, description, current_price, time_left)

    def open_user_window(self, name, role, tcp_port):
        # If a window for this user already exists, close it
        if name in self.user_windows:
            self.user_windows[name].close_window()
            del self.user_windows[name]

        uw = UserWindow(self, name, role, self.local_udp_port, tcp_port)
        self.user_windows[name] = uw
        uw.add_log(f"Welcome {name} ({role})! Registered/Login success.")

if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ClientApp()
    app.mainloop()

import customtkinter as ctk
import socket
import threading
import json
import os

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000
DATA_FILE = "server_data.json"
MAX_USERS = 4

# Store active users in a list of dicts:
# [
#   {"name":..., "role":..., "ip":..., "udp_port":..., "tcp_port":...},
#   ...
# ]
active_registrations = []

def load_data():
    """Load active registrations from JSON file."""
    global active_registrations
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                active_registrations = json.load(f)
        except:
            active_registrations = []

def save_data():
    """Save active registrations to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(active_registrations, f, indent=2)

class ServerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Server UI")
        self.geometry("600x400")
        self.resizable(False, False)

        # Main frame
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Log area
        self.log_text = ctk.CTkTextbox(main_frame, width=580, height=150)
        self.log_text.pack(pady=5)

        # Active users label
        self.active_label = ctk.CTkLabel(main_frame, text="Active Users (Max 4)")
        self.active_label.pack()

        # Scrollable frame for active users
        self.active_list = ctk.CTkScrollableFrame(main_frame, width=580, height=150)
        self.active_list.pack(pady=5, fill="both", expand=True)

        # Load existing data
        load_data()
        self.refresh_active_list()

        # Create and bind UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((SERVER_IP, SERVER_PORT))
        self.add_log(f"Server listening on {SERVER_IP}:{SERVER_PORT}")

        # Start listener thread
        threading.Thread(target=self.listen_udp, daemon=True).start()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        """Save data before closing."""
        save_data()
        self.destroy()

    def add_log(self, message: str):
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def refresh_active_list(self):
        # Clear existing items
        for widget in self.active_list.winfo_children():
            widget.destroy()

        # Show each active user
        for reg in active_registrations:
            frame = ctk.CTkFrame(self.active_list)
            frame.pack(fill="x", pady=2)
            text = f"{reg['name']} ({reg['role']})  UDP:{reg['udp_port']}  TCP:{reg['tcp_port']}"
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

    def handle_register(self, rq, name, role, ip, udp_port, tcp_port, addr):
        # Check for duplicate name
        for user in active_registrations:
            if user["name"] == name:
                resp = f"REGISTER-DENIED {rq} NameInUse"
                self.sock.sendto(resp.encode(), addr)
                self.add_log(f"Denied registration (duplicate name): {name}")
                return
        # Check capacity
        if len(active_registrations) >= MAX_USERS:
            resp = f"REGISTER-DENIED {rq} ServerFull"
            self.sock.sendto(resp.encode(), addr)
            self.add_log("Denied registration (server full).")
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
        self.refresh_active_list()
        resp = f"REGISTERED {rq}"
        self.sock.sendto(resp.encode(), addr)
        self.add_log(f"Registered new user: {name} ({role})")

    def handle_login(self, rq, name, role, addr):
        # Check if user exists in active_registrations
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
        # Remove user if found
        for user in active_registrations:
            if user["name"] == name:
                active_registrations.remove(user)
                self.refresh_active_list()
                resp = f"DE-REGISTERED {rq}"
                self.sock.sendto(resp.encode(), addr)
                self.add_log(f"De-registered user: {name}")
                return
        # If not found, we still respond
        resp = f"DE-REGISTERED {rq}"
        self.sock.sendto(resp.encode(), addr)
        self.add_log(f"De-register requested but user not found: {name}")


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ServerApp()
    app.mainloop()

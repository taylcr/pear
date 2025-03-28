import customtkinter as ctk
import socket
import threading
import random
import sys
import os

# Adjust these to match your server’s address/port:
SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000

class UserWindow(ctk.CTkToplevel):
    """
    A separate window that opens after a successful register/login.
    Shows user info, a 'de-register' button, a log area, and a placeholder label.
    """
    def __init__(self, master_app, name, role, udp_port, tcp_port):
        super().__init__()
        self.master_app = master_app  # reference to the main client app
        self.name = name
        self.role = role
        self.udp_port = udp_port
        self.tcp_port = tcp_port

        self.title(f"User: {self.name}")
        self.geometry("400x300")
        self.resizable(False, False)

        # Main frame
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

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
        self.dereg_button = ctk.CTkButton(
            main_frame,
            text="De-register",
            command=self.request_deregister
        )
        self.dereg_button.pack(pady=5)

        # Log area
        self.log_text = ctk.CTkTextbox(main_frame, width=380, height=80)
        self.log_text.pack(pady=5)

        # Placeholder label
        placeholder_label = ctk.CTkLabel(
            main_frame,
            text="(Placeholder area for future features)"
        )
        placeholder_label.pack(pady=5)

    def add_log(self, message: str):
        """Append text to the user window's log area."""
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def request_deregister(self):
        """Ask the main app to send DE-REGISTER for this user."""
        self.master_app.send_deregister(self.name, self)

    def close_window(self):
        """Close this user window."""
        self.destroy()


class ClientApp(ctk.CTk):
    """
    The main client window:
      - Name entry
      - Role dropdown
      - Register, Login buttons
      - A log area
    Opens a UserWindow on successful register/login.
    """
    def __init__(self):
        super().__init__()
        self.title("Client Main Page")
        self.geometry("500x300")
        self.resizable(False, False)

        # Create a UDP socket for the entire client
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Bind to a random local UDP port
        self.sock.bind((SERVER_IP, 0))
        self.local_udp_port = self.sock.getsockname()[1]

        # A dictionary to keep track of outstanding requests: { rq#: {"type":..., "name":..., "role":..., "tcp_port":..., ...} }
        self.requests = {}
        # A dictionary to track open user windows by name: { name: user_window }
        self.user_windows = {}

        # Start a background thread to listen for server responses
        self.listening = True
        threading.Thread(target=self.listen_server, daemon=True).start()

        # Build the main UI
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Name entry
        ctk.CTkLabel(main_frame, text="Name:").pack(anchor="w")
        self.name_var = ctk.StringVar()
        self.name_entry = ctk.CTkEntry(main_frame, textvariable=self.name_var, width=200)
        self.name_entry.pack(pady=5)

        # Role dropdown
        ctk.CTkLabel(main_frame, text="Role:").pack(anchor="w")
        self.role_var = ctk.StringVar(value="Buyer")
        self.role_menu = ctk.CTkOptionMenu(main_frame, values=["Buyer", "Seller"], variable=self.role_var)
        self.role_menu.pack(pady=5)

        # Buttons (Register, Login)
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(pady=5)

        self.register_button = ctk.CTkButton(button_frame, text="Register", command=self.register_user)
        self.register_button.pack(side="left", padx=5)

        self.login_button = ctk.CTkButton(button_frame, text="Login", command=self.login_user)
        self.login_button.pack(side="left", padx=5)

        # Log area
        self.log_text = ctk.CTkTextbox(main_frame, width=450, height=80)
        self.log_text.pack(pady=5)

        # On close, clean up
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        """Close the main window."""
        self.listening = False
        self.sock.close()
        # Close all user windows
        for w in list(self.user_windows.values()):
            w.close_window()
        self.destroy()

    def add_log(self, msg: str):
        """Append text to the main window's log area."""
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    # ---------------------------------------------------------------------
    # Sending Requests to the Server
    # ---------------------------------------------------------------------

    def register_user(self):
        name = self.name_var.get().strip()
        role = self.role_var.get().strip()
        if not name:
            self.add_log("ERROR: Name cannot be empty.")
            return
        rq = str(random.randint(1000, 9999))
        tcp_port = str(random.randint(40001, 50000))  # random TCP port for demonstration
        # Build REGISTER message
        # Format: REGISTER RQ# Name Role IP UDP_port TCP_port
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
        """
        Called by a user window to request de-registration.
        We'll store the user_window so we can close it when we get the response.
        """
        rq = str(random.randint(1000, 9999))
        msg = f"DE-REGISTER {rq} {name}"
        self.sock.sendto(msg.encode(), (SERVER_IP, SERVER_PORT))
        self.requests[rq] = {"type": "deregister", "name": name, "window": user_window}
        self.add_log(f"Sent DE-REGISTER (RQ={rq}) for {name}.")

    # ---------------------------------------------------------------------
    # Receiving Responses from the Server
    # ---------------------------------------------------------------------

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
        request_info = self.requests.pop(rq, None)  # remove from dictionary if present

        if cmd == "REGISTERED" and request_info is not None:
            # e.g. "REGISTERED 1234"
            if request_info["type"] == "register":
                name = request_info["name"]
                role = request_info["role"]
                tcp_port = request_info["tcp_port"]
                self.open_user_window(name, role, tcp_port)
            else:
                # Not matching a register request (unlikely if everything is correct)
                pass

        elif cmd == "REGISTER-DENIED":
            # e.g. "REGISTER-DENIED 1234 Reason"
            # request_info might have details
            pass

        elif cmd == "LOGIN_OK" and request_info is not None:
            # e.g. "LOGIN_OK 1234"
            if request_info["type"] == "login":
                name = request_info["name"]
                role = request_info["role"]
                # For demonstration, pick a random TCP port when login is successful
                tcp_port = str(random.randint(40001, 50000))
                self.open_user_window(name, role, tcp_port)
            else:
                pass

        elif cmd == "LOGIN_FAIL":
            # e.g. "LOGIN_FAIL 1234 reason"
            pass

        elif cmd == "DE-REGISTERED" and request_info is not None:
            # e.g. "DE-REGISTERED 1234"
            if request_info["type"] == "deregister":
                name = request_info["name"]
                user_window = request_info["window"]
                # Close that user window
                user_window.add_log("De-registered successfully. Closing window.")
                user_window.close_window()
                if name in self.user_windows:
                    del self.user_windows[name]
            else:
                pass

        # If request_info is None, it means we didn't find a matching RQ, or we already popped it.

    # ---------------------------------------------------------------------
    # Creating/Managing User Windows
    # ---------------------------------------------------------------------

    def open_user_window(self, name, role, tcp_port):
        """Create and display a UserWindow for a newly registered/logged-in user."""
        # If there's already a window for this user, close it or reuse it.
        if name in self.user_windows:
            self.user_windows[name].close_window()
            del self.user_windows[name]

        uw = UserWindow(
            master_app=self,
            name=name,
            role=role,
            udp_port=self.local_udp_port,
            tcp_port=tcp_port
        )
        self.user_windows[name] = uw
        uw.add_log(f"Welcome {name} ({role})! Registered/Login success.")


if __name__ == "__main__":
    ctk.set_appearance_mode("System")
    ctk.set_default_color_theme("blue")
    app = ClientApp()
    app.mainloop()

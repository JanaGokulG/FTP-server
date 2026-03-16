"""
FTP Server - 24XW46 Computer Networks Lab
Topic: FTP Server For Secure File Transfer
Language: Python
"""

import socket
import threading
import os
import hashlib
import json
import time
from pathlib import Path

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────
HOST         = "0.0.0.0"
CTRL_PORT    = 2121          # Control channel port
DATA_PORT    = 2122          # Data channel base port
SERVER_DIR   = "./server_files"  # Root directory served to clients
BUFFER_SIZE  = 4096
MAX_CLIENTS  = 10

# ─────────────────────────────────────────────
#  USER DATABASE  (username -> hashed password)
#  Passwords are SHA-256 hashed for security.
#  Default credentials:  admin/admin123  |  user1/pass123
# ─────────────────────────────────────────────
USER_DB = {
    "admin": hashlib.sha256("admin123".encode()).hexdigest(),
    "user1": hashlib.sha256("pass123".encode()).hexdigest(),
}

# Ensure server directory exists
os.makedirs(SERVER_DIR, exist_ok=True)


# ─────────────────────────────────────────────
#  LOGGING HELPER
# ─────────────────────────────────────────────
def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}")


# ─────────────────────────────────────────────
#  CLIENT HANDLER THREAD
# ─────────────────────────────────────────────
class ClientHandler(threading.Thread):
    """Handles one connected FTP client on its own thread."""

    def __init__(self, conn: socket.socket, addr, data_port: int):
        super().__init__(daemon=True)
        self.conn       = conn
        self.addr       = addr
        self.data_port  = data_port
        self.username   = None
        self.authenticated = False
        self.current_dir   = SERVER_DIR

    # ── low-level send / recv ──────────────────
    def send(self, msg: str):
        try:
            self.conn.sendall((msg + "\r\n").encode())
        except Exception:
            pass

    def recv(self) -> str:
        try:
            data = self.conn.recv(BUFFER_SIZE)
            return data.decode(errors="replace").strip()
        except Exception:
            return ""

    # ── data channel ──────────────────────────
    def open_data_channel(self) -> socket.socket | None:
        """Open a temporary TCP data channel on self.data_port."""
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((HOST, self.data_port))
            srv.listen(1)
            srv.settimeout(15)
            self.send(f"150 Opening data connection on port {self.data_port}")
            data_conn, _ = srv.accept()
            srv.close()
            return data_conn
        except Exception as e:
            self.send(f"425 Cannot open data connection: {e}")
            return None

    # ── command handlers ──────────────────────
    def cmd_user(self, args: str):
        self.username = args.strip()
        self.send(f"331 Password required for {self.username}")

    def cmd_pass(self, args: str):
        if not self.username:
            self.send("503 Login with USER first")
            return
        pw_hash = hashlib.sha256(args.strip().encode()).hexdigest()
        if self.username in USER_DB and USER_DB[self.username] == pw_hash:
            self.authenticated = True
            log(f"User '{self.username}' authenticated from {self.addr}")
            self.send(f"230 User {self.username} logged in successfully")
        else:
            self.send("530 Login incorrect")
            log(f"Failed login attempt for '{self.username}' from {self.addr}", "WARN")

    def cmd_list(self, _args: str):
        """List files in current server directory."""
        if not self.authenticated:
            self.send("530 Please login with USER and PASS")
            return
        data_conn = self.open_data_channel()
        if not data_conn:
            return
        try:
            files = []
            for entry in os.scandir(self.current_dir):
                size  = entry.stat().st_size if entry.is_file() else 0
                ftype = "FILE" if entry.is_file() else "DIR "
                files.append(f"{ftype}  {entry.name:<40}  {size:>10} bytes")
            listing = "\n".join(files) if files else "(empty directory)"
            data_conn.sendall(listing.encode())
            data_conn.close()
            self.send("226 Directory listing complete")
        except Exception as e:
            self.send(f"550 Error listing directory: {e}")

    def cmd_retr(self, filename: str):
        """Send a file to the client (download)."""
        if not self.authenticated:
            self.send("530 Please login first")
            return
        filepath = os.path.join(self.current_dir, os.path.basename(filename.strip()))
        if not os.path.isfile(filepath):
            self.send(f"550 File not found: {filename.strip()}")
            return
        data_conn = self.open_data_channel()
        if not data_conn:
            return
        try:
            filesize = os.path.getsize(filepath)
            # Send metadata first: JSON header terminated by newline
            header = json.dumps({"filename": os.path.basename(filepath), "size": filesize})
            data_conn.sendall((header + "\n").encode())
            bytes_sent = 0
            with open(filepath, "rb") as f:
                while chunk := f.read(BUFFER_SIZE):
                    data_conn.sendall(chunk)
                    bytes_sent += len(chunk)
            data_conn.close()
            log(f"RETR '{filepath}' -> {self.addr} ({bytes_sent} bytes)")
            self.send(f"226 Transfer complete ({bytes_sent} bytes)")
        except Exception as e:
            self.send(f"426 Transfer aborted: {e}")

    def cmd_stor(self, filename: str):
        """Receive a file from the client (upload)."""
        if not self.authenticated:
            self.send("530 Please login first")
            return
        safe_name = os.path.basename(filename.strip())
        if not safe_name:
            self.send("550 Invalid filename")
            return
        data_conn = self.open_data_channel()
        if not data_conn:
            return
        try:
            # Read JSON header
            header_buf = b""
            while b"\n" not in header_buf:
                chunk = data_conn.recv(BUFFER_SIZE)
                if not chunk:
                    break
                header_buf += chunk
            header_line, rest = header_buf.split(b"\n", 1)
            meta     = json.loads(header_line.decode())
            filesize = meta.get("size", 0)

            filepath = os.path.join(self.current_dir, safe_name)
            received = len(rest)
            with open(filepath, "wb") as f:
                f.write(rest)
                while received < filesize:
                    chunk = data_conn.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            data_conn.close()
            log(f"STOR '{filepath}' <- {self.addr} ({received} bytes)")
            self.send(f"226 Transfer complete ({received} bytes stored)")
        except Exception as e:
            self.send(f"426 Transfer aborted: {e}")

    def cmd_dele(self, filename: str):
        """Delete a file from the server."""
        if not self.authenticated:
            self.send("530 Please login first")
            return
        filepath = os.path.join(self.current_dir, os.path.basename(filename.strip()))
        if not os.path.isfile(filepath):
            self.send(f"550 File not found: {filename.strip()}")
            return
        os.remove(filepath)
        log(f"DELE '{filepath}' by {self.username}@{self.addr}")
        self.send("250 File deleted successfully")

    def cmd_pwd(self, _args: str):
        """Print working directory."""
        if not self.authenticated:
            self.send("530 Please login first")
            return
        self.send(f'257 "{self.current_dir}" is current directory')

    def cmd_quit(self, _args: str):
        self.send("221 Goodbye")
        log(f"Client {self.addr} disconnected")
        self.conn.close()

    def cmd_syst(self, _args: str):
        self.send("215 UNIX Type: Python FTP Server")

    def cmd_noop(self, _args: str):
        self.send("200 OK")

    # ── dispatch table ────────────────────────
    COMMANDS = {
        "USER": cmd_user,
        "PASS": cmd_pass,
        "LIST": cmd_list,
        "RETR": cmd_retr,
        "STOR": cmd_stor,
        "DELE": cmd_dele,
        "PWD" : cmd_pwd,
        "QUIT": cmd_quit,
        "SYST": cmd_syst,
        "NOOP": cmd_noop,
    }

    # ── main loop ─────────────────────────────
    def run(self):
        log(f"New connection from {self.addr}")
        self.send("220 Python FTP Server Ready (24XW46 CN Lab)")
        try:
            while True:
                line = self.recv()
                if not line:
                    break
                parts   = line.split(" ", 1)
                cmd     = parts[0].upper()
                args    = parts[1] if len(parts) > 1 else ""
                handler = self.COMMANDS.get(cmd)
                if handler:
                    handler(self, args)
                    if cmd == "QUIT":
                        break
                else:
                    self.send(f"502 Command '{cmd}' not implemented")
        except Exception as e:
            log(f"Error with client {self.addr}: {e}", "ERROR")
        finally:
            try:
                self.conn.close()
            except Exception:
                pass


# ─────────────────────────────────────────────
#  SERVER MAIN
# ─────────────────────────────────────────────
def start_server():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, CTRL_PORT))
    server_sock.listen(MAX_CLIENTS)

    log(f"FTP Server started on {HOST}:{CTRL_PORT}")
    log(f"Serving files from: {os.path.abspath(SERVER_DIR)}")
    log(f"Valid users: {', '.join(USER_DB.keys())}")
    log("Waiting for connections... (Ctrl+C to stop)\n")

    client_count = 0
    try:
        while True:
            conn, addr = server_sock.accept()
            # Assign a unique data port per client
            data_port   = DATA_PORT + (client_count % MAX_CLIENTS)
            client_count += 1
            handler = ClientHandler(conn, addr, data_port)
            handler.start()
    except KeyboardInterrupt:
        log("Server shutting down...")
    finally:
        server_sock.close()


if __name__ == "__main__":
    start_server()
"""
FTP Client (GUI) - 24XW46 Computer Networks Lab
Topic: FTP Server For Secure File Transfer
Language: Python  |  GUI: tkinter (stdlib)
"""

import socket
import os
import json
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# ─────────────────────────────────────────────
#  PROTOCOL CONSTANTS
# ─────────────────────────────────────────────
DEFAULT_HOST   = "127.0.0.1"
DEFAULT_PORT   = 2121
BUFFER_SIZE    = 4096
DOWNLOAD_DIR   = "./downloaded_files"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ─────────────────────────────────────────────
#  NETWORK LAYER  (no GUI dependency)
# ─────────────────────────────────────────────
class FTPClient:
    """Low-level FTP client; all network I/O in plain Python."""

    def __init__(self):
        self.sock       = None
        self.connected  = False
        self.logged_in  = False
        self.host       = ""
        self.data_port  = None

    # ── helpers ───────────────────────────────
    def _send(self, cmd: str):
        self.sock.sendall((cmd + "\r\n").encode())

    def _recv(self) -> str:
        data = b""
        self.sock.settimeout(10)
        try:
            while True:
                chunk = self.sock.recv(BUFFER_SIZE)
                if not chunk:
                    break
                data += chunk
                if b"\r\n" in data or b"\n" in data:
                    break
        except socket.timeout:
            pass
        return data.decode(errors="replace").strip()

    def _get_data_port(self, welcome: str) -> int:
        """Parse data port from server welcome or response."""
        # Server encodes port in 150 responses: "port XXXX"
        for word in welcome.split():
            if word.isdigit() and int(word) > 1024:
                return int(word)
        return self.data_port or (int(DEFAULT_PORT) + 1)

    # ── public API ────────────────────────────
    def connect(self, host: str, port: int) -> str:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect((host, port))
        self.host      = host
        self.connected = True
        return self._recv()   # "220 ..."

    def login(self, username: str, password: str) -> tuple[str, str]:
        self._send(f"USER {username}")
        r1 = self._recv()     # "331 ..."
        self._send(f"PASS {password}")
        r2 = self._recv()     # "230 ..." or "530 ..."
        if r2.startswith("230"):
            self.logged_in = True
        return r1, r2

    def list_files(self) -> tuple[str, str]:
        """Return (control_response, directory_listing)."""
        self._send("LIST")
        ctrl = self._recv()   # "150 Opening data connection on port XXXX"
        dport = self._get_data_port(ctrl)
        # Open data connection
        listing = ""
        try:
            dsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dsock.settimeout(10)
            dsock.connect((self.host, dport))
            buf = b""
            while True:
                chunk = dsock.recv(BUFFER_SIZE)
                if not chunk:
                    break
                buf += chunk
            dsock.close()
            listing = buf.decode(errors="replace")
        except Exception as e:
            listing = f"(error reading data channel: {e})"
        ctrl2 = self._recv()  # "226 ..."
        return ctrl2, listing

    def download(self, filename: str, progress_cb=None) -> tuple[str, str]:
        """Download a file from the server. Returns (status, local_path)."""
        self._send(f"RETR {filename}")
        ctrl = self._recv()   # "150 ..."
        if not ctrl.startswith("150"):
            return ctrl, ""
        dport = self._get_data_port(ctrl)
        local_path = ""
        try:
            dsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dsock.settimeout(30)
            dsock.connect((self.host, dport))

            # Read JSON header line
            hbuf = b""
            while b"\n" not in hbuf:
                c = dsock.recv(1)
                if not c:
                    break
                hbuf += c
            meta      = json.loads(hbuf.decode())
            filesize  = meta.get("size", 0)
            safe_name = os.path.basename(meta.get("filename", filename))

            local_path = os.path.join(DOWNLOAD_DIR, safe_name)
            received   = 0
            with open(local_path, "wb") as f:
                while received < filesize:
                    chunk = dsock.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    if progress_cb:
                        progress_cb(received, filesize)
            dsock.close()
        except Exception as e:
            ctrl2 = self._recv()
            return f"Error: {e}", local_path
        ctrl2 = self._recv()  # "226 ..."
        return ctrl2, local_path

    def upload(self, filepath: str, progress_cb=None) -> str:
        """Upload a local file to the server. Returns control response."""
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        self._send(f"STOR {filename}")
        ctrl = self._recv()   # "150 ..."
        if not ctrl.startswith("150"):
            return ctrl
        dport = self._get_data_port(ctrl)
        try:
            dsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            dsock.settimeout(30)
            dsock.connect((self.host, dport))

            # Send JSON header first
            header = json.dumps({"filename": filename, "size": filesize}) + "\n"
            dsock.sendall(header.encode())

            sent = 0
            with open(filepath, "rb") as f:
                while chunk := f.read(BUFFER_SIZE):
                    dsock.sendall(chunk)
                    sent += len(chunk)
                    if progress_cb:
                        progress_cb(sent, filesize)
            dsock.close()
        except Exception as e:
            return f"Error: {e}"
        return self._recv()   # "226 ..."

    def delete(self, filename: str) -> str:
        self._send(f"DELE {filename}")
        return self._recv()

    def pwd(self) -> str:
        self._send("PWD")
        return self._recv()

    def quit(self) -> str:
        if self.connected:
            self._send("QUIT")
            resp = self._recv()
            self.sock.close()
            self.connected  = False
            self.logged_in  = False
            return resp
        return ""


# ─────────────────────────────────────────────
#  GUI APPLICATION
# ─────────────────────────────────────────────
class FTPApp(tk.Tk):
    """Main GUI window for the FTP client."""

    # ── colours / fonts ───────────────────────
    BG      = "#1e1e2e"
    PANEL   = "#2a2a3e"
    ACCENT  = "#7c6af7"
    TEXT    = "#cdd6f4"
    GREEN   = "#a6e3a1"
    RED     = "#f38ba8"
    YELLOW  = "#f9e2af"
    FONT    = ("Consolas", 10)
    BOLD    = ("Consolas", 10, "bold")

    def __init__(self):
        super().__init__()
        self.ftp = FTPClient()
        self.title("FTP Client — 24XW46 Computer Networks Lab")
        self.geometry("960x680")
        self.resizable(True, True)
        self.configure(bg=self.BG)
        self._build_ui()

    # ── UI BUILDER ────────────────────────────
    def _build_ui(self):
        # ─ top bar: connection ─
        top = tk.Frame(self, bg=self.BG, pady=8)
        top.pack(fill="x", padx=12)

        tk.Label(top, text="Host:", bg=self.BG, fg=self.TEXT, font=self.FONT).pack(side="left")
        self.host_var = tk.StringVar(value=DEFAULT_HOST)
        tk.Entry(top, textvariable=self.host_var, width=16, bg=self.PANEL, fg=self.TEXT,
                 insertbackground=self.TEXT, font=self.FONT, relief="flat").pack(side="left", padx=(2,8))

        tk.Label(top, text="Port:", bg=self.BG, fg=self.TEXT, font=self.FONT).pack(side="left")
        self.port_var = tk.StringVar(value=str(DEFAULT_PORT))
        tk.Entry(top, textvariable=self.port_var, width=6, bg=self.PANEL, fg=self.TEXT,
                 insertbackground=self.TEXT, font=self.FONT, relief="flat").pack(side="left", padx=(2,8))

        tk.Label(top, text="User:", bg=self.BG, fg=self.TEXT, font=self.FONT).pack(side="left")
        self.user_var = tk.StringVar(value="admin")
        tk.Entry(top, textvariable=self.user_var, width=10, bg=self.PANEL, fg=self.TEXT,
                 insertbackground=self.TEXT, font=self.FONT, relief="flat").pack(side="left", padx=(2,8))

        tk.Label(top, text="Pass:", bg=self.BG, fg=self.TEXT, font=self.FONT).pack(side="left")
        self.pass_var = tk.StringVar(value="admin123")
        tk.Entry(top, textvariable=self.pass_var, show="*", width=10, bg=self.PANEL, fg=self.TEXT,
                 insertbackground=self.TEXT, font=self.FONT, relief="flat").pack(side="left", padx=(2,8))

        self.conn_btn = tk.Button(top, text="Connect", command=self._toggle_connection,
                                  bg=self.ACCENT, fg="white", font=self.BOLD,
                                  relief="flat", padx=10, cursor="hand2")
        self.conn_btn.pack(side="left", padx=4)

        self.status_lbl = tk.Label(top, text="● Disconnected", bg=self.BG, fg=self.RED, font=self.BOLD)
        self.status_lbl.pack(side="left", padx=8)

        # ─ middle: file list + log ─
        mid = tk.PanedWindow(self, orient="horizontal", bg=self.BG, sashwidth=4)
        mid.pack(fill="both", expand=True, padx=12, pady=4)

        # left pane: file list
        left = tk.Frame(mid, bg=self.PANEL, padx=6, pady=6)
        mid.add(left, minsize=320)

        tk.Label(left, text="Server Files", bg=self.PANEL, fg=self.ACCENT,
                 font=("Consolas", 11, "bold")).pack(anchor="w")

        cols = ("type", "name", "size")
        self.tree = ttk.Treeview(left, columns=cols, show="headings", height=20)
        self.tree.heading("type", text="Type")
        self.tree.heading("name", text="Filename")
        self.tree.heading("size", text="Size")
        self.tree.column("type", width=50, anchor="center")
        self.tree.column("name", width=200)
        self.tree.column("size", width=90, anchor="e")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
                        background=self.PANEL, foreground=self.TEXT,
                        fieldbackground=self.PANEL, font=self.FONT, rowheight=22)
        style.configure("Treeview.Heading",
                        background=self.BG, foreground=self.ACCENT, font=self.BOLD)
        style.map("Treeview", background=[("selected", self.ACCENT)])

        vsb = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")

        # right pane: log
        right = tk.Frame(mid, bg=self.BG, padx=6, pady=6)
        mid.add(right, minsize=300)

        tk.Label(right, text="Session Log", bg=self.BG, fg=self.ACCENT,
                 font=("Consolas", 11, "bold")).pack(anchor="w")
        self.log_box = scrolledtext.ScrolledText(right, bg=self.PANEL, fg=self.TEXT,
                                                  font=self.FONT, relief="flat", state="disabled")
        self.log_box.pack(fill="both", expand=True)

        # ─ bottom: action buttons + progress ─
        bot = tk.Frame(self, bg=self.BG, pady=6)
        bot.pack(fill="x", padx=12)

        btn_cfg = dict(bg=self.PANEL, fg=self.TEXT, font=self.BOLD,
                       relief="flat", padx=12, pady=4, cursor="hand2",
                       activebackground=self.ACCENT, activeforeground="white")

        self.refresh_btn = tk.Button(bot, text="⟳ Refresh", command=self._refresh, **btn_cfg)
        self.refresh_btn.pack(side="left", padx=4)

        self.download_btn = tk.Button(bot, text="⬇ Download", command=self._download, **btn_cfg)
        self.download_btn.pack(side="left", padx=4)

        self.upload_btn = tk.Button(bot, text="⬆ Upload", command=self._upload, **btn_cfg)
        self.upload_btn.pack(side="left", padx=4)

        self.delete_btn = tk.Button(bot, text="✕ Delete", command=self._delete,
                                    bg=self.PANEL, fg=self.RED, font=self.BOLD,
                                    relief="flat", padx=12, pady=4, cursor="hand2")
        self.delete_btn.pack(side="left", padx=4)

        tk.Button(bot, text="⏻ Disconnect", command=self._disconnect,
                  bg=self.PANEL, fg=self.YELLOW, font=self.BOLD,
                  relief="flat", padx=12, pady=4, cursor="hand2").pack(side="left", padx=4)

        self.progress = ttk.Progressbar(bot, length=200, mode="determinate")
        self.progress.pack(side="right", padx=8)
        self.progress_lbl = tk.Label(bot, text="", bg=self.BG, fg=self.TEXT, font=self.FONT)
        self.progress_lbl.pack(side="right")

        self._set_buttons_state(False)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── LOG HELPERS ───────────────────────────
    def _log(self, msg: str, color: str | None = None):
        self.log_box.configure(state="normal")
        tag = color or "default"
        self.log_box.tag_configure(tag, foreground=color or self.TEXT)
        self.log_box.insert("end", msg + "\n", tag)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # ── STATE HELPERS ─────────────────────────
    def _set_buttons_state(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for btn in (self.refresh_btn, self.download_btn, self.upload_btn,
                    self.delete_btn):
            btn.configure(state=state)

    def _set_status(self, connected: bool):
        if connected:
            self.status_lbl.configure(text="● Connected", fg=self.GREEN)
            self.conn_btn.configure(text="Disconnect", bg="#e06c75")
        else:
            self.status_lbl.configure(text="● Disconnected", fg=self.RED)
            self.conn_btn.configure(text="Connect", bg=self.ACCENT)
        self._set_buttons_state(connected)

    # ── PROGRESS CALLBACK ─────────────────────
    def _update_progress(self, done: int, total: int):
        pct = int(done / total * 100) if total else 0
        self.progress["value"] = pct
        self.progress_lbl.configure(text=f"{pct}%")
        self.update_idletasks()

    def _reset_progress(self):
        self.progress["value"] = 0
        self.progress_lbl.configure(text="")

    # ── ACTIONS ───────────────────────────────
    def _toggle_connection(self):
        if self.ftp.connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        host = self.host_var.get().strip()
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Invalid port number")
            return
        user = self.user_var.get().strip()
        pw   = self.pass_var.get()

        def _worker():
            try:
                self._log(f"Connecting to {host}:{port} ...", self.YELLOW)
                welcome = self.ftp.connect(host, port)
                self._log(f"← {welcome}", self.GREEN)
                r1, r2 = self.ftp.login(user, pw)
                self._log(f"← {r1}")
                self._log(f"← {r2}", self.GREEN if self.ftp.logged_in else self.RED)
                if self.ftp.logged_in:
                    self.after(0, lambda: self._set_status(True))
                    self.after(0, self._refresh)
                else:
                    self.ftp.sock.close()
                    self.ftp.connected = False
            except Exception as e:
                self._log(f"Connection error: {e}", self.RED)

        threading.Thread(target=_worker, daemon=True).start()

    def _disconnect(self):
        if self.ftp.connected:
            resp = self.ftp.quit()
            self._log(f"← {resp}", self.YELLOW)
        self._set_status(False)
        self.tree.delete(*self.tree.get_children())

    def _refresh(self):
        if not self.ftp.logged_in:
            return
        def _worker():
            self._log("→ LIST", self.YELLOW)
            ctrl, listing = self.ftp.list_files()
            self._log(f"← {ctrl}")
            self.after(0, lambda: self._populate_tree(listing))
        threading.Thread(target=_worker, daemon=True).start()

    def _populate_tree(self, listing: str):
        self.tree.delete(*self.tree.get_children())
        for line in listing.strip().splitlines():
            parts = line.split()
            if not parts:
                continue
            ftype = parts[0]
            # Format: "FILE  name  size bytes"
            if len(parts) >= 3:
                size = parts[-2] + " B"
                name = " ".join(parts[1:-2])
            else:
                size = ""
                name = " ".join(parts[1:])
            icon = "📄" if ftype == "FILE" else "📁"
            self.tree.insert("", "end", values=(icon, name, size))

    def _download(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select file", "Please select a file to download.")
            return
        filename = self.tree.item(sel[0])["values"][1]

        def _worker():
            self._log(f"→ RETR {filename}", self.YELLOW)
            self._reset_progress()
            ctrl, path = self.ftp.download(filename, self._update_progress)
            self._log(f"← {ctrl}", self.GREEN if ctrl.startswith("226") else self.RED)
            if path:
                self._log(f"   Saved → {os.path.abspath(path)}", self.GREEN)
                self.after(0, self._reset_progress)

        threading.Thread(target=_worker, daemon=True).start()

    def _upload(self):
        filepath = filedialog.askopenfilename(title="Select file to upload")
        if not filepath:
            return

        def _worker():
            self._log(f"→ STOR {os.path.basename(filepath)}", self.YELLOW)
            self._reset_progress()
            resp = self.ftp.upload(filepath, self._update_progress)
            self._log(f"← {resp}", self.GREEN if resp.startswith("226") else self.RED)
            self.after(0, self._reset_progress)
            self.after(500, self._refresh)

        threading.Thread(target=_worker, daemon=True).start()

    def _delete(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select file", "Please select a file to delete.")
            return
        filename = self.tree.item(sel[0])["values"][1]
        if not messagebox.askyesno("Confirm Delete", f"Delete '{filename}' from server?"):
            return

        def _worker():
            self._log(f"→ DELE {filename}", self.YELLOW)
            resp = self.ftp.delete(filename)
            self._log(f"← {resp}", self.GREEN if resp.startswith("250") else self.RED)
            self.after(500, self._refresh)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_close(self):
        self._disconnect()
        self.destroy()


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = FTPApp()
    app.mainloop()
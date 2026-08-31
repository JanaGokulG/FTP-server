# 📁 Secure FTP Server for File Transfer

> A Python-based FTP Server and GUI Client that enables secure file transfer with user authentication, multithreading, and an intuitive desktop interface.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue.svg">
  <img src="https://img.shields.io/badge/GUI-Tkinter-green.svg">
  <img src="https://img.shields.io/badge/Networking-Socket-orange.svg">
  <img src="https://img.shields.io/badge/Protocol-FTP-red.svg">
  <img src="https://img.shields.io/badge/License-MIT-lightgrey.svg">
</p>

---

# 📖 Overview

This project implements a **File Transfer Protocol (FTP)** system in Python consisting of:

- 🖥️ A multithreaded FTP Server
- 💻 A modern GUI FTP Client
- 🔐 Secure user authentication using SHA-256 password hashing
- 📂 File upload, download, delete, and directory listing
- 📊 File transfer progress monitoring
- 🧵 Concurrent client handling using multithreading

The project demonstrates practical concepts of **Computer Networks**, **Socket Programming**, **Client-Server Architecture**, and **Multithreading**.

---

# ✨ Features

## 🖥️ FTP Server

- Multi-client support using threads
- Secure login authentication
- SHA-256 password hashing
- Separate control and data channels
- Directory listing
- File upload
- File download
- File deletion
- Activity logging
- JSON-based metadata exchange

---

## 💻 FTP Client

- Clean Tkinter GUI
- Connect/Disconnect server
- User authentication
- Browse server files
- Upload files
- Download files
- Delete files
- Progress bar for file transfers
- Session log viewer
- File explorer integration

---

# 🔐 Security Features

- SHA-256 encrypted password storage
- Username/password authentication
- Protected file operations
- Safe filename handling
- Client authentication before file access

---

# 🧠 Computer Networks Concepts Demonstrated

| Concept | Implementation |
|----------|----------------|
| Socket Programming | TCP Client-Server Communication |
| FTP Protocol | Command & Data Channels |
| Multithreading | Multiple client handling |
| Authentication | Secure Login |
| File Transfer | Upload & Download |
| Client-Server Architecture | FTP Communication |
| Network Programming | Python Socket API |

---

# 🛠️ Technologies Used

- Python 3
- Socket Programming
- Tkinter
- Threading
- JSON
- SHA-256 Hashing
- File System APIs

---

# 📂 Project Structure

```
FTP-Server/
│
├── server.py
├── client.py
├── server_files/
├── downloaded_files/
├── README.md
```

---

# 🚀 Installation

Clone the repository

```bash
git clone https://github.com/yourusername/ftp-server.git
```

Move into the project

```bash
cd ftp-server
```

---

# ▶️ Running the Server

```bash
python server.py
```

The server starts on

```
Host : 0.0.0.0
Control Port : 2121
Data Port : 2122
```

---

# ▶️ Running the Client

```bash
python client.py
```

Enter

```
Host : 127.0.0.1
Port : 2121
Username : admin
Password : admin123
```

(Default credentials are provided for demonstration purposes.)

---

# 📋 Supported FTP Commands

| Command | Description |
|----------|-------------|
| USER | Login username |
| PASS | Login password |
| LIST | List server files |
| RETR | Download file |
| STOR | Upload file |
| DELE | Delete file |
| PWD | Current directory |
| QUIT | Disconnect |
| SYST | System information |
| NOOP | Keep connection alive |

---


---

# 🎯 Learning Outcomes

This project helped in understanding:

- TCP Socket Programming
- FTP Architecture
- Client-Server Communication
- Concurrent Programming
- GUI Development using Tkinter
- Secure Authentication
- File Transfer Protocol
- Python Networking
- Thread Synchronization
- Network Application Development

---

# 🔮 Future Enhancements

- SSL/TLS encrypted FTP (FTPS)
- Drag-and-drop file uploads
- Resume interrupted downloads
- User registration
- Admin dashboard
- File sharing via links
- Database-backed user management
- File compression before transfer

---

# 👨‍💻 Authors

- **Jana Gokul G**  
  M.Sc. Software Systems  
  PSG College of Technology

- **Nidarshana R S**  
  M.Sc. Software Systems  
  PSG College of Technology
---
# 📄 License

This project was developed as part of the **24XW46 Computer Networks Laboratory** coursework and is intended for educational purposes.

---

⭐ If you found this project helpful, consider giving it a **Star** on GitHub!

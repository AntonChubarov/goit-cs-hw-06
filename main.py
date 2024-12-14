import json
import multiprocessing
import os
import socket
import sys
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pymongo
from pymongo import MongoClient

WEB_PORT = int(os.environ.get("WEB_PORT", "3000"))
SOCKET_PORT = int(os.environ.get("SOCKET_PORT", "5000"))
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://mongo:27017/")
MONGO_DB = os.environ.get("MONGO_DB", "messagesDB")
MONGO_COLLECTION = os.environ.get("MONGO_COLLECTION", "messages")
LAST_MESSAGES_COUNT = int(os.environ.get("LAST_MESSAGES_COUNT", "10"))

FRONT_DIR = Path(__file__).parent / "front"


def run_socket_server():
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[MONGO_COLLECTION]

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("0.0.0.0", SOCKET_PORT))
    server_socket.listen(5)

    while True:
        conn, addr = server_socket.accept()
        data = conn.recv(4096)
        if data:
            try:
                msg_dict = json.loads(data.decode("utf-8"))
                msg_dict["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                collection.insert_one(msg_dict)
            except Exception as e:
                print(f"Error inserting document: {e}", file=sys.stderr)
        conn.close()


def send_to_socket_server(data):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(("0.0.0.0", SOCKET_PORT))
    s.send(json.dumps(data).encode("utf-8"))
    s.close()


class RequestHandler(BaseHTTPRequestHandler):
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[MONGO_COLLECTION]

    def do_GET(self):
        if self.path == "/":
            self.serve_index_with_messages()
        elif self.path == "/message.html" or self.path == "/message":
            self.serve_file("message.html", "text/html")
        elif self.path.startswith("/style.css"):
            self.serve_file("style.css", "text/css")
        elif self.path.startswith("/logo.png"):
            self.serve_file("logo.png", "image/png")
        else:
            self.send_error_page()

    def do_POST(self):
        if self.path == "/message":
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length).decode('utf-8')
            data = urllib.parse.parse_qs(body)
            username = data.get("username", [""])[0]
            message = data.get("message", [""])[0]

            send_to_socket_server({"username": username, "message": message})

            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
        else:
            self.send_error_page()

    def serve_index_with_messages(self):
        messages = list(self.collection.find().sort("date", pymongo.ASCENDING).limit(LAST_MESSAGES_COUNT))

        messages_html = '<div class="row"><div class="col"><ul class="list-group mb-4">'
        if messages:
            for msg in messages:
                date = msg.get("date", "")
                if '.' in date:
                    date = date.split('.')[0]
                username = msg.get("username", "Anonymous")
                text = msg.get("message", "")
                messages_html += f'<li class="list-group-item"><strong>{username}</strong> <span class="text-muted" style="float:right;">{date}</span><br>{text}</li>'
        else:
            messages_html += '<li class="list-group-item">No messages found.</li>'
        messages_html += '</ul></div></div>'

        index_path = FRONT_DIR / "index.html"
        if index_path.exists():
            content = index_path.read_text()
            content = content.replace("<!-- MESSAGES_PLACEHOLDER -->", messages_html)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_error_page()

    def serve_file(self, filename, content_type):
        filepath = FRONT_DIR / filename
        if filepath.exists():
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.end_headers()
            with open(filepath, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_error_page()

    def send_error_page(self):
        filepath = FRONT_DIR / "error.html"
        self.send_response(404)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        if filepath.exists():
            with open(filepath, "rb") as f:
                self.wfile.write(f.read())
        else:
            self.wfile.write(b"404 Not Found")


def run_http_server():
    server = HTTPServer(("0.0.0.0", WEB_PORT), RequestHandler)
    server.serve_forever()


if __name__ == "__main__":
    p = multiprocessing.Process(target=run_socket_server)
    p.start()

    run_http_server()
    p.join()

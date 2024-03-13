import re
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer

import redis

redis_storage = redis.Redis()

mappings = [
    (r"^/books?/(?P<book_id>\d+)$", "get_book"),
    (r"^/$", "index"),
]


class WebResquestHandler(BaseHTTPRequestHandler):
    def cookies(self):
        return SimpleCookie(self.headers.get('Cookie'))

    def get_session(self):
        cookies = self.cookies()
        return uuid.uuid4() if not cookies else cookies["session_id"].value

    def write_session_cookie(self, session_id):
        cookies = SimpleCookie()
        cookies["session_id"] = session_id
        cookies["session_id"]["max-age"] = 1000
        self.send_header("Set-Cookie", cookies.output(header=""))

    def do_GET(self):
        self.url_mapping_response()

    def url_mapping_response(self):
        for pattern, method in mappings:
            params = self.get_params(pattern, self.path)
            if params is not None:
                md = getattr(self, method)
                md(**params)
                return
        self.send_response(404)
        self.end_headers()
        self.wfile.write("Not Found".encode("utf-8"))

    def get_params(self, pattern, path):
        match = re.match(pattern, path)
        if match:
            return match.groupdict()

    def index(self, **_):
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        index_page = "<h1>Bienvenidos a la biblioteca!</h1>".encode("utf-8")
        self.wfile.write(index_page)

    def get_book(self, book_id):
        session_id = self.get_session()
        redis_storage.lpush(f"session:{session_id}", f"book:{book_id}")

        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.write_session_cookie(session_id)
        self.end_headers()

        book_info = redis_storage.get(f"book:{book_id}") or "<h1>No existe el libro</h1>".encode("utf-8")
        book_info += f"Session ID:{session_id}".encode("utf-8")
        self.wfile.write(book_info)

        books = redis_storage.lrange(f"session:{session_id}", 0, -1)
        for book in books:
            decoded_book_id = book.decode('utf-8')
            self.wfile.write(f"<br>book:{decoded_book_id}".encode("utf-8"))


if __name__ == "__main__":
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 8000), WebResquestHandler)
    server.serve_forever()

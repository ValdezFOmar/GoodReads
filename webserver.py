import re
import redis
from http.server import BaseHTTPRequestHandler, HTTPServer

r = redis.Redis()

mappings = [
    (r"^/books?/(?P<book_id>\d+)$", "get_book"),
    (r"^/$", "index"),
]

class WebResquestHandler(BaseHTTPRequestHandler):
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
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        # book_info = f"<h1>info del libro {book_id}</h1>".encode("utf-8")
        book_info = r.get('book:' + book_id) or "No existe el libro".encode("utf-8")
        self.wfile.write(book_info)


if __name__ == "__main__":
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 8000), WebResquestHandler)
    server.serve_forever()

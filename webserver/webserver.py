#!/usr/bin/env python

import re
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse

from . import load_pages
from .load_pages import BOOKS_HASH, INDEX_KEY, WORD_KEY_PREFIX
from redis import Redis

redis = Redis()


class WebResquestHandler(BaseHTTPRequestHandler):
    mappings: list[tuple[str, str]] = [
        (r"^/$", "index"),
        (r"^/search", "search"),
        (r"^/books?/(?P<book_id>\d+)$", "get_book"),
    ]

    @property
    def query_data(self):
        return dict(parse_qsl(self.url.query))

    @property
    def url(self):
        return urlparse(self.path)

    def do_GET(self):
        self.url_mapping_response()

    def url_mapping_response(self):
        """Map a path pattern to a method"""
        for pattern, method_name in self.mappings:
            if match := re.match(pattern, self.url.path):
                method = getattr(self, method_name)
                method(**match.groupdict())
                return
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"<h1>Not Found<h1>")

    def index(self):
        html = redis.get(INDEX_KEY)

        if not html:
            html = load_pages.load_index(redis)

        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        self.wfile.write(html)

    def search(self):
        key = "words"
        query = self.query_data

        if key in query:
            words = re.findall(r"\w+", query[key])
        else:
            words = []

        html = load_pages.search_page(words, redis)
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        self.wfile.write(html)

    def get_book(self, book_id: str):
        session_id = self.get_session()
        redis.lpush(f"session:{session_id}", f"book:{book_id}")

        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.write_session_cookie(session_id)
        self.end_headers()

        book_info = redis.hget(BOOKS_HASH, book_id) or b"<h1>Error 404: Book not Found!</h1>"
        book_info += f"Session ID:{session_id}".encode("utf-8")
        self.wfile.write(book_info)

        books = redis.lrange(f"session:{session_id}", 0, -1)
        for book in books:
            decoded_book_id = book.decode("utf-8")
            self.wfile.write(f"<br>book:{decoded_book_id}".encode("utf-8"))

    def cookies(self):
        return SimpleCookie(self.headers.get("Cookie"))

    def get_session(self):
        cookies = self.cookies()
        key = "session_id"
        return cookies[key].value if key in cookies else uuid.uuid4()

    def write_session_cookie(self, session_id):
        cookies = SimpleCookie()
        cookies["session_id"] = session_id
        cookies["session_id"]["max-age"] = 1000
        self.send_header("Set-Cookie", cookies.output(header=""))


def main():
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 8000), WebResquestHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()

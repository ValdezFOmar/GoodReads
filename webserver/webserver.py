#!/usr/bin/env python

import random
import re
import uuid
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlparse

from redis import Redis

from . import load_pages
from .load_pages import BOOKS_HASH, INDEX_KEY

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
        self.error_404()

    def error_404(self, message: str = ""):
        message = message or "Error 404: Page not Found!"
        page = f"<h1>{message}<h1>".encode("utf-8")
        self.send_response(404)
        self.send_header("content-type", "text/html")
        self.end_headers()
        self.wfile.write(page)

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
        session_id = self.get_session_id()
        session_key = f"session:{session_id}"
        self.add_book_to_session(session_key, book_id)

        book_info = redis.hget(BOOKS_HASH, book_id)

        if book_info is None:
            self.error_404("Book not Found!")
            return

        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.write_session_cookie(session_id)
        self.end_headers()
        self.wfile.write(book_info)

        if redis.llen(session_key) >= 3:
            self.wfile.write(self.recommended_book(session_key))

    def add_book_to_session(self, session_key: str, book_id: str):
        id = redis.lindex(session_key, 0)

        if id is None or id.decode("utf-8") != book_id:
            redis.lpush(session_key, book_id)

    def recommended_book(self, session_key) -> bytes:
        books_seen = set(redis.lrange(session_key, 0, -1))
        books_ids = redis.hkeys(BOOKS_HASH)


        if len(books_seen) == len(books_ids):
            random_id = random.choice(books_ids)
        else:
            while True:
                random_id = random.choice(books_ids)
                if random_id not in books_seen:
                    break

        return load_pages.generate_recommendation(random_id.decode("utf-8"), redis)

    @property
    def cookies(self):
        return SimpleCookie(self.headers.get("Cookie"))

    def get_session_id(self) -> str:
        cookies = self.cookies
        session_id = "session_id"

        if session_id in cookies:
            return cookies[session_id].value
        else:
            return str(uuid.uuid4())

    def write_session_cookie(self, session_id: str):
        cookies = SimpleCookie()
        cookies["session_id"] = session_id
        cookies["session_id"]["max-age"] = 1000
        cookies["session_id"]["httponly"] = True
        cookies["session_id"]["samesite"] = "Strict"
        self.send_header("Set-Cookie", cookies.output(header=""))


def main():
    print("Server starting...")
    server = HTTPServer(("0.0.0.0", 8000), WebResquestHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()

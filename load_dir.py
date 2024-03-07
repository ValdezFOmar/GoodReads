import re
import redis
from pathlib import Path

r = redis.Redis()


def load_dir(path):
    for file in Path(path).iterdir():
        match = re.search(r"/book(\d+)\.html$", str(file))
        if match is None:
            continue
        with open(file, encoding="utf-8") as f:
            html = f.read()
            book_id = match[1]
            r.set(f"book:{book_id}", html)
            print(file, "loaded into redis")


if __name__ == "__main__":
    load_dir("html/books/")

import re
from pathlib import Path

from bs4 import BeautifulSoup
from redis import Redis

_parser = "html.parser"


def load_index(redis: Redis, num_books: int = 10) -> bytes:
    """
    Generates the index.html from the template at `html/index.html`
    inserting the number of books specified by `num_books` as a preview
    with the following format:

    <article>
      <h3><a href="/books/id">Book Title</a></h3>
      <p>Author Name</p>
    </article>
    """
    with open("html/index.html") as file:
        index_html = BeautifulSoup(file, _parser)

    books_index = index_html.find("section", id="books")
    assert books_index is not None

    for i, (id, book_page) in enumerate(redis.hscan_iter("books")):
        if i == num_books:
            break
        id = id.decode("utf-8")

        article = index_html.new_tag("article")
        h3 = index_html.new_tag("h3")
        a = index_html.new_tag("a", href=f"/books/{id}")

        book_html = BeautifulSoup(book_page, _parser)
        a.string = book_html.h2.string  # type: ignore

        article.append(h3)
        h3.append(a)
        books_index.append(article)

    return index_html.prettify(encoding='utf-8')


def load_dir(path: str, redis: Redis):
    for file in Path(path).iterdir():
        match = re.search(r"/book(\d+)\.html$", str(file))
        if match is None:
            continue
        with open(file, encoding="utf-8") as f:
            html = f.read()
            book_id = match[1]
            redis.hset("books", book_id, html)
            print(file, "loaded into redis")


if __name__ == "__main__":
    load_dir("html/books/", Redis())

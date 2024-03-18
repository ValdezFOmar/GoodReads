import re
from pathlib import Path

from bs4 import BeautifulSoup
from redis import Redis


INDEX_KEY = ":index:"
_parser = "html.parser"


def load_index(redis: Redis, num_books: int = 10) -> bytes:
    """
    Generates the index.html from the template at `html/index.html`
    inserting the number of books specified (or less) by `num_books`
    as a preview with the following format:

    <li>
      <article>
        <h3><a href="/books/id">Book Title</a></h3>
        <p>Comma separated list of genres</p>
      </article>
    </li>
    """
    with open("html/index.html") as file:
        index_html = BeautifulSoup(file, _parser)

    books_list = index_html.find("ul", id="books-list")
    assert books_list is not None

    for i, (id, book_page) in enumerate(redis.hscan_iter("books")):
        if i == num_books:
            break
        id = id.decode("utf-8")
        book_html = BeautifulSoup(book_page, _parser)

        article = book_html.new_tag("article")
        h3 = book_html.new_tag("h3")
        a = book_html.new_tag("a", href=f"/books/{id}")
        a.string = book_html.h2.string  # type: ignore

        h3.append(a)
        article.append(h3)

        if tag := book_html.find(id="genres"):
            genres = tag.extract()
            genres.name = "p" # pyright: ignore[reportAttributeAccessIssue]
            article.append(genres)

        li = book_html.new_tag("li")
        li.append(article)
        books_list.append(li)

    html = index_html.prettify(encoding='utf-8')
    redis.set(INDEX_KEY, html)
    return html


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


def main():
    redis = Redis()
    load_dir("html/books/", redis)
    load_index(redis)


if __name__ == "__main__":
    main()

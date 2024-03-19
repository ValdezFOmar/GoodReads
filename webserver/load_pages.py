import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from redis import Redis

from .process_data import HTML

BOOKS_HASH = "books"
INDEX_KEY = ":index:"
WORD_KEY_PREFIX = "word:"
_parser = "html.parser"


def load_index(redis: Redis, num_books: int = 10) -> bytes:
    """
    Generates an `index.html` from the template at `html/index.html`
    inserting the number of books specified (or less) by `num_books`
    as a preview with the following format:

    <li>
      <article>
        <h3><a href="/books/id">Book Title</a></h3>
        <p>Comma separated list of genres</p>
      </article>
    </li>
    """
    with open(HTML / "index.html") as file:
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
            genres.name = "p"  # pyright: ignore[reportAttributeAccessIssue]
            article.append(genres)

        li = book_html.new_tag("li")
        li.append(article)
        books_list.append(li)

    html = index_html.encode("utf-8")
    redis.set(INDEX_KEY, html)
    return html


def search_page(words: list[str], redis: Redis) -> bytes:
    """
    Generate and return the search page with the results for the given words.
    Each result is genrated in the following format:

    <li>
      <h3><a href="/books/id">Book title</a></h3>
    </li>
    """
    book_ids = redis.sinter(WORD_KEY_PREFIX + word for word in words)

    with open(HTML / "search.html", "rb") as file:
        template = BeautifulSoup(file, _parser)

    if tag := template.find(id="query"):
        assert isinstance(tag, Tag)
        tag.string = " ".join(words)

    if not book_ids:
        return template.encode("utf-8")

    if tag := template.find("p", id="no-result"):
        tag.extract()

    section = template.find(id="search-results")
    assert isinstance(section, Tag)
    ul = template.new_tag("ul")
    section.append(ul)

    for book_id in book_ids:
        assert isinstance(book_id, bytes)
        book_id = book_id.decode("utf-8")
        book_page = redis.hget(BOOKS_HASH, book_id)
        assert book_page is not None

        book_html = BeautifulSoup(book_page, _parser)
        title = book_html.find(id="book-title")
        assert title is not None

        li = template.new_tag("li")
        h3 = template.new_tag("h3")
        a = template.new_tag("a", href=f"/books/{book_id}")
        a.string = title.string  # type: ignore
        h3.append(a)
        li.append(h3)
        ul.append(li)

    return template.encode("utf-8")


def load_dir(path: str, redis: Redis):
    for book_page in Path(path).iterdir():
        match = re.search(r"/book(\d+)\.html$", str(book_page))
        if match is None:
            continue
        with open(book_page, encoding="utf-8") as file:
            html = file.read()
            book_id = match[1]
            redis.hset(BOOKS_HASH, book_id, html)
            load_words(book_id, html, redis)
            print(book_page, "loaded into redis")


def load_words(book_id: str, html: str, redis: Redis):
    soup = BeautifulSoup(html, _parser)
    summary = soup.find("p", id="summary")
    title = soup.find(id="book-title")

    parser = re.compile(r"\w+")

    for content in (title, summary):
        if not isinstance(content, Tag):
            continue
        for match in parser.finditer(content.get_text(strip=True)):
            word = match[0].lower()
            redis.sadd(WORD_KEY_PREFIX + word, book_id)


def main():
    redis = Redis()
    load_dir("html/books/", redis)
    load_index(redis)


if __name__ == "__main__":
    main()

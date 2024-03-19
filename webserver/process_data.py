#!/usr/bin/env python

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

import bs4

# Information about the data schema
# https://www.kaggle.com/datasets/ymaricar/cmu-book-summary-dataset/data

HTML = Path("html")
BOOKS_DIR = HTML / "books"
TEMPLATE = BOOKS_DIR / "template.html"


@dataclass
class Book:
    wikipedia_id: int
    freebase_id: str
    title: str
    author: str
    publication_date: str
    genres: list[str]
    summary: str


def process_books(path: Path) -> Iterator[Book]:
    with open(path, encoding="utf-8") as file:
        for line in map(str.strip, file):
            wiki_id, *fields, genres, summary = line.split("\t")

            try:
                genres = json.loads(genres)
            except json.decoder.JSONDecodeError:
                genres = {}

            yield Book(
                int(wiki_id),
                *fields,
                list(genres.values()),  # type: ignore
                summary,  # type: ignore
            )


def save_to_json(books_summaries: Path, name: str):
    """Saves each book in single line as a JSON object."""
    with open(name, "w") as file:
        for book in process_books(books_summaries):
            if not book.author or not book.genres:
                continue
            json.dump(book, file, default=asdict)
            file.write("\n")
            print("Saved book:", book.title)


def generate_html(book: Book) -> bs4.BeautifulSoup:
    with open(TEMPLATE, encoding="utf-8") as file:
        html = bs4.BeautifulSoup(file, "html.parser")

    html.head.title.string = book.title  # type: ignore
    html.find(id="book-title").string = book.title  # type: ignore
    html.find(id="author").string = book.author  # type: ignore
    html.find(id="date").string = book.publication_date  # type: ignore
    html.find(id="summary").string = book.summary  # type: ignore

    genres_tag = html.find(id="genres")
    assert isinstance(genres_tag, bs4.Tag)

    if book.genres:
        genres_tag.string = ", ".join(book.genres)
    else:
        genres_tag.extract()

    return html


def generate_pages(data_path: str, max_pages: int):
    with open(data_path, encoding="utf-8") as file:
        for i, data in enumerate(map(json.loads, file)):
            if i == max_pages:
                break

            soup = generate_html(Book(**data))
            output_file = BOOKS_DIR / f"book{i}.html"

            with open(output_file, "w", encoding="utf-8") as html:
                html.write(soup.prettify())


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse data and generate HTML")
    parser.add_argument("-p", "--process", action="store_true")
    parser.add_argument("-g", "--generate", action="store_true")
    parser.add_argument("file", nargs="?", type=Path, default="booksummaries.txt")
    args = parser.parse_args()

    if not (args.process or args.generate):
        parser.error("Choose at least 1 option")

    if not args.file.exists():
        print(f"\033[31m'{args.file}' doesn't exist", file=sys.stderr)
        return 1

    data_output = "books.json.txt"

    if args.process:
        save_to_json(args.file, data_output)
    if args.generate:
        generate_pages(data_output, max_pages=50)

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""A file's line endings, kept across a rewrite: the ledger `set` rewrites
and the markdown `render` rewrites are each worked on with `\\n` and written
back with the newline they were read with."""

from pathlib import Path


def split(text):
    """`text` with its newlines as `\\n`, and the newline it was written
    with: `\\r\\n` where any line ends so, else `\\n`."""
    return text.replace("\r\n", "\n"), "\r\n" if "\r\n" in text else "\n"


def write(path, text, newline):
    """Write `text` to `path` as UTF-8, each `\\n` in it as `newline`."""
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        f.write(text.replace("\n", newline))

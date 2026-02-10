"""CLI entrypoint for EUR-Lex downloader."""

from eurlex_unit_parser.download.eurlex import main

__all__ = ["main"]


if __name__ == "__main__":
    main()

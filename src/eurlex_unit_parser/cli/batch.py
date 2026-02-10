"""CLI entrypoint for batch processing."""

from eurlex_unit_parser.batch.runner import main

__all__ = ["main"]


if __name__ == "__main__":
    main()

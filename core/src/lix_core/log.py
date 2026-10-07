"""Console logging with one consistent format."""

import logging

ROOT = "lix"


def setup_logging(name: str) -> logging.Logger:
    """Return the ``lix.{name}`` logger.

    One handler lives on the shared ``lix`` parent, so nested names (``stage`` and
    ``stage.iod``) never print a line twice and records still propagate to the root
    logger (where pytest's caplog listens).
    """
    parent = logging.getLogger(ROOT)
    if not parent.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
        )
        parent.addHandler(handler)
        parent.setLevel(logging.INFO)
    return logging.getLogger(f"{ROOT}.{name}")

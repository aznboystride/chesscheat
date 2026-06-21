"""The ``ImageBackend`` interface."""

from abc import ABC, abstractmethod


class ImageBackend(ABC):
    """Low-level square operations, abstracting the image representation.

    Splitting these out lets the recognition *algorithm* be shared between a
    real numpy/array backend and a pure-Python mock backend.
    """

    @abstractmethod
    def get_square(self, image, row, col):
        """Crop one square's comparable region from a board image.

        Args:
            image: A full board image from a ``FrameSource``.
            row: Screen grid row, 0 at the top.
            col: Screen grid column, 0 at the left.

        Returns:
            The cropped square region, in the backend's image representation.
        """

    @abstractmethod
    def feature(self, patch):
        """Reduce a square crop to a comparable feature.

        Args:
            patch: A square region from ``get_square``.

        Returns:
            A feature value comparable via ``similarity``.
        """

    @abstractmethod
    def similarity(self, feature_a, feature_b):
        """Score how alike two features are.

        Args:
            feature_a: A feature from ``feature``.
            feature_b: Another feature from ``feature``.

        Returns:
            A similarity score where higher means more alike.
        """

    @abstractmethod
    def recolor(self, patch, from_empty, to_empty):
        """Repaint a square's background from one empty colour to another.

        Used to synthesise how a piece would look on a square of the opposite
        colour from how it looks on its calibration square: background pixels
        (those matching ``from_empty``) are repainted with ``to_empty`` while
        the piece's own pixels are kept. Relies on the assumptions that empty
        squares of a colour are uniform and a piece composites over them
        identically everywhere.

        Args:
            patch: A square crop containing a piece on a ``from_empty`` square.
            from_empty: A crop of an empty square of the piece's current colour.
            to_empty: A crop of an empty square of the target colour.

        Returns:
            A patch of the same form as ``patch`` with the background repainted.
        """


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

"""The ``MockImageBackend`` image backend."""

import math

from chesscheat.interfaces import ImageBackend


class MockImageBackend(ImageBackend):
    """Pure-Python backend matching synthetic images by normalised correlation.

    Mirrors ``NumpyImageBackend``'s maths on plain lists of ints, so the same
    ``TemplateBoardRecognizer`` algorithm can be tested without numpy.

    Attributes:
        margin: Fraction trimmed from each side of a square before matching.
    """

    def __init__(self, margin=0.0):
        """Initialise the backend.

        Args:
            margin: Fraction trimmed from each side of a square; 0 keeps the
                whole square (synthetic squares have no borders to drop).
        """
        self.margin = margin

    def get_square(self, image, row, col):
        """Crop one square from a synthetic image.

        Args:
            image: A board image as a list of lists of ints.
            row: Screen grid row, 0 at the top.
            col: Screen grid column, 0 at the left.

        Returns:
            The cropped square as a list of lists of ints.
        """
        cell = len(image) // 8
        m = int(cell * self.margin)
        return [r[col * cell + m:(col + 1) * cell - m]
                for r in image[row * cell + m:(row + 1) * cell - m]]

    def feature(self, patch):
        """Reduce a square to a mean-subtracted, unit-normalised vector.

        Args:
            patch: A square crop as a list of lists of ints.

        Returns:
            A tuple of floats; normalising makes ``similarity`` a correlation
            coefficient. A flat patch yields an all-zero tuple.
        """
        flat = [v for r in patch for v in r]
        mean = sum(flat) / len(flat)
        centered = [v - mean for v in flat]
        norm = math.sqrt(sum(v * v for v in centered))
        return tuple(v / norm for v in centered) if norm else tuple(centered)

    def similarity(self, feature_a, feature_b):
        """Return the normalised cross-correlation of two features.

        Args:
            feature_a: A tuple from ``feature``.
            feature_b: Another tuple from ``feature``.

        Returns:
            The dot product as a float; in ``[-1, 1]`` for unit-normalised
            features.
        """
        return sum(x * y for x, y in zip(feature_a, feature_b))

    def recolor(self, patch, from_empty, to_empty, tol=0):
        """Repaint background pixels from one empty value to another.

        Synthetic mock pieces fully replace their square rather than
        compositing over it, so there are usually no background pixels to
        repaint; this is provided for interface completeness and mirrors the
        real backend's average-colour swap.

        Args:
            patch: A square crop as a list of lists of ints.
            from_empty: An empty-square crop of the current colour.
            to_empty: An empty-square crop of the target colour.
            tol: Max absolute distance to the source value to count as
                background.

        Returns:
            A list of lists of ints with background values repainted.
        """
        def avg(cell):
            flat = [v for row in cell for v in row]
            return sum(flat) / len(flat)

        from_value, to_value = avg(from_empty), avg(to_empty)
        return [[to_value if abs(v - from_value) <= tol else v for v in row]
                for row in patch]

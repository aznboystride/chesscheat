"""The ``TemplateBoardRecognizer`` board recognizer."""

from chesscheat import board
from chesscheat.interfaces import BoardRecognizer


class TemplateBoardRecognizer(BoardRecognizer):
    """Recognise a board by matching squares against calibrated templates.

    Calibration captures one template per square from the starting position
    (so every piece type and empty square gets a reference); ``read`` then
    classifies each square by nearest template. The algorithm is delegated to
    an ``ImageBackend``, so it runs identically with the real numpy backend and
    the pure-Python mock backend.

    Attributes:
        backend: The ``ImageBackend`` used for cropping and matching.
        playing_white: Perspective captured at calibration time.
        templates: List of ``(label, feature)`` pairs, one per starting square.
    """

    def __init__(self, backend):
        """Initialise the recognizer.

        Args:
            backend: An ``ImageBackend`` implementation used to crop squares
                and score template similarity.
        """
        self.backend = backend
        self.playing_white = True
        self.templates = []  # list of (label, feature)

    def calibrate(self, image, playing_white):
        """Capture one template per square from the starting position.

        Every piece type and empty square appears in the starting position, so
        this yields a reference feature for each.

        Args:
            image: A board image showing the standard starting position.
            playing_white: True if the board is shown from white's
                perspective, False for black's.
        """
        self.playing_white = playing_white
        self.templates = [
            (board.start_label(*board.square_coord(row, col, playing_white)),
             self.backend.feature(self.backend.get_square(image, row, col)))
            for row in range(8) for col in range(8)
        ]

    def read(self, image):
        """Classify every square of an image by nearest calibrated template.

        Args:
            image: A board image to recognise.

        Returns:
            A ``{(file_idx, rank): label}`` map of all 64 squares.
        """
        def classify(row, col):
            feat = self.backend.feature(self.backend.get_square(image, row, col))
            label, _ = max(
                self.templates,
                key=lambda t: self.backend.similarity(feat, t[1]),
            )
            return board.square_coord(row, col, self.playing_white), label

        return dict(classify(row, col)
                    for row in range(8) for col in range(8))

"""The ``TemplateBoardRecognizer`` board recognizer."""

from chesscheat import board
from chesscheat.interfaces import BoardRecognizer


class TemplateBoardRecognizer(BoardRecognizer):
    """Recognise a board by matching squares against calibrated templates.

    The recognizer infers, from a single starting-position image, how each
    piece and each empty square looks, then extrapolates to any later
    configuration. It relies only on these properties of the board (not on
    pieces resembling anything in particular):

    - squares are evenly spaced, so each cell is one eighth of the board;
    - a colour's squares look identical everywhere;
    - a given piece looks identical on every square it occupies.

    Matching is **colour-aware**: a square's colour is known from its
    coordinates, so a square is only compared against templates for that
    colour. Because the starting position shows kings and queens on a single
    colour, the missing piece-on-opposite-colour templates are **synthesised**
    from the calibration image (repainting the background via the backend's
    ``recolor``), so every piece can be recognised on either colour.

    Attributes:
        backend: The ``ImageBackend`` used for cropping, matching and recolour.
        playing_white: Perspective captured at calibration time.
        templates: Dict mapping ``(label, is_light)`` to a feature.
    """

    def __init__(self, backend):
        """Initialise the recognizer.

        Args:
            backend: An ``ImageBackend`` implementation used to crop squares,
                score template similarity and synthesise opposite-colour
                templates.
        """
        self.backend = backend
        self.playing_white = True
        self.templates = {}  # (label, is_light) -> feature

    def calibrate(self, image, playing_white):
        """Learn how each piece and empty square looks from the start position.

        Captures one template per ``(label, square colour)`` seen, then
        synthesises any piece-on-opposite-colour template that the starting
        position did not show (e.g. king/queen on the colour they do not start
        on) by repainting the background to the other empty colour.

        Args:
            image: A board image showing the standard starting position.
            playing_white: True if the board is shown from white's
                perspective, False for black's.
        """
        self.playing_white = playing_white

        patches = {}   # (label, is_light) -> patch
        empties = {}   # is_light -> empty-square patch
        for row in range(8):
            for col in range(8):
                file_rank = board.square_coord(row, col, playing_white)
                label = board.start_label(*file_rank)
                light = board.is_light(*file_rank)
                patch = self.backend.get_square(image, row, col)
                patches.setdefault((label, light), patch)
                if label == ".":
                    empties[light] = patch

        templates = {key: self.backend.feature(patch)
                     for key, patch in patches.items()}

        # Synthesise each piece on the colour the start position did not show.
        for (label, light), patch in list(patches.items()):
            other = not light
            if label == "." or (label, other) in templates:
                continue
            if light in empties and other in empties:
                synthesised = self.backend.recolor(patch, empties[light],
                                                   empties[other])
                templates[(label, other)] = self.backend.feature(synthesised)

        self.templates = templates

    def read(self, image):
        """Classify every square against same-colour templates.

        Args:
            image: A board image to recognise.

        Returns:
            A ``{(file_idx, rank): label}`` map of all 64 squares.
        """
        def classify(row, col):
            file_rank = board.square_coord(row, col, self.playing_white)
            light = board.is_light(*file_rank)
            feat = self.backend.feature(self.backend.get_square(image, row, col))
            candidates = ((label, feature)
                          for (label, tint), feature in self.templates.items()
                          if tint == light)
            label, _ = max(
                candidates,
                key=lambda lf: self.backend.similarity(feat, lf[1]),
            )
            return file_rank, label

        return dict(classify(row, col)
                    for row in range(8) for col in range(8))

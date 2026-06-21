"""chesscheat -- read a chessboard off the screen and print its state.

The package is layered behind the interfaces in ``chesscheat.interfaces``:

- ``board``       -- pure logic (coordinates, labels, rendering, FEN).
- ``interfaces``  -- the abstract contracts the app depends on.
- ``recognition`` -- the template-matching recognizer + numpy backend.
- ``providers``   -- real setup (GUI/prompt) and screen frame source.
- ``mocks``       -- dependency-free fakes for testing.
- ``capture``     -- fast screen capture.
- ``gui``         -- tkinter setup dialogs.
- ``app``         -- the ``run`` loop and ``main`` entry point.
"""

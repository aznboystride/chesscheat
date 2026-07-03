"""The ``PromptSetupProvider`` setup provider."""

from chesscheat.interfaces import SetupProvider


class PromptSetupProvider(SetupProvider):
    """Plain text prompts on stdin/stdout."""

    def select_side(self):
        """Prompt for the side on stdin, repeating until valid.

        Returns:
            True for white, False for black.
        """
        while True:
            side = input("Are you playing white or black? (w/b): ").strip().lower()
            if side in ("w", "white"):
                return True
            if side in ("b", "black"):
                return False
            print("  Please answer 'w' or 'b'.")

    def select_box(self):
        """Prompt for two corner coordinates on stdin.

        Returns:
            The normalised bounding box as ``(x1, y1, x2, y2)``.
        """
        def ask(label):
            while True:
                try:
                    x, y = input(f"Enter {label} corner as 'x y': ").split()
                    return int(x), int(y)
                except ValueError:
                    print("  Please enter two integers separated by a space.")

        x1, y1 = ask("top-left")
        x2, y2 = ask("bottom-right")
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def confirm_box(self, image, playing_white=True):
        """Report the capture's dimensions and ask y/n to proceed.

        A terminal cannot display the capture itself, so the user is told its
        pixel size and asked to confirm.

        Args:
            image: The frame captured from the selected bounding box.
            playing_white: Unused; a terminal shows no annotations.

        Returns:
            True to proceed with this region, False to select it again.
        """
        height = len(image)
        width = len(image[0]) if height else 0
        while True:
            answer = input(f"Captured a {width}x{height} region of the screen."
                           " Proceed? (y/n): ").strip().lower()
            if answer in ("y", "yes"):
                return True
            if answer in ("n", "no"):
                return False
            print("  Please answer 'y' or 'n'.")

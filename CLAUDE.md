# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A single-file (`chess_cheat.py`) screen-scraping toolkit that reads a chess.com
game from the macOS screen and drives the mouse to play moves. It captures
screen regions, OCRs move notation, recognizes pieces by image similarity, and
maps chess coordinates to on-screen pixels.

## Running

```bash
python3 chess_cheat.py
```

There is no build, test, or lint setup — execution is driven by the
module-level code at the bottom of `chess_cheat.py`. To change what runs,
edit/uncomment that bottom block (most of the experiments are left commented
as a record of usage). The file currently ends by calling
`PieceMover().move("h7", "h6")`.

### Dependencies

Requires `numpy`, `opencv-python` (cv2), `mss`, `Pillow`, `pytesseract`,
`pyautogui`, `python-chess`, and `scikit-image`, plus the native `tesseract`
binary. There is no requirements file; install manually.

## Critical environment assumptions

This code is hard-wired to one specific machine/display and will not work
elsewhere without editing constants:

- **Screen pixel coordinates are hardcoded.** Board corners live in
  `FullScreenBoardCornerDetector` (top-left `191,173` … bottom-right `793,774`)
  and the move-list region in `NotationCornerDetector`. These are absolute
  pixels for a particular chess.com window layout and resolution.
- **Player color is hardcoded.** `WhiteOrBlackDetector1.isBlack()` always
  returns `True`. This flips the coordinate mapping in
  `ChessPositionTo2DPointMapper`, so playing as white requires changing this.
- **Absolute filesystem paths** to the tesseract binary
  (`NotationInterpreter`) and the reference piece images
  (`/Users/fair/Downloads/chesspieces`, used by the `PieceImageInterpreter*`
  classes) are macOS-specific.
- **macOS-specific input.** `ScreenSwitch` uses the `command` key for app
  switching.

## Architecture

Everything is built from small single-responsibility classes, most behind an
`ABC` interface so implementations can be swapped. The data flow has three
stages:

1. **Screen capture → image.** `ImageReader` (wrapping `mss`) grabs a screen
   region described by a `Corner` (four `Point`s). `CornerPropertyReader`
   converts a `Corner` into the `top/left/width/height` bounding box that
   capture and cropping need. `*CornerDetector` classes supply the regions.

2. **Image → meaning.** Two independent recognition paths:
   - *Move-list OCR:* `RowNotationReader` slices the notation region into rows;
     `WhiteMoveReader`/`BlackMoveReader` take the left/right half of a row;
     `NotationInterpreter` / `TesseractWrapper` run tesseract on the crop.
   - *Board piece recognition:* `PieceImageExtractor` crops a single square
     (via the coordinate mapper), and the `PieceImageInterpreter*` classes
     compare it against the reference piece images using SSIM
     (`PieceImageInterpreterSsimColored`/`SsimGrayScale`) or Canny-edge SSIM
     (`PieceImageInterpreterEdgeSimilarity`).

3. **Coordinate mapping → mouse action.** `ChessPositionTo2DPointMapper`
   converts algebraic positions like `"e4"` to board grid `Point`s, accounting
   for board orientation via the white/black detector. `PieceMover` maps two
   positions and `MouseDragger` (a `MouseMover`) drags the piece with
   `pyautogui`.

### Key coupling to know

The `Point` class is overloaded: it represents both **absolute screen pixels**
(corners, capture boxes) and **0–7 board grid indices** (mapper output). Note
that `PieceMover.move` passes grid-index Points straight to `MouseDragger`,
which treats them as pixels — coordinate spaces are not consistently
reconciled, so changes here need care.

`Game`/`InteractiveGame`/`UciGame` sketch a turn loop but are not the active
entry point; the live behavior is the module-level script at the bottom of the
file.

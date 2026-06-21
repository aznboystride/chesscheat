# Test fixtures

## `pieces/`

The classic Wikipedia chess piece set (PNG), downloaded from the chessboard.js
project:

> https://raw.githubusercontent.com/oakmac/chessboardjs/master/website/img/chesspieces/wikipedia/

These pieces are the standard public-domain Wikipedia set. chessboard.js itself
is MIT licensed.

## `boards/`

Real board images for a short opening that evolves over time — `start.png`,
`e4.png`, `c5.png`, `nf3.png` (the line 1.e4 c5 2.Nf3) — composed by pasting the
real pieces above onto a standard two-tone board. Used by
`tests/test_real_images.py` to verify the recognizer recovers each position.

## Regenerating

```bash
pip install -r requirements-dev.txt
python3 tests/fixtures/generate_boards.py
```

(Re-run only if the fixtures need to change; the generated boards are committed.)

# Test fixtures

## `pieces/<set>/`

Real chess piece sets pulled from the web, one folder each:

- **`wikipedia`** and **`alpha`** — PNGs from the chessboard.js project:
  > https://raw.githubusercontent.com/oakmac/chessboardjs/master/website/img/chesspieces/
  The Wikipedia set is the standard public-domain set; chessboard.js is MIT
  licensed.
- **`merida`** — lichess's SVG set, rasterised to 80×80 PNG with `cairosvg`:
  > https://raw.githubusercontent.com/lichess-org/lila/master/public/piece/merida/
  lichess piece sets are GPL/CC licensed (see the lila repository).

## `boards/<set>/`

Real board images for a short opening that evolves over time — `start.png`,
`e4.png`, `c5.png`, `nf3.png` (the line 1.e4 c5 2.Nf3) — for each piece set,
composed by pasting that set's pieces onto a per-set colour theme (brown for
`wikipedia`, green for `alpha`, blue/grey for `merida`). Used by
`tests/test_real_images.py`, which recognises every position for every set.

## Regenerating

The board images are committed, so this is only needed when changing fixtures.

Re-fetch the piece artwork (needs network + `cairosvg` for merida):

```bash
pieces=(wK wQ wR wB wN wP bK bQ bR bB bN bP)
for s in wikipedia alpha; do
  for p in "${pieces[@]}"; do
    curl -sSo tests/fixtures/pieces/$s/$p.png \
      "https://raw.githubusercontent.com/oakmac/chessboardjs/master/website/img/chesspieces/$s/$p.png"
  done
done
for p in "${pieces[@]}"; do
  curl -sSo /tmp/$p.svg \
    "https://raw.githubusercontent.com/lichess-org/lila/master/public/piece/merida/$p.svg"
  python3 -c "import cairosvg,sys; cairosvg.svg2png(url='/tmp/$p.svg', \
    write_to='tests/fixtures/pieces/merida/$p.png', output_width=80, output_height=80)"
done
```

Then rebuild the boards:

```bash
pip install -r requirements-dev.txt
python3 tests/fixtures/generate_boards.py
```

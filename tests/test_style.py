"""Playing styles: the pure chooser, the move heuristics, the book engine
and the styled search path of the local engine (fake UCI engine)."""

import os
import random
import struct
import sys
import tempfile
import unittest

try:
    import chess
    import chess.polyglot
    _HAVE_CHESS = True
except ImportError:
    _HAVE_CHESS = False

from chesscheat import board
from chesscheat.assist import (STYLES, choose_move, eligible_moves,
                               aggression, solidity, BookMoveEngine)
from chesscheat.interfaces import MoveEngine
from chesscheat.mocks import MockMoveEngine

FAKE_ENGINE = os.path.join(os.path.dirname(__file__), "fixtures",
                           "fake_uci_engine.py")
# 1.e4 e5 2.Nf3 Nc6: white to move.
ITALIAN_FEN = "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 2 3"
START_FEN = board.to_full_fen(board.starting_board(), True)


class EligibilityTests(unittest.TestCase):
    """Only lines within the margin of the best qualify (dep-free)."""

    def test_margin_filters_and_keeps_order(self):
        candidates = [("a", 50), ("b", 30), ("c", 15), ("d", -100)]
        self.assertEqual(eligible_moves(candidates, 35),
                         [("a", 50), ("b", 30), ("c", 15)])
        self.assertEqual(eligible_moves(candidates, 20),
                         [("a", 50), ("b", 30)])
        self.assertEqual(eligible_moves(candidates, 0), [("a", 50)])
        self.assertEqual(eligible_moves([], 30), [])

    def test_best_style_and_unknown_styles_take_the_top_line(self):
        candidates = [("a", 50), ("b", 40)]
        self.assertEqual(choose_move(candidates, "best", "fen"), "a")
        self.assertEqual(choose_move(candidates, "whatever", "fen"), "a")
        self.assertIsNone(choose_move([], "unusual", "fen"))
        self.assertEqual(STYLES, ("best", "aggressive", "solid", "unusual"))

    def test_unusual_avoids_the_top_line_when_it_can(self):
        candidates = [("a", 50), ("b", 40), ("c", 30), ("d", -500)]
        self.assertEqual(choose_move(candidates, "unusual", "fen", 30,
                                     rng=lambda: 0.0), "b")
        self.assertEqual(choose_move(candidates, "unusual", "fen", 30,
                                     rng=lambda: 0.99), "c")
        # Alone within the margin: the best line it is.
        self.assertEqual(choose_move(candidates, "unusual", "fen", 5), "a")


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class HeuristicTests(unittest.TestCase):
    """Aggression and solidity read the move's character."""

    def test_captures_and_checks_are_aggressive(self):
        quiet, capture = aggression(ITALIAN_FEN, "b1c3"), aggression(
            ITALIAN_FEN, "f3e5")
        self.assertGreater(capture, quiet)
        check_fen = "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2"
        self.assertGreater(aggression(check_fen, "d1h5"),   # eyes f7, forward
                           aggression(check_fen, "b1c3"))
        self.assertGreater(aggression(check_fen, "f1c4"),   # towards the king
                           aggression(check_fen, "a2a3"))

    def test_castling_and_development_are_solid(self):
        fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
        self.assertGreater(solidity(fen, "e1g1"), solidity(fen, "f3e5"))
        self.assertGreater(solidity(fen, "b1c3"), solidity(fen, "d1e2"))
        self.assertLess(aggression(fen, "e1g1"), aggression(fen, "f3e5"))
        self.assertLess(solidity(fen, "e1e2"), solidity(fen, "a2a3"))

    def test_styles_pick_by_character_within_the_margin(self):
        candidates = [("b1c3", 40), ("f3e5", 35), ("f1c4", 30), ("a2a3", -50)]
        self.assertEqual(choose_move(candidates, "aggressive", ITALIAN_FEN, 30),
                         "f3e5")
        self.assertEqual(choose_move(candidates, "solid", ITALIAN_FEN, 30),
                         "b1c3")
        # The capture is outside a tight margin.
        self.assertEqual(choose_move(candidates, "aggressive", ITALIAN_FEN, 2),
                         "b1c3")


def _polyglot_move(uci):
    """Encode a UCI move the Polyglot way (no promotion)."""
    frm, to = chess.parse_square(uci[:2]), chess.parse_square(uci[2:4])
    return (chess.square_file(to) | chess.square_rank(to) << 3
            | chess.square_file(frm) << 6 | chess.square_rank(frm) << 9)


def _write_book(path, entries):
    """Write a Polyglot book: ``[(fen, uci, weight)]``, sorted by key."""
    rows = sorted((chess.polyglot.zobrist_hash(chess.Board(fen)),
                   _polyglot_move(uci), weight)
                  for fen, uci, weight in entries)
    with open(path, "wb") as f:
        for key, move, weight in rows:
            f.write(struct.pack(">QHHI", key, move, weight, 0))


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class BookEngineTests(unittest.TestCase):
    """``BookMoveEngine`` plays from the book, then defers to the engine."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = os.path.join(self.dir.name, "book.bin")
        _write_book(self.path, [(START_FEN, "e2e4", 100),
                                (START_FEN, "b2b3", 1)])
        self.inner = MockMoveEngine("g1f3")
        self.engine = BookMoveEngine(self.inner, self.path,
                                     rng=random.Random(1))
        self.addCleanup(self.engine.close)

    def test_in_book_the_weighted_choice_is_played(self):
        picks = {self.engine.best_move(START_FEN) for _ in range(30)}
        self.assertTrue(picks <= {"e2e4", "b2b3"})
        self.assertIn("e2e4", picks)                 # weight 100 dominates
        self.assertEqual(self.inner.seen_fens, [])   # engine not consulted

    def test_unusual_style_plays_the_rarest_line(self):
        self.engine.set_style("unusual", 0.4)
        self.assertEqual(self.engine.best_move(START_FEN), "b2b3")
        self.assertEqual(self.inner.styles, [("unusual", 0.4)])

    def test_out_of_book_the_engine_decides(self):
        after_e4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
        self.assertEqual(self.engine.best_move(after_e4), "g1f3")
        self.assertEqual(self.inner.seen_fens, [after_e4])

    def test_settings_and_evaluation_are_forwarded(self):
        self.inner.score = {"cp": 12}
        self.engine.set_strength(1500)
        self.engine.set_think_time(0.2)
        self.assertEqual(self.engine.evaluate(START_FEN), {"cp": 12})
        self.assertEqual(self.inner.strengths, [1500])
        self.assertEqual(self.inner.think_times, [0.2])
        self.assertIsInstance(self.engine, MoveEngine)


@unittest.skipUnless(_HAVE_CHESS, "requires python-chess")
class StyledSearchTests(unittest.TestCase):
    """The local engine fetches several lines and chooses by style."""

    def _engine(self):
        from chesscheat.assist import StockfishMoveEngine

        engine = StockfishMoveEngine(path=[sys.executable, FAKE_ENGINE],
                                     think_time=0.01, eval_time=0.01)
        self.addCleanup(engine.close)
        return engine

    def test_best_style_plays_the_first_line(self):
        engine = self._engine()
        first = engine.best_move(START_FEN)
        engine.set_style("best", 1.0)
        self.assertEqual(engine.best_move(START_FEN), first)

    def test_unusual_style_avoids_the_first_line(self):
        engine = self._engine()
        first = engine.best_move(START_FEN)
        engine.set_style("unusual", 1.0)           # all five lines qualify
        pick = engine.best_move(START_FEN)
        self.assertNotEqual(pick, first)
        self.assertIn(chess.Move.from_uci(pick), chess.Board().legal_moves)
        engine.set_style("unusual", 0.0)           # only the first qualifies
        self.assertEqual(engine.best_move(START_FEN), first)

    def test_aggressive_style_prefers_the_capture_among_the_lines(self):
        engine = self._engine()
        engine.set_style("aggressive", 1.0)
        # The fake offers the first five legal moves; in this position one
        # of them is the capture Nxe5, which aggression ranks highest.
        pick = engine.best_move(ITALIAN_FEN)
        first_five = [m.uci() for m in list(chess.Board(ITALIAN_FEN)
                                            .legal_moves)[:5]]
        self.assertIn(pick, first_five)
        self.assertEqual(aggression(ITALIAN_FEN, pick),
                         max(aggression(ITALIAN_FEN, m) for m in first_five))

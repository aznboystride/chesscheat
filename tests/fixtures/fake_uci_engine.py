"""A minimal UCI engine for tests, so engine clients run without Stockfish.

Speaks just enough of the protocol for python-chess: ``uci`` (advertising
``UCI_LimitStrength``/``UCI_Elo`` so strength options are exercised),
``isready``, ``setoption`` (recorded), ``position``, ``go`` and ``quit``.
Every search answers with the first legal move and an ``info score cp``
that encodes what it was told: ``+37`` at full strength, ``-37`` while
strength is limited (so a client can check which it asked for), from the
side to move's point of view as UCI requires. ``go`` with ``crash`` in the
command line arguments kills the process instead, to test recovery.

Run as ``python3 fake_uci_engine.py [crash]``.
"""

import sys

import chess


def main(argv):
    """Serve UCI on stdin/stdout until ``quit``.

    Args:
        argv: Command-line arguments; ``"crash"`` makes the first ``go``
            exit abruptly.
    """
    board = chess.Board()
    limited = False
    crash = "crash" in argv
    out = sys.stdout

    def say(line):
        out.write(line + "\n")
        out.flush()

    for raw in sys.stdin:
        parts = raw.split()
        if not parts:
            continue
        command = parts[0]
        if command == "uci":
            say("id name FakeUCI")
            say("option name UCI_LimitStrength type check default false")
            say("option name UCI_Elo type spin default 1320 min 1320 max 3190")
            say("uciok")
        elif command == "isready":
            say("readyok")
        elif command == "setoption":
            if parts[2] == "UCI_LimitStrength":
                limited = parts[4] == "true"
        elif command == "ucinewgame":
            board = chess.Board()
        elif command == "position":
            if parts[1] == "startpos":
                board = chess.Board()
                moves = parts[3:]
            else:
                end = parts.index("moves") if "moves" in parts else len(parts)
                board = chess.Board(" ".join(parts[2:end]))
                moves = parts[end + 1:]
            for uci in moves:
                board.push_uci(uci)
        elif command == "go":
            if crash:
                sys.exit(3)
            move = next(iter(board.legal_moves), None)
            cp = -37 if limited else 37
            say(f"info depth 1 score cp {cp} pv {move.uci() if move else ''}")
            say(f"bestmove {move.uci() if move else '(none)'}")
        elif command == "quit":
            return


if __name__ == "__main__":
    main(sys.argv[1:])

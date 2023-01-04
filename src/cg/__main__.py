from __future__ import annotations

import curses
import os.path
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

## print(something, file=DEBUG_FILE) anywhere to retrieve values
DEBUG_FILE = open("debug.txt", "w")
##


CHUNK_WIDTH = CHUNK_HEIGHT = 32
CHUNK_X_RANGE = range(65, 91)
CHUNK_Y_RANGE = range(1, 10)

# 'A' -> 'Z'
VALID_CHUNK_POS_X = list(map(chr, CHUNK_X_RANGE))
# '1' -> '9'
VALID_CHUNK_POS_Y = list(map(str, CHUNK_Y_RANGE))

# 'A1' -> 'Z9'
VALID_CHUNK_NAME = [CPX + CPY for CPY in VALID_CHUNK_POS_Y for CPX in VALID_CHUNK_POS_X]


WALLS = {"&"}
DOORS = list(map(str, range(10)))


# for further hitbox implementation
class Direction(Enum):
    Up = 0
    Down = 1
    Left = 2
    Right = 3


class Chunk:
    def __init__(self, raw: str, x: int, y: int) -> None:
        self.raw: str = raw
        self.matrix: list[list[str]] = make_matrix(self.raw)
        self.pos = self.x, self.y = x, y

        # Useful if I mess up a chunk file lol
        if self.is_invalid():
            raise ValueError(f"chunk size must be {CHUNK_WIDTH}x{CHUNK_HEIGHT}")

    def is_invalid(self) -> bool:
        return len(self.matrix) != CHUNK_HEIGHT or any(
            len(row) != CHUNK_WIDTH for row in self.matrix
        )

    def is_wall_at(self, x: int, y: int) -> bool:
        return self.matrix[y][x] in WALLS

    def get_door_at(self, x: int, y: int) -> str | None:
        if not self.matrix[y][x] in DOORS:
            return None
        return self.matrix[y][x]

    def get_door_pos(self, door: str) -> list[tuple[int, int]]:
        return [
            (x, y)
            for y, row in enumerate(self.matrix)
            for x, cell in enumerate(row)
            if cell == door
        ]

    def get_entrances(self) -> dict[str, list[DoorEntrance]]:
        return {door: [DoorEntrance(self, x, y) for x, y in self.get_door_pos(door)] for door in DOORS}

    def print(self, stdscr: curses.window, player_x: int, player_y: int) -> None:
        stdscr.move(0, 0)

        max_x, max_y = get_terminal_size()
        center_x, center_y = max_x // 2, max_y // 2

        for rel_y, row in enumerate(self.matrix):
            for rel_x, cell in enumerate(row):
                abs_x = center_x - player_x + (CHUNK_WIDTH * self.x) + rel_x
                abs_y = center_y - player_y + (CHUNK_HEIGHT * self.y) + rel_y
                if 0 <= abs_x < (max_x - 1) and 0 <= abs_y < (max_y - 1):
                    stdscr.addch(abs_y, abs_x, cell)

    @classmethod
    def from_file(cls, path: str):
        file_name = os.path.basename(path)

        if not is_valid_chunk_file_name(file_name):
            raise ValueError(f"invalid chunk file name")

        if not os.path.exists(path):
            raise FileNotFoundError(f"could not load chunk from path {path!r}")

        with open(path, "r") as chunk_file:
            raw = chunk_file.read()

        str_x, str_y = file_name
        x, y = ord(str_x) - 64, int(str_y)

        return cls(raw, x - 1, y - 1)

    # For rich comparison support

    def __gt__(self, other: Chunk) -> bool:
        return self.pos > other.pos

    def __lt__(self, other: Chunk) -> bool:
        return self.pos < other.pos


@dataclass
class DoorEntrance:
    chunk: Chunk
    x: int
    y: int


DoorPipeDict = dict[str, list[DoorEntrance]]


class Player:
    walk_speed = 1
    run_speed = 2

    def __init__(self, char: str, *, x: int = 1, y: int = 1) -> None:
        self.char = char
        self.pos = self.x, self.y = x, y
        self.speed = Player.walk_speed

        if self.x <= 0 or self.y <= 0:
            raise ValueError("Player coordinates must be strictly positive")

    def walk(self) -> None:
        self.speed = Player.walk_speed

    def run(self) -> None:
        self.speed = Player.run_speed

    def go_left(self) -> None:
        self.x -= self.speed

    def go_right(self) -> None:
        self.x += self.speed

    def go_up(self) -> None:
        self.y -= self.speed

    def go_down(self) -> None:
        self.y += self.speed

    def teleport(self, entrance: DoorEntrance) -> None:
        x = entrance.chunk.x * CHUNK_WIDTH + entrance.x
        y = entrance.chunk.y * CHUNK_HEIGHT + entrance.y
        self.x, self.y = x, y

    def move(self, x: int, y: int) -> None:
        self.x, self.y = x, y

    def print(self, stdscr: curses.window) -> None:
        cx, cy = get_terminal_center()
        stdscr.move(cy, cx)
        stdscr.addch(self.char)


class Map:
    def __init__(self, chunks: list[Chunk], player: Player) -> None:
        self.matrix: list[list[Chunk | None]] = dispatch_chunks(chunks)
        self.player: Player = player
        self.doors_entrances: DoorPipeDict = find_door_pipes(chunks)

    def move(
        self,
        action: Callable[[], None],
        *,
        dx: int = 0,
        dy: int = 0,
        player_run: bool = False,
    ) -> None:

        if player_run:
            self.player.run()

        move_speed = self.player.speed
        self.player.walk()

        for _ in range(move_speed):
            chunk_x, x = divmod(self.player.x + dx, CHUNK_WIDTH)
            chunk_y, y = divmod(self.player.y + dy, CHUNK_HEIGHT)

            player_chunk = self.matrix[chunk_y][chunk_x]

            if player_chunk is None:
                raise RuntimeError("player is in the void")

            if (door := player_chunk.get_door_at(x, y)) is not None:
                next_entrance = self.get_next_entrance(player_chunk, x, y, door)
                c = next_entrance.chunk
                print(c.x, c.y, file=DEBUG_FILE)
                self.player.teleport(next_entrance)

            elif not player_chunk.is_wall_at(x, y):
                action()

    def move_left(self, *, player_run: bool = False) -> None:
        self.move(self.player.go_right, dx=1, player_run=player_run)

    def move_right(self, *, player_run: bool = False) -> None:
        self.move(self.player.go_left, dx=-1, player_run=player_run)

    def move_up(self, *, player_run: bool = False) -> None:
        self.move(self.player.go_down, dy=1, player_run=player_run)

    def move_down(self, *, player_run: bool = False) -> None:
        self.move(self.player.go_up, dy=-1, player_run=player_run)

    def get_visible_chunks(self) -> list[Chunk]:
        return [chunk for row in self.matrix for chunk in row if chunk is not None]

        ## KEEPING THIS CODE IN CASE OF PERFORMANCE ISSUES
        # ix, iy = self.player.x // CHUNK_WIDTH, self.player.y // CHUNK_HEIGHT
        # return slice_matrix(self.matrix, ix, iy)
        ##

    def get_next_entrance(
        self,
        chunk: Chunk,
        x: int,
        y: int,
        door: str,
    ) -> DoorEntrance:
        current_entrance = DoorEntrance(chunk, x, y)
        entrances = self.doors_entrances[door]
        for i, entrance in enumerate(entrances):
            if entrance == current_entrance:
                return entrances[(i + 1) % len(entrances)]

        raise ValueError("door has only one entrance")

    def print(self, stdscr: curses.window) -> None:
        visible_chunks = self.get_visible_chunks()
        for chunk in visible_chunks:
            chunk.print(stdscr, self.player.x, self.player.y)

    @classmethod
    def load(cls, player: Player, *skip_chunks: str):
        chunks_dir = os.path.join(os.path.dirname(__file__), "chunks")
        chunks: list[Chunk] = []

        for chunk_name in VALID_CHUNK_NAME:
            if chunk_name in skip_chunks:
                continue

            chunk_path = os.path.join(chunks_dir, chunk_name)
            if os.path.exists(chunk_path):
                if (chunk := Chunk.from_file(chunk_path)) in chunks:
                    raise ValueError(f"found duplicate {chunk_name!r}")
                chunks.append(chunk)

        return cls(chunks, player)


# *- UTILS -* #


def make_matrix(raw: str) -> list[list[str]]:
    return list(map(list, raw.splitlines()))


def dispatch_chunks(chunks: list[Chunk]) -> list[list[Chunk | None]]:
    chunk_matrix: list[list[Chunk | None]] = [
        [None for _ in CHUNK_X_RANGE] for _ in CHUNK_Y_RANGE
    ]

    for chunk in chunks:
        chunk_matrix[chunk.y][chunk.x] = chunk

    return chunk_matrix


def find_door_pipes(chunks: list[Chunk]) -> DoorPipeDict:
    door_pipes: DoorPipeDict = {door: [] for door in DOORS}

    for chunk in chunks:
        for door, entrances in chunk.get_entrances().items():
            door_pipes[door].extend(entrances)

    return door_pipes


def slice_matrix(
    chunk_matrix: list[list[Chunk | None]],
    cx: int,
    cy: int,
) -> list[Chunk]:
    # NOTE: This function is not used anymore, but might be in the future
    # if performance issues occur

    chunks: list[Chunk] = []
    max_x, max_y = get_terminal_size()
    visible_chunks_x, visible_chunks_y = (
        max_x // CHUNK_WIDTH + 2,
        max_y // CHUNK_HEIGHT + 2,
    )
    for row in chunk_matrix[
        max(cy - visible_chunks_y // 2, 0) : cy + max(visible_chunks_y // 2, 1)
    ]:
        for chunk in row[
            max(cx - visible_chunks_x // 2, 0) : cx + max(visible_chunks_x // 2, 1)
        ]:
            if chunk is not None:
                chunks.append(chunk)
    return chunks


def is_valid_chunk_file_name(file_name: str) -> bool:
    return (
        len(file_name) == 2
        and file_name[0] in VALID_CHUNK_POS_X
        and file_name[1] in VALID_CHUNK_POS_Y
    )


def get_terminal_size() -> tuple[int, int]:
    curses.update_lines_cols()
    return curses.COLS, curses.LINES


def get_terminal_center() -> tuple[int, int]:
    return tuple(map(lambda n: n // 2, get_terminal_size()))


# *- MAIN PROGRAM -* #


def main(stdscr: curses.window) -> int:
    curses.use_default_colors()
    curses.curs_set(0)

    player = Player("P", x=2, y=2)
    map = Map.load(player)

    while True:
        map.print(stdscr)
        player.print(stdscr)

        ch = stdscr.getch()

        if ch == 10:
            return 0

        match ch:
            case curses.KEY_LEFT:
                map.move_right()
            case curses.KEY_RIGHT:
                map.move_left()
            case curses.KEY_UP:
                map.move_down()
            case curses.KEY_DOWN:
                map.move_up()
            case 393:  # SHIFT+LEFT
                map.move_right(player_run=True)
            case 402:  # SHIFT+RIGHT
                map.move_left(player_run=True)
            case 337:  # SHIFT+UP
                map.move_down(player_run=True)
            case 336:  # SHIFT+DOWN
                map.move_up(player_run=True)

        stdscr.erase()


if __name__ == "__main__":
    raise SystemExit(curses.wrapper(main))
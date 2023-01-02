# curses demo

At this point of development, it is not really a game (yet?).
I'm currently just experimenting with curses.

## How to run

1. Create a virtual environment with Python 3.10
2. Inside this new venv, do `pip install -e .`
3. Run:

```
python3 src/cg/
```

## How to use

- Walk in any direction using the arrow keys.
- To run, press `Shift` simultaneously.
- Pressing `Enter` quits the program.

Encountering a portal (any digit) will teleport you to the next similar one\*, with movement conservation.

\* if you go through `2`, you'll be teleported to the next `2`.

## Demo

<video src="https://user-images.githubusercontent.com/43090614/210164587-59e0581a-b703-4f3b-9928-1d477147bf2d.mp4"></video>

> VS Code Theme: <https://github.com/qexat/qexat-theme>

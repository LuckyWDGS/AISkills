"""Command-line entry point; tools/_launch.py runs main() of the scripts/ module with this file's name."""

import _launch

if __name__ == "__main__":
    raise SystemExit(_launch.run(__file__))

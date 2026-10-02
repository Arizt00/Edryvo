"""An executable Python example for the Lumen task runner."""
from math import sqrt


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)


if __name__ == "__main__":
    print("LUMEN · Python workspace")
    print(f"Distance from (0, 0) to (3, 4): {distance((0, 0), (3, 4)):.1f}")
    print("Ready to build something brighter.")

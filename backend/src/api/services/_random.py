from random import gauss, random


def random_gauss(
    center: float, spread: float = 1.0, lo: float = 0.0, hi: float = 1.0
) -> float:
    while not (lo <= (x := gauss(center, spread)) <= hi):
        continue
    return x


def random_frequency(center: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return hi if random() < center else lo

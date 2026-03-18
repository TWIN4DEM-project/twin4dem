from random import expovariate, gauss, random


def random_weights(n: int = 6) -> list[float]:
    x = [expovariate(1.0) for _ in range(n)]
    s = sum(x)
    return [x_i / s for x_i in x]


def random_gauss(
    center: float, spread: float = 1.0, lo: float = 0.0, hi: float = 1.0
) -> float:
    while not (lo <= (x := gauss(center, spread)) <= hi):
        continue
    return x


def random_frequency(center: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return hi if random() < center else lo

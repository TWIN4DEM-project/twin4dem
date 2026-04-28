from random import expovariate


def random_weights(n: int = 6) -> list[float]:
    x = [expovariate(1.0) for _ in range(n)]
    s = sum(x)
    return [x_i / s for x_i in x]


def equal_weights(n: int = 6) -> list[float]:
    x = [round(1.0 / n, 2) for _ in range(n)]
    x[-1] = round(1 - sum(x[:-1]), 2)
    return x

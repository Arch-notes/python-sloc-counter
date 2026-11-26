# docstring module


class Calc:
    """Calculator."""

    factor = 2

    def add(self, a, b):
        return a + b

    def mul(self, a, b):
        return a * b * self.factor


def top():
    return Calc()

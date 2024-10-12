"""
Script contains definitions for Functions exectuor classes
"""


class FunctionExecutor:
    """
    Class for invoking functions with their arguments
    """

    def __init__(self, func):
        if type(func).__name__ != "function":
            raise TypeError("func must be a function")

        self.func = func

    def compute(self, **kwargs):
        return self.func(**kwargs)
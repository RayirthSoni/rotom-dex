"""
Script containing functions for multiprocessing
"""

from concurrent import futures


class ProcessExecutor:
    """Class to handle multiprocessing
    """
    def __init__(self):
        self.executor = futures.ProcessPoolExecutor()

    def __del__(self):
        self.executor.shutdown()

    def wait_on_futures(self, futures_iter):
        futures.wait(futures_iter)

    def submit(self, fn, **kwargs):
        return self.executor.submit(fn, **kwargs)

executor = ProcessExecutor()
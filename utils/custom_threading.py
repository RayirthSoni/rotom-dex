"""
Script contains functions for threading
"""

from concurrent import futures


class ThreadExecutor:
    def __init__(self):
        self.executor = futures.ThreadPoolExecutor()

    def __del__(self):
        self.executor.shutdown()

    def wait_on_futures(self):
        pass

    def submit(self, fn, **kwargs):
        self.executor.submit(fn, **kwargs)


executor = ThreadExecutor()

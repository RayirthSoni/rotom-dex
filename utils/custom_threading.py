"""
Script contains functions for threading
"""

from concurrent import futures
from utils.logger import logger


class ThreadExecutor:
    """
    Class to handle threading
    """
    def __init__(self):
        self.executor = futures.ThreadPoolExecutor()

    def __del__(self):
        self.executor.shutdown()

    def wait_on_futures(self, futures_iter):
        logger.info("ThreadExecutor: Waiting on futures")
        futures.wait(futures_iter)
        logger.info("ThreadExecutor: done waiting")

    def submit(self, fn, **kwargs):
        return self.executor.submit(fn, **kwargs)


executor = ThreadExecutor()

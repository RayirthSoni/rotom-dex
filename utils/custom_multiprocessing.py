"""
Script containing functions for multiprocessing
"""

from concurrent import futures


class ProcessExecutor:
    def __init__(self):
        self.executor = futures.ProcessPoolExecutor()

    def __del__(self):
        self.executor.shutdown()

    pass


executor = ProcessExecutor()

"""
Script containing functions for multiprocessing
"""

from concurrent import futures


class ProcessExecutor:
    def __init__(self):
        self.executor = futures.ProcessPoolExecutor(max_workers=4)

    def __del__(self):
        self.executor.shutdown()

    pass


executor = ProcessExecutor()

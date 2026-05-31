
import time

class PerformanceMonitor:

    def measure(self, fn):

        start = time.time()

        result = fn()

        end = time.time()

        return {
            "result": result,
            "execution_time": end - start
        }

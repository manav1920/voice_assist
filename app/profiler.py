import time


class Profiler:

    def __init__(self):
        self.times = {}

    def start(self, name):
        self.times[name] = time.perf_counter()

    def stop(self, name):
        self.times[name] = time.perf_counter() - self.times[name]

    def report(self):

        print("\n" + "=" * 50)
        print("       PERFORMANCE REPORT")
        print("=" * 50)

        total = 0

        for key, value in self.times.items():

            print(f"{key:<15}: {value:.2f} sec")

            total += value

        print("-" * 50)
        print(f"{'TOTAL':<15}: {total:.2f} sec")
        print("=" * 50)
#!/usr/bin/env python3
"""長時間の処理中に、処理段階と件数を定期表示する。"""

import threading

build_progress = None


class ProgressReporter:
    """処理本体とは別のスレッドから進捗を表示する。"""

    def __init__(self, emit, phase, *, enabled=True, interval=10.0):
        self._emit = emit
        self._phase = phase
        self._enabled = enabled
        self._interval = interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._completed = 0
        self._total = None
        self._unit = "items"
        self._count = False

    def __enter__(self):
        if self._enabled:
            self.report()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _run(self):
        while not self._stop.wait(self._interval):
            self.report()

    def report(self):
        if not self._enabled:
            return
        with self._lock:
            counts = ""
            if self._total is not None:
                counts = " {}/{} {}".format(self._completed, self._total, self._unit)
            elif self._count:
                counts = " {} {}".format(self._completed, self._unit)
            self._emit(self._phase + counts)

    def set_phase(self, phase, total=None, *, completed=0, announce=True,
                  unit="items", count=False):
        with self._lock:
            self._phase = phase
            self._completed = completed
            self._total = total
            self._unit = unit
            self._count = count
        if announce:
            self.report()

    def update(self, completed):
        with self._lock:
            self._completed = completed

    def advance(self):
        with self._lock:
            self._completed += 1

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join()
            self._thread = None

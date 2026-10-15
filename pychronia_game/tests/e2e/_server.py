# -*- coding: utf-8 -*-

import threading
import time

from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.test.testcases import LiveServerThread
from django.utils.deprecation import MiddlewareMixin

_counter_lock = threading.Lock()
_in_flight_count = 0


class InFlightRequestsMiddleware(MiddlewareMixin):
    """Tracks requests currently being handled by the live server thread, so that
    the per-test ZODB-restore fixture can wait for trailing AJAX polling (chat,
    webradio...) to settle before closing the ZODB connection."""

    def process_request(self, request):
        global _in_flight_count
        with _counter_lock:
            _in_flight_count += 1

    def process_response(self, request, response):
        global _in_flight_count
        with _counter_lock:
            _in_flight_count -= 1
        return response

    def process_exception(self, request, exception):
        global _in_flight_count
        with _counter_lock:
            _in_flight_count -= 1


def wait_for_idle_server(timeout=5.0, poll_interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _counter_lock:
            if _in_flight_count <= 0:
                return
        time.sleep(poll_interval)


class LiveServerRunner(object):
    """Runs the Django app, in-process, in a background thread.

    Must run in-process (rather than as a `runserver` subprocess) so that the
    per-test fixture can close() and reset the module-global ZODB_INSTANCE from
    the main thread before swapping the gamedata.fs file - which also sidesteps
    Windows' file lock on an externally-held FileStorage file.
    """

    def __init__(self, host="127.0.0.1"):
        self._thread = LiveServerThread(host, StaticFilesHandler, connections_override=None, port=0)

    def start(self):
        self._thread.daemon = True
        self._thread.start()
        self._thread.is_ready.wait()
        if self._thread.error:
            raise self._thread.error

    @property
    def base_url(self):
        return "http://%s:%s" % (self._thread.host, self._thread.port)

    def stop(self):
        self._thread.terminate()

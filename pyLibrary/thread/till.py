# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#
# THIS THREADING MODULE IS PERMEATED BY THE please_stop SIGNAL.
# THIS SIGNAL IS IMPORTANT FOR PROPER SIGNALLING WHICH ALLOWS
# FOR FAST AND PREDICTABLE SHUTDOWN AND CLEANUP OF THREADS

from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from thread import allocate_lock as _allocate_lock
from time import sleep, time

from pyLibrary.thread.signal import Signal
from pyLibrary.times.dates import Date, unix2Date
from pyLibrary.times.durations import Duration

DEBUG = True
INTERVAL = 0.1

_till_locker = _allocate_lock()
next_ping = time()
done = Signal("Timers shutdown")
done.go()

_Log = None

class Till(Signal):
    """
    TIMEOUT AS A SIGNAL
    """
    enabled = False
    new_timers = []

    def __new__(cls, till=None, timeout=None, seconds=None):
        if not Till.enabled:
            return done
        elif till is None and timeout is None and seconds is None:
            return None
        else:
            return object.__new__(cls)

    def __init__(self, till=None, timeout=None, seconds=None):
        global next_ping

        if not _Log:
            global _Log
            from MoLogs import Log as _Log
            _ = _Log

        if till != None:
            timeout = Date(till).unix
        elif seconds != None:
            timeout = time() + seconds
        elif timeout != None:
            timeout = time() + Duration(timeout).seconds

        Signal.__init__(self, name=unicode(timeout))

        with _till_locker:
            next_ping = min(next_ping, timeout)
            Till.new_timers.append((timeout, self))

    @classmethod
    def daemon(cls, please_stop):
        global next_ping

        Till.enabled = True
        sorted_timers = []

        try:
            while not please_stop:
                now = time()

                with _till_locker:
                    later = next_ping - now

                if later > 0:
                    try:
                        sleep(min(later, INTERVAL))
                    except Exception, e:
                        from MoLogs import Log

                        Log.warning(
                            "Call to sleep failed with ({{later}}, {{interval}})",
                            later=later,
                            interval=INTERVAL,
                            cause=e
                        )
                    continue

                with _till_locker:
                    next_ping = now + INTERVAL
                    new_timers, Till.new_timers = Till.new_timers, []

                if DEBUG:
                    _Log.note("new timers: {{timers}}", timers=[unix2Date(t[0]).format() for t in new_timers])

                sorted_timers.extend(new_timers)

                if sorted_timers:
                    sorted_timers.sort(key=lambda r: r[0])
                    for i, (t, s) in enumerate(sorted_timers):
                        if now < t:
                            work, sorted_timers[:i] = sorted_timers[:i], []
                            next_ping = min(next_ping, sorted_timers[0][0])
                            break
                    else:
                        work, sorted_timers = sorted_timers, []

                    if work:
                        for t, s in work:
                            s.go()

        except Exception, e:
            from MoLogs import Log

            Log.warning("timer shutdown", cause=e)
        finally:
            Till.enabled = False
            # TRIGGER ALL REMAINING TIMERS RIGHT NOW
            with _till_locker:
                new_work, Till.new_timers = Till.new_timers, []
            for t, s in new_work + sorted_timers:
                s.go()



import logging
log = logging.getLogger(__name__)

# Track time to avoid potential infinite loops
import time

class TimeoutException(Exception):
    """"Raise for when the time limit is exceeded."""
    # See https://stackoverflow.com/questions/1319615/proper-way-to-declare-custom-exceptions-in-modern-python

class TimeLimiter(object):
    def __init__(self, limit_sec = 1):
        self.cur_limit_sec = limit_sec
        self.reset()
        log.debug(
            "TimeLimiter: Created new time limit of '{0}' sec"
            .format(limit_sec)
        )

    @property
    def limit_sec(self):
        return self.cur_limit_sec

    def reset(self):
        # Reset the start time
        self.start_time = time.time()

    def check(self):
        # Compare the start with the current time
        limit_sec = self.limit_sec
        cur_time = time.time()
        if (cur_time - self.start_time) > limit_sec:
            log.info(
                "TimeLimiter: Exceeded limit of '{0}' sec, throwing exception"
                .format(limit_sec)
            )
            raise TimeoutException(
                "Exceeded time limit of '{0}' sec".format(limit_sec)
            )

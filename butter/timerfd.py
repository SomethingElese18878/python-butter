#!/usr/bin/env python
"""timerfd: recive timing events on a file descriptor"""

from __future__ import print_function

from os import write as _write, read as _read, close as _close
from select import select as _select
from cffi import FFI as _FFI
import errno as _errno
import math as _math

_ffi = _FFI()
_ffi.cdef("""
#define TFD_CLOEXEC ...
#define TFD_NONBLOCK ...

#define TFD_TIMER_ABSTIME ...

#define CLOCK_REALTIME ...
#define CLOCK_MONOTONIC ...

typedef long int time_t;

struct timespec {
    time_t tv_sec; /* Seconds */
    long tv_nsec; /* Nanoseconds */
};

struct itimerspec {
    struct timespec it_interval; /* Interval for periodic timer */
    struct timespec it_value; /* Initial expiration */
};

int timerfd_create(int clockid, int flags);

int timerfd_settime(int fd, int flags,
                    const struct itimerspec *new_value,
                    struct itimerspec *old_value);

int timerfd_gettime(int fd, struct itimerspec *curr_value);
""")

_C = _ffi.verify("""
#include <sys/timerfd.h>
#include <stdint.h> /* Definition of uint64_t */
#include <time.h>
""", libraries=[])

def timerfd(clock_type=0, flags=0):
    """Create a new timerfd
    
    Arguments
    ----------
    :param int clock_type: The type of clock to use internally
    :param int flags: Flags to specify extra options
    
    Flags
    ------
    CLOCK_REALTIME: Use a clock that mirrors the system time
                    (will be affected by settime)
    CLOCK_MONOTONIC: Use a Monotonically increasing clock value
    TFD_CLOEXEC: Close the timerfd when executing a new program
    TFD_NONBLOCK: Open the socket in non-blocking mode
    
    Returns
    --------
    :return: The file descriptor representing the timerfd
    :rtype: int
    
    Exceptions
    -----------
    :raises ValueError: Invalid value in flags
    :raises OSError: Max per process FD limit reached
    :raises OSError: Max system FD limit reached
    :raises OSError: Could not mount (internal) anonymous inode device
    :raises MemoryError: Insufficient kernel memory
    """
    fd = _C.timerfd_create(clock_type, flags)
    
    if fd < 0:
        err = _ffi.errno
        if err == _errno.EINVAL:
            if not clock_type  & (CLOCK_MONOTONIC|CLOCK_REALTIME):
                raise ValueError("clock_type is not one of CLOCK_MONOTONIC or CLOCK_REALTIME")
            raise ValueError("Invalid value in flags")
        elif err == _errno.EMFILE:
            raise OSError("Max per process FD limit reached")
        elif err == _errno.ENFILE:
            raise OSError("Max system FD limit reached")
        elif err == _errno.ENODEV:
            raise OsError("Could not mount (internal) anonymous inode device")
        elif err == _errno.ENOMEM:
            raise MemoryError("Insufficent kernel memory available")
        else:
            # If you are here, its a bug. send us the traceback
            raise ValueError("Unknown Error: {}".format(err))

    return fd

def timerfd_gettime(fd):
    """Get the current expiry time of a timerfd
    
    Arguments
    ----------
    :param int fd: File descriptor representing the timerfd

    Returns
    --------
    :return: The file descriptor representing the timerfd
    :rtype: int
    
    Exceptions
    -----------
    :raises ValueError: Invalid value in flags
    :raises OSError: Max per process FD limit reached
    :raises OSError: Max system FD limit reached
    :raises OSError: Could not mount (internal) anonymous inode device
    :raises MemoryError: Insufficient kernel memory
    """
    curr_val = _ffi.new('struct itimerspec *')
    ret = _C.timerfd_gettime(fd, curr_val)
    
    if ret < 0:
        err = _ffi.errno
        if err == _errno.EBADF:
            raise ValueError("fd is not a valid file descriptor")
        elif err == _errno.EFAULT:
            raise IOError("curr_val is not a valid pointer (internal/bug, let us know)")
        elif err == _errno.EINVAL:
            raise ValueError("fd is not a valid timerfd")
        else:
            # If you are here, its a bug. send us the traceback
            raise ValueError("Unknown Error: {}".format(err))

    curr_val = TimerSpec(timerspec=curr_val)
    return curr_val

def timerfd_settime(fd, timer_spec, flags=0):
    """Set the expiry time of a timerfd
    
    Arguments
    ----------
    :param int fd: File descriptor representing the timerfd
    :param int inital_value: The inital value to set the timerfd to
    :param int flags: Flags to specify extra options
    
    Flags
    ------
    TFD_TIMER_ABSTIMER: The specified time is an absolute value rather than relative to now
        
    Returns
    --------
    :return: The file descriptor representing the timerfd
    :rtype: int
    
    Exceptions
    -----------
    :raises ValueError: Invalid value in flags
    :raises OSError: Max per process FD limit reached
    :raises OSError: Max system FD limit reached
    :raises OSError: Could not mount (internal) anonymous inode device
    :raises MemoryError: Insufficient kernel memory
    """
    if hasattr(timer_spec, '__timerspec__'):
        timer_spec = timer_spec.__timerspec__()
    
    if hasattr(fd, 'fileno'):
        fd = fd.fileno()
    
    old_timer_spec = _ffi.new('struct itimerspec *')

    ret = _C.timerfd_settime(fd, flags, timer_spec, old_timer_spec)
    
    if ret < 0:
        err = _ffi.errno
        if err == _errno.EINVAL:
            if timer_spec.it_interval.tv_sec > 999999999:
                raise ValueError("Nano seconds in it_interval is > 999,999,999")
            elif timer_spec.it_value.tv_nsec > 999999999:
                raise ValueError("Nano seconds in it_value is > 999,999,999")
            else:
                raise ValueError('flags is invalid or fd not a timerfd')
        elif err == _errno.EFAULT:
            raise IOError("timer_spec does not point to a valid timer specfication")
        elif err == _errno.EMFILE:
            raise OSError("Max per process FD limit reached")
        elif err == _errno.ENFILE:
            raise OSError("Max system FD limit reached")
        elif err == _errno.ENODEV:
            raise OsError("Could not mount (internal) anonymous inode device")
        elif err == _errno.ENOMEM:
            raise MemoryError("Insufficent kernel memory available")
        else:
            # If you are here, its a bug. send us the traceback
            raise ValueError("Unknown Error: {}".format(err))
            
    old_timer_spec = TimerSpec(timerspec=old_timer_spec)
    return old_timer_spec

class TimerSpec(object):
    """Thin wrapper around the itimerspec c struct providing convience methods"""
    def __init__(self, reoccuring=None, reoccuring_seconds=None, reoccuring_nano_seconds=None, 
                       one_off=None, one_off_seconds=None, one_off_nano_seconds=None,
                       timerspec=None):
        """Friendly wrapper around a c struct
        
        If setting a raw timerspec via the timerspec field then the reoccuring and one_off fields
        can still be used to customise the timerspec object in one go
        
        Arguments
        ----------
        :param int reoccuring: set the reoccuring interval
        :param int reoccuring_seconds: set the reoccuring intervals seconds field
        :param int reoccuring_nano_seconds: set the reoccuring intervals nano seconds field
        :param int one_off: set a one off interval
        :param int one_off_seconds: set a one off intervals seconds field
        :param int one_off_nanon_seconds: set a one off intervals nano seconds field
        :param int timerspec: set the timerspec to an exisiting timerspec
        """
        self._timerspec = _ffi.new('struct itimerspec *')
        # cheap clone (this is harder than it appears at fist glance)
        if timerspec:
            self._timerspec.it_interval.tv_sec = timerspec.it_interval.tv_sec
            self._timerspec.it_interval.tv_nsec = timerspec.it_interval.tv_nsec
            self._timerspec.it_value.tv_sec = timerspec.it_value.tv_sec
            self._timerspec.it_value.tv_nsec = timerspec.it_value.tv_nsec
            
        if reoccuring:
            self.reoccuring = reoccuring
        if reoccuring_seconds:
            self.reoccuring_seconds = reoccuring_sec
        if reoccuring_nano_seconds:
            self.reoccuring_nano_seconds = reoccuring_nano
        if one_off:
            self.one_off = one_off
        if one_off_seconds:
            self.one_off_seconds = one_off_sec
        if one_off_nano_seconds:
            self.one_off_nano_seconds = one_off_nano
    
    @property
    def reoccuring(self):
        """The interval for reoccuring events in seconds as a float"""
        return self.reoccuring_seconds + (self.reoccuring_nano_seconds / 1000000000)
        
    @reoccuring.setter
    def reoccuring(self, val):
        """The interval for reoccuring events in seconds as a float"""
        if isinstance(val, float):
            x, y = _math.modf(val)
            sec = int(y)
            nano = round(1000000000 * x)
            nano = int(nano) # python2.7 workaround (returns float there)
        else:
            sec = val
            nano = 0
        
        self.reoccuring_seconds = sec
        self.reoccuring_nano_seconds = nano
    
    @property
    def reoccuring_seconds(self):
        """Seconds part of a reoccuring event as an integer"""
        return self._timerspec.it_interval.tv_sec
        
    @reoccuring_seconds.setter
    def reoccuring_seconds(self, val):
        """Seconds part of a reoccuring event as an integer"""
        self._timerspec.it_interval.tv_sec = val

    @property
    def reoccuring_nano_seconds(self):
        """Nano seconds part of a reoccuring event as an integer"""
        return self._timerspec.it_interval.tv_nsec
    
    @reoccuring_nano_seconds.setter
    def reoccuring_nano_seconds(self, val):
        """Nano seconds part of a reoccuring event as an integer"""
        self._timerspec.it_interval.tv_nsec = val

    @property
    def one_off(self):
        """The interval for a one off event in seconds as a float"""
        return self.one_off_seconds + (self.one_off_nano_seconds / 1000000000)
        
    @one_off.setter
    def one_off(self, val):
        """The interval for a one off event in seconds as a float"""
        if isinstance(val, float):
            x, y = _math.modf(val)
            sec = int(y)
            nano = round(1000000000 * x)
            nano = int(nano) # python2.7 workaround (returns float there)
        else:
            sec = val
            nano = 0
        
        self.one_off_seconds = sec
        self.one_off_nano_seconds = nano

    @property
    def one_off_seconds(self):
        """Seconds part of a one off event as an integer"""
        return self._timerspec.it_value.tv_sec
        
    @one_off_seconds.setter
    def one_off_seconds(self, val):
        """Seconds part of a one off event as an integer"""
        self._timerspec.it_value.tv_sec = val

    @property
    def one_off_nano_seconds(self):
        """Nano seconds part of a one off event as an integer"""
        return self._timerspec.it_value.tv_nsec
    
    @one_off_nano_seconds.setter
    def one_off_nano_seconds(self, val):
        """Nano seconds part of a one off event as an integer"""
        self._timerspec.it_value.tv_nsec = val
    
    def __timerspec__(self):
        return self._timerspec
    
    def __bool__(self):
        return False if self.one_off == 0.0 else True
    
    @property
    def enabled(self):
        """Will this timer fire if used?, returns a bool"""
        return bool(self)
    
    @property
    def disabled(self):
        """Will this timer not fire if used?, returns a bool"""
        return not self.enabled

    def disable(self):
        """Disable the timer in this timespec"""
        self.one_off = 0.0
    
    @property
    def next_event(self):
        """Convenience accessor for results returned by timerfd_gettime"""
        return self.one_off

    @property
    def next_event_seconds(self):
        """Convenience accessor for results returned by timerfd_gettime"""
        return self.one_off_seconds
        
    @property
    def next_event_nano_seconds(self):
        """Convenience accessor for results returned by timerfd_gettime"""
        return self.one_off_nano_seconds
    
    def __repr__(self):
        return "<{} next={}s reoccuring={}s>".format(self.__class__.__name__, self.next_event, self.reoccuring)
    

TFD_CLOEXEC = _C.TFD_CLOEXEC
TFD_NONBLOCK = _C.TFD_NONBLOCK
TFD_TIMER_ABSTIME = _C.TFD_TIMER_ABSTIME

CLOCK_REALTIME = _C.CLOCK_REALTIME
CLOCK_MONOTONIC = _C.CLOCK_MONOTONIC

class Timerfd(object):
    def __init__(self, clock_type=CLOCK_REALTIME, flags=0):
        """Create a new Timerfd object

        Arguments
        ----------
        :param int clock_type: The type of clock to use for timing
        :param int flags: Flags to specify extra options
        
        Flags
        ------
        CLOCK_REALTIME: Use a time source that matches the wall time
        CLOCK_MONOTONIC: Use a monotonically incrementing time source
        TFD_CLOEXEC: Close the timerfd when executing a new program
        TFD_NONBLOCK: Open the socket in non-blocking mode
        """
        self._fd = timerfd(clock_type, flags)
        self._timerspec = TimerSpec()
    
    def set_one_off(self, seconds, nano_seconds=0, absolute=False):
        timer = TimerSpec()
        timer.one_off = seconds
        timer.one_off = nano_seconds
        
        old_val = self._update(timer, absolute=absolute)
        
        return old_val
        
    def set_reoccuring(self, seconds, nano_seconds=0, 
                             next_seconds=0, next_nano_seconds=0,
                             absolute=False):
        timer = TimerSpec()
        # set nano seconds first, if seconds is a float it
        # will get overidden. this was we dont need any
        # if conditionals/guards
        timer.reoccuring_nano = nano_seconds
        timer.reoccuring = seconds
        
        if next_seconds or next_nano_seconds:
            timer.one_off = next_nano_seconds
            timer.one_off = next_seconds
        else:
            timer.one_off = nano_seconds
            timer.one_off = seconds

        old_val = self._update(timer, absolute=absolute)
        
        return old_val

    def get_current(self):
        return timerfd_gettime(self._fd)

    def _update(self, timerspec, absolute=False):
        flags = TFD_TIMER_ABSTIME if absolute else 0
        old_timer = timerfd_settime(self._fd, timerspec, flags)
        
        return old_timer
    
    def wait(self):
        """Wait for the next timer event (ethier one off or periodic)
        
        Returns
        --------
        :return: The amount of timerfd events that have fired since the last read()
        :rtype: int
        """
        _select([self._fd], [], [])
        
        data = _read(self._fd, 8)
        value = _ffi.new('uint64_t[1]')
        _ffi.buffer(value, 8)[0:8] = data

        return value[0]
    
    def close(self):
        _close(self._fd)

    def fileno(self):
        return self._fd

    @property
    def enabled(self):
        return self.get_current().enabled

    @property
    def disabled(self):
        return not self.enabled

    def disable(self):
        timer = self.get_current()
        timer.disable()

        self._update(timer)

def _main():
    from time import time, sleep
    t = Timerfd()
    
    time_val = 0.5
    t.set_reoccuring(time_val)
    print("Setting time interval to {:.2f} seconds".format(time_val))
    
    for i in range(5):
        old_time = time()
        num_events = t.wait()
        new_time = time()
        assert num_events == 1, "Too many events"
        print("Woke up after {:.2f} seconds".format(new_time - old_time))
        
    print("Got all 5 events")
    
    print("Sleeping for 0.3s")
    sleep(0.3)
    print("Next event:", t.get_current())
    
    
# import asyncio code if avalible
# must be done here as otherwise the module's dict
# does not have the required functions defined yet
# as it is a circular import
import platform
if platform.python_version_tuple() >= ('3', '4', '0'):
    from .asyncio.timerfd import Timerfd as Timerfd_async
    
if __name__ == "__main__":
    _main()

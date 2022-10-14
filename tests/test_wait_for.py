# -------------------------------------------------------------------------------
# - Copyright (c) 2021-2022 Arista Networks, Inc. All rights reserved.
# -------------------------------------------------------------------------------
# - Author:
# -   fdk-support@arista.com
# -
# - Description:
# -   Tests for the wait_for function.
# -
# -   Licensed under BSD 3-clause license:
# -     https://opensource.org/licenses/BSD-3-Clause
# -
# - Tags:
# -   license-bsd-3-clause
# -
# -------------------------------------------------------------------------------

import time
import pexpect
import pytest

pytest_plugins = ["pytest_netdut"]


def test_wait_for(wait_for):
    """Make sure that pytest reports a timeout."""
    # The timeout for this particular test
    TIMEOUT = 1
    # The hard-coded TIMEOUT_LEEWAY_FACTOR constant must be the same as the
    # one similarly defined in the wait_for function (in utils.py).
    TIMEOUT_LEEWAY_FACTOR = 2

    def good_fn():
        time.sleep(0.5 * TIMEOUT)
        return True

    def slow_fn():
        time.sleep((1 + TIMEOUT_LEEWAY_FACTOR) * TIMEOUT / 2)
        return True

    def bad_fn():
        time.sleep(1.1 * TIMEOUT_LEEWAY_FACTOR * TIMEOUT)
        return False

    # Test a good function which completes within "timeout" (i.e. does not time out)
    # T < timeout
    wait_for(good_fn, timeout=TIMEOUT)

    # Test a slow function which completes after "timeout" but before "TIMEOUT_LEEWAY_FACTOR * timeout"
    # timeout <= T < TIMEOUT_LEEWAY_FACTOR * timeout
    with pytest.raises(pexpect.TIMEOUT, match=r"succeeded"):
        wait_for(slow_fn, timeout=TIMEOUT)

    # Test a bad function which doesn't complete within "TIMEOUT_LEEWAY_FACTOR * timeout"
    # T >= TIMEOUT_LEEWAY_FACTOR * timeout
    with pytest.raises(pexpect.TIMEOUT, match=r"unsuccessful"):
        wait_for(bad_fn, timeout=TIMEOUT)

# -------------------------------------------------------------------------------
# - Copyright (c) 2021-2022 Arista Networks, Inc. All rights reserved.
# -------------------------------------------------------------------------------
# - Author:
# -   fdk-support@arista.com
# -
# - Description:
# -   Utility functions to use in pytest-netdut.
# -
# -   Licensed under BSD 3-clause license:
# -     https://opensource.org/licenses/BSD-3-Clause
# -
# - Tags:
# -   license-bsd-3-clause
# -
# -------------------------------------------------------------------------------

import contextlib
import time
import pexpect
import pytest


@pytest.fixture(scope="session")
def wait_for():
    """A fixture that returns a function that can be called to wait for something to happen.

    This is useful waiting for configuration to be applied asynchronously.

    Examples:
        >>> wait_for(lambda: dut.eapi.sendcmd(f"show {appname} status")["running"])
    """

    def _wait_for(func, timeout=30, period=0.1, suppress=None):
        """Wait up to 'timeout' seconds for the successful completion of 'func'."""
        # Let the elapsed time within this function be T seconds.
        # There are 3 scenarios:

        # 1.  T < 'timeout'
        #    'func' returns successfully.
        #    This function returns.

        # 2. 'timeout' <= T < TIMEOUT_LEEWAY_FACTOR * 'timeout'
        #    'func' returns successfully.
        #    This function raises an exception with an error message.

        # 3. T >= TIMEOUT_LEEWAY_FACTOR * 'timeout'
        #    'func' returns unsuccessfully.
        #    This function raises an exception with an error message.

        # The hard-coded timeout_leeway_factor constant must be the same as the
        # one similarly defined in the test_wait_for function (in test_wait_for.py).
        # This constant is used to allow for some leeway in the reporting of a
        # 'func' which was successful, but whose duration exceeded the requested
        # 'timeout', i.e. 'func' returned successfully after a time T where
        # 'timeout' <= T < timeout_leeway_factor * 'timeout'.
        timeout_leeway_factor = 2

        # Alert the user if the polling period is greater than the requested timeout.
        assert timeout > period

        if suppress is None:
            suppress = []
        start = time.time()
        while True:
            with contextlib.suppress(*suppress):
                result = func()
                if result:
                    elapsed = time.time() - start
                    if elapsed > timeout:
                        raise pexpect.TIMEOUT(
                            f"Timed out waiting for {func} after {timeout} seconds, "
                            f"but eventually succeeded after {elapsed} seconds."
                        )
                    return result
            if time.time() - start > timeout_leeway_factor * timeout:
                raise pexpect.TIMEOUT(
                    f"Function {func} was unsuccessful after the requested {timeout} "
                    f"second timeout, and was also unsuccessful after being allowed "
                    f"a leeway of {timeout_leeway_factor * timeout} seconds."
                )
            time.sleep(period)

    yield _wait_for

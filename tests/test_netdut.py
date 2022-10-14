# -------------------------------------------------------------------------------
# - Copyright (c) 2021-2022 Arista Networks, Inc. All rights reserved.
# -------------------------------------------------------------------------------
# - Author:
# -   fdk-support@arista.com
# -
# - Description:
# -   Tests for the netdut fixtures.
# -
# -   Licensed under BSD 3-clause license:
# -     https://opensource.org/licenses/BSD-3-Clause
# -
# - Tags:
# -   license-bsd-3-clause
# -
# -------------------------------------------------------------------------------


def test_dut_fixtures(testdir):
    """Make sure that pytest accepts our fixture."""

    # create a temporary conftest module
    testdir.makeconftest(
        """
        pytest_plugins = ["pytest_netdut"]
    """
    )

    # create a temporary pytest test module
    testdir.makepyfile(
        """
        def test_sth(dut):
            assert dut.info["hostname"] == "baz01"
            assert dut.info["console_url"] == "telnet://bernie:1001"
    """
    )

    # run pytest with the following cmd args
    result = testdir.runpytest("--device=baz01", "--console=telnet://bernie:1001", "-v")

    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(
        [
            "*::test_sth PASSED*",
        ]
    )

    # make sure that we get a '0' exit code for the testsuite
    assert result.ret == 0


def test_help_message(testdir):
    testdir.makeconftest(
        """
        pytest_plugins = ["pytest_netdut"]
    """
    )

    result = testdir.runpytest(
        "--help",
    )
    # fnmatch_lines does an assertion internally
    result.stdout.fnmatch_lines(
        [
            "netdut:",
            "*--device=DUT_HOSTNAME",
            "*DUT hostname",
            "*--console=DUT_CONSOLE_URL",
            "*DUT console URL",
        ]
    )

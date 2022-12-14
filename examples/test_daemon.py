import logging
import pprint
import pytest


@pytest.fixture
def sleeper_daemon(dut, wait_for):
    # Start a dummy daemon that sleeps
    dut.eapi.sendcmds(
        """
        enable
            configure
                daemon sleeper
                    exec /usr/bin/sleep 10
                    no shutdown
    """
    )

    # Wait for the OS to register the config and add the daemon.
    wait_for(
        lambda: "sleeper" in dut.eapi.sendcmds(["enable", "show daemon"])[-1]["daemons"]
    )

    # Yield the name of the daemon for the test to use.
    yield "sleeper"

    dut.eapi.sendcmds(
        """
        enable
            configure
                no daemon sleeper
    """
    )

    # Wait for the OS to register the config and remove the daemon.
    wait_for(
        lambda: "sleeper"
        not in dut.eapi.sendcmds(["enable", "show daemon"])[-1]["daemons"]
    )


def test_sendcmds(dut, sleeper_daemon, wait_for):

    # This local functon determines whether the daemon has started.
    # We call it below using wait_for.
    def daemon_has_started():
        daemon_info = dut.eapi.sendcmds(["enable", f"show daemon {sleeper_daemon}"])[-1]
        return daemon_info["daemons"][sleeper_daemon]["starttime"] != 0.0

    # Wait for the Daemon to start. If it doesn't within 10s, the test fails.
    wait_for(daemon_has_started, timeout=10.0)

    # Snapshot the info about the daemon
    daemon_info = dut.eapi.sendcmds(["enable", f"show daemon {sleeper_daemon}"])[-1][
        "daemons"
    ][sleeper_daemon]

    # Check that our uptime is still non-zero
    assert daemon_info["starttime"] != 0.0
    assert daemon_info["uptime"] != 0.0
    assert daemon_info["running"]

    # Print the PID, so we can show we really created a daemon.
    logging.info(f"Daemon was started and the PID is {daemon_info['pid']}")

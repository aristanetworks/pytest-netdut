import logging
import pytest
import time


@pytest.fixture
def my_test_harness(dut):
    dut.ssh.sendcmds(
        ["enable", "configure", "banner motd\nMy test is running, hands off!\nEOF\n"]
    )
    yield
    dut.ssh.sendcmds(["enable", "configure", "no banner motd"])


def test_mytest(my_test_harness):
    logging.info("Sleeping to simulate running a test here")
    time.sleep(5)

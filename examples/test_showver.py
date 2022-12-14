import logging
import pytest

# A simplified demo
def test_showver(dut):
    info = dut.eapi.sendcmd("show version")
    logging.info(f"DUT model was: {info['modelName']}")


# A demo of an assertion, which we expect to fail
@pytest.mark.xfail()
def test_check_version(dut):
    info = dut.eapi.sendcmd("show version")
    assert info["version"] == "1.0.0"

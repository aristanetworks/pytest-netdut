import pytest
import logging


@pytest.mark.eos
def test_that_runs_on_EOS(dut):
    "A test decorated so that it only runs on EOS"
    #    logging.info("Must be EOS!")
    assert True


@pytest.mark.mos
def test_that_runs_on_MOS(dut):
    "A test decorated so that it only runs on MOS"
    #    logging.info("Must be MOS!")
    assert True


@pytest.mark.only_device_type(
    "DCS-7130",
    reason="Demonstrating a 7130-only test",
)
def test_that_runs_on_7130(dut):
    "A test decorated so that it only runs on 7130 platforms"
    #    logging.info("Must be a 7130!")
    assert True


@pytest.mark.skip_device_type(
    "DCS-7130",
    reason="Demonstrating a non-7130 test",
)
def test_that_skips_7130(dut):
    "A test decorated so that it only runs on non-7130 platforms"
    #    logging.info("Must not be 7130!")
    assert True

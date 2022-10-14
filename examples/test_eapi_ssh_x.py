def test_ssh_showver(dut):
    """Demonstrate using the `dut` fixture to determine the version via ssh.
    SSH returns a text output."""

    dut.ssh.sendcmds("show version")


def test_eapi_showver(dut):
    """Demonstrate using the `dut` fixture to check the OS version via eapi."""
    version_info = dut.eapi.sendcmd("show version")
    assert version_info["version"] != "1.0.0"


def test_x_showver(dut):
    """Demonstrate the X api using the `dut` fixture"""
    assert dut.x.show_version()["version"] != "1.0.0"

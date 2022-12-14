"""pytest-netdut is a pytest plugin to provide fixtures for the control networked DUTs.

The purpose is to running automated tests of software on networking hardware,
including FPGA applications like those built using Arista's FDK.

Assuming the device is accessible via SSH, run tests like this:

```bash
pytest --device=1.2.3.4
```

# The `dut` fixture

The `dut` fixture is created dynamically (by [`create`][pytest_netdut.create]) when the pytest-netdut plugin
is loaded, based on information passed to pytest on the CLI. By default, it refers to a number of sub-fixtures,
which are also dynamically created on first use.

These sub-fixtures of `dut` are:

1. ssh -- an instance of the [CLI][pytest_netdut.CLI] class for this DUT.
2. eapi -- an instance of the [EAPI][pytest_netdut.EAPI] class for this DUT.
3. xapi -- an instance of the [xapi][pytest_netdut.xapi] class for this DUT.
4. hostname -- the hostname of this DUT.
5. sku -- the SKU, as a string, determined by querying the DUT.

# Usage

A test which uses netdut might look like:

```python
def test_showver(dut):
    info = dut.eapi.sendcmd("show version")
    logging.info(f"DUT model was: {info['modelName']}")
```

this uses the dut.eapi fixture to run `show version` on the DUT and then logs the value of `modelName` from the result.

# Skipping

`pytest-netdut` implements a skipping mechansim based on the dut, by providing marks which annotate the desired
behaviour for the tests. Current marks are:

1. `eos` -- marks a test to run on EOS only.
2. `mos` -- marks a test to run on MOS only.
3. `skip_device_type(pattern)` -- marks a test to be skipped when the DUT's SKU matches the pattern.
4. `only_device_type(pattern)` -- marks a test to only be run when the DUT's SKU matches the pattern.

An example of a test which would be skipped on a particular SKU:

```python
@pytest.mark.only_device_type("^DCS-7130")
def test_showver(dut):
    assert dut.eapi.sendcmd("show version")['modelName'].startswith("DCS-7130")
```

# Utilities

`pytest-netdut` provides some other functionality to make it easier to write tests.

* The [wait_for][pytest_netdut.wait_for] fixture repeatedly calls a function until
    a condition becomes true, or a timeout expires. This is useful for waiting for
    the configuration to take effect once the commands have been sent.

# Pytest Command Line Options

`pytest-netdut` adds a command line option:

* `--device` -- specifies the hostname for the device. Netdut expects to be able to connect via ssh
    to this hostname.

"""
from typing import Callable
import pytest
from . import factories
from .utils import wait_for
from .wrappers import CLI, EAPI, eapi_enabled_fixture, xapi

__all__ = ["CLI", "EAPI", "create", "eapi_enabled_fixture", "wait_for", "xapi"]


def pytest_configure(config):
    """pytest_configure hook that adds markers used by netdut.

    Args:
        config (pytest.Config): The pytest config object.
    """

    # register markers
    config.addinivalue_line("markers", "eos: mark a test as eos only.")
    config.addinivalue_line("markers", "mos: mark a test as mos only.")
    config.addinivalue_line(
        "markers", "skip_device_type: mark a test as excluding a particular SKU regex."
    )
    config.addinivalue_line(
        "markers",
        "only_device_type: mark a test as only running on a particular SKU regex.",
    )

    # FIXME: not really part of netdut
    config.addinivalue_line("markers", "slow: slower than usual tests.")


def pytest_addoption(parser):
    """pytest_addoption hook adds options used by netdut.

    Netdut uses the following CLI/ini/config file options:
    * --device : configure the hostname for the switch, which can be used for SSH
    * --console: the address of a TCP socket which serves the device's serial console

    Args:
        parser (pytest.Parser): The pytest parser to add configuration options to.
    """
    group = parser.getgroup("netdut")
    group.addoption("--device", dest="dut_hostname", help="DUT hostname")
    group.addoption("--console", dest="dut_console_url", help="DUT console URL")


def create(name) -> Callable:
    """Dynamically create all fixtures required to implement "dut"

    Fixtures can be created for any named dut. The DUT fixture named `dut`
    is created by default when netdut is loaded. These DUT fixtures
    refer to other fixtures which may be used dynamically (e.g. no resources
    are used until required).

    This function creates the DUT fixture itself, as well as the other associated
    fixtures, like the EAPI fixture (used for methods like `dut.eapi.sendcmds()`).

    We assume that there is a pre-existing fixture called `{name}_info` (where
    {name} is the value of the parameter passed to create.). It should be a
    dictionary containing a host name.

    Args:
        name (str): The name of the top level DUT fixture - e.g. `dut`

    Returns:
        The DUT fixture which was created.
    """
    fixtures = [
        factories.create_dut_fixture(name),
        factories.create_eapi_fixture(name),
        factories.create_hostname_fixture(name),
        factories.create_skipper_fixture(name),
        factories.create_sku_fixture(name),
        factories.create_softened_fixture(name),
        factories.create_ssh_fixture(name),
        factories.create_xapi_fixture(name),
    ]

    for fixture in fixtures:
        globals()[fixture.__name__] = fixture

    return fixtures[0]


@pytest.fixture(scope="session")
def dut_info(pytestconfig) -> dict:
    """A fixture providing the DUT configuration passed via config to pytest-netdut.

    Args:
        pytestconfig (pytest.Config): The pytestconfig object representing the pytest configuration.

    Returns:
        A dictionary containing the hostname and console URL config parameters.
    """
    info = {
        "hostname": pytestconfig.getoption("dut_hostname"),
        "console_url": pytestconfig.getoption("dut_console_url"),
    }
    assert info["console_url"] or info["hostname"], "You must specify a device"
    return info


create("dut")

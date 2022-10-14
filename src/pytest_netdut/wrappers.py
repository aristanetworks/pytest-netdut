# -------------------------------------------------------------------------------
# - Copyright (c) 2021 Arista Networks, Inc. All rights reserved.
# -------------------------------------------------------------------------------
# - Author:
# -   fdk-support@arista.com
# -
# - Description:
# -   Convenience wrappers around CLI/EAPI.
# -
# -   Licensed under BSD 3-clause license:
# -     https://opensource.org/licenses/BSD-3-Clause
# -
# - Tags:
# -   license-bsd-3-clause
# -
# -------------------------------------------------------------------------------
import contextlib
import re
import logging
import pprint

from typing import Callable

import pyeapi
import pytest
import six

from . import px


def _splitcmds(cmds):
    if isinstance(cmds, six.string_types):
        return [cmd.strip() for cmd in cmds.strip().splitlines()]
    return cmds


def _eos_to_mos_translator(cmds):
    translations = [
        (r"interface ap1/(.*)", r"interface ap\1"),
        (r"l1 source interface ap1/(.*)", r"source ap\1"),
        (r"l1 source interface ap(.*)", "CAN NOT TRANSLATE"),
        (r"l1 source interface (.*)", r"source \1"),
        (
            r"l1 source mac",
            r"source mac",
        ),
        (r"no l1 source", r"no source"),
        (r"bash sudo cortina", "CAN NOT TRANSLATE"),
        (r"traffic-loopback source network device phy", r"loopback internal"),
        (r"traffic-loopback source system device phy", r"loopback"),
        (r"no traffic-loopback", r"no loopback"),
    ]

    commands = []
    for command in _splitcmds(cmds):
        for (before, after) in translations:
            matcher = re.match(before, command)
            if matcher:
                commands.append(matcher.expand(after))
                break
        else:
            # If we don't get a match, just append the original.
            commands.append(command)
    if commands != cmds:
        logging.debug("Before: %s, After: %s", repr(cmds), repr(commands))
    return commands


class CLI(px.CLI):
    """Extends pexpect.spawn (via px.CLI) to add support for interacting with
    an Arista style CLI."""

    def sendcmds(self, cmds):
        """Returns a list of results of running multiple commands on the CLI.

        Args:
            cmds (str | Iterable[str]): Either an iterable of commands to be run or a newline separated string containing one or more commands.
        """
        return [self.sendcmd(cmd) for cmd in _splitcmds(cmds)]


class EAPI:
    """A wrapper around pyeapi connections with px-like methods.

    Args:
        hostname (str): The hostname or IP address of the device to connect to.
        transport (str): The transport to use to connect.
    """

    def __init__(self, hostname, transport):
        self._conn = pyeapi.connect(host=hostname, transport=transport)
        self.translator = None

    def set_translator(self, translator):
        """Sets the function to be called on each command before it is passed to the CLI or CAPI/eAPI.

        This can be used, for example, to hide syntax differences between devices with different CLIs.

        Args:
            translator (Callable): The function to be called before on each command.
        """
        self.translator = translator

    def sendcmd(self, cmd, timeout=None):
        """Returns the deserialized JSON result of running a command via the CAPI/eAPI.

        Args:
            cmd (str): The command to be run.
        """
        if timeout:
            logging.debug("Timeout parameter is ignored by EAPI -- timeout=%f", timeout)
        if self.translator:
            cmds = self.translator(cmd)
        else:
            cmds = [cmd]
        return self._conn.execute(cmds)["result"][0]

    def sendcmds(self, cmds, timeout=None):
        """Returns a list of results of running multiple commands via the CAPI/eAPI.

        Args:
            cmds (str | Iterable[str]): Either an iterable of commands to be run or a newline separated string containing one or more commands.
        """
        if timeout:
            logging.debug("Timeout parameter is ignored by EAPI -- timeout=%f", timeout)
        if self.translator:
            cmds = self.translator(cmds)
        logging.info(pprint.pformat(cmds))
        return self._conn.execute(_splitcmds(cmds))["result"]


@pytest.fixture(scope="session", name="eapi_enabled")
def eapi_enabled_fixture(wait_for):
    """A session-scoped fixture that automatically enables the EAPI on the dut and returns a px-like wrapper around it."""

    @contextlib.contextmanager
    def _eapi_enabled(hostname, ssh, transport):
        if ssh.cli_flavor == "mos":
            ssh.sendcmds(
                """
                configure
                management http
                    no protocol secure
                management api
                    no shutdown
                end
            """
            )
        else:
            ssh.sendcmds(
                """
                configure
                management api http-commands
                    no shutdown
                    validate-output
                management http-server
                    protocol http
                end
            """
            )
            # Wait for services to init
            ssh.sendcmd("wait-for-warmup Capi CapiApp")

        def connect():
            # Disable pyeapi error logging while we try to connect.
            logger = logging.getLogger("pyeapi")
            old_level = logger.getEffectiveLevel()
            logger.setLevel(logging.CRITICAL)
            try:
                eapi = EAPI(hostname=hostname, transport=transport)
                eapi.sendcmd("show version")
                if ssh.cli_flavor == "mos":
                    eapi.set_translator(_eos_to_mos_translator)
                return eapi
            except (pyeapi.eapilib.ConnectionError, ConnectionRefusedError):
                return None
            finally:
                logger.setLevel(old_level)

        yield wait_for(connect)

        # FIXME: we should we restore the config rather than just disabling EAPI.
        if ssh.cli_flavor == "mos":
            ssh.sendcmds(
                """
                configure
                management api
                    shutdown
                management http
                    default protocol
                end
            """
            )
        else:
            ssh.sendcmds(
                """
                configure
                management http-server
                    no protocol http
                management api http-commands
                    shutdown
                    no validate-output
                end
            """
            )

    yield _eapi_enabled


def xapi(eapi):
    """Provides a pythonic wrapper around the cAPI/eAPI.

    Examples:
        >>> xapi.show_version()["version"]
        '4.26.1FX-7130'
    """

    class X:
        def __init__(self, cmds=None):
            self.cmds = cmds or []

        def __getattr__(self, name):
            return X([*self.cmds, name.replace("_", " ")])

        def __call__(self):
            return eapi.sendcmds(self.cmds)[-1]

        def __getitem__(self, key):
            return X([*self.cmds[:-1], f"{self.cmds[-1]} {key}"])

        def add(self, elem):
            return X([*self.cmds, elem])()

    return X()

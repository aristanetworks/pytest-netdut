# -------------------------------------------------------------------------------
# - Copyright (c) 2021 Arista Networks, Inc. All rights reserved.
# -------------------------------------------------------------------------------
# - Author:
# -   fdk-support@arista.com
# -
# - Description:
# -   Convenience wrappers around pexpect for CLIs.
# -
# -   Licensed under BSD 3-clause license:
# -     https://opensource.org/licenses/BSD-3-Clause
# -
# - Tags:
# -   license-bsd-3-clause
# -
# -------------------------------------------------------------------------------

# pylint: disable=consider-using-f-string

from __future__ import absolute_import, print_function

import os
import re
import subprocess
import six.moves.urllib.parse
import sys
import time

import pexpect
import six
from pexpect import TIMEOUT, ExceptionPexpect
from six.moves import range


class spawn(pexpect.spawn):
    def __str__(self):
        spawned = pexpect.spawn.__str__(self).splitlines()
        spawned.append("_prompt: " + repr(getattr(self, "_prompt", None)))
        return "\n".join(spawned)


class Shell(spawn):
    _control_code_re = r"(?:\x1B(?:.|[@-_][0-?]*[ -/]*[@-~]))*"  # Match control codes

    # Match device hostname or bash prompt (requires at least one alphabet)
    _hostname_re = r"([a-zA-Z]+[\w\-\.]*)"
    _mode_and_path_re = (
        r"("  # Match
        r">"  # cli non-priv mode
        r"|"  # or
        # cli priv and config modes (only simple config mode names are allowed)
        r"((\([\w\-\.\,\/]+\))?#)"
        r"|"  # or
        r"(:[\w\-\.\/~]+(#|\$))"  # bash working dir and shell type (bash, sudo bash)
        # End optional (bash-4.4# is a special case that matches cli priv prompt)
        r")"
    )
    _prompt_regex = re.compile(_control_code_re + _hostname_re + _mode_and_path_re)

    def syncprompt(self):
        self.expect(self._prompt_regex)
        # Use captured serial number / hostname for finding the prompt
        self._prompt = re.compile(
            self._control_code_re + self.match.group(1) + self._mode_and_path_re
        )

    def prompt(self, timeout=-1, reset=0):
        if reset:
            self.syncprompt()
        else:
            self.expect(self._prompt, timeout)
        return self.before.replace("\r\n", "\n")

    def sendcmd(self, cmd="", timeout=-1, reset=0, wait=True):
        if not isinstance(self.after, six.string_types) or not self._prompt.match(
            self.after
        ):
            raise Exception(
                "Cannot find prompt. Refusing to send command.",
                self.after,
                self._prompt.pattern,
            )

        self.sendcmd_unchecked(cmd)

        if wait:
            return self.prompt(timeout, reset)

        return None

    def sendcmd_unchecked(self, cmd=""):
        # "en" is a common abbreviation for enable.
        # We special-case this particular command.
        if cmd == "en":
            cmd = "enable"

        # self.sendline() appends os.linesep, so strip any line endings from
        # the end of the command to prevent the prompt from getting out of
        # sync.
        cmd = cmd.rstrip(os.linesep)

        self.sendline(cmd)

        try:
            self.expect(re.escape(cmd), timeout=10)
        except TIMEOUT:
            # This deals with long commands on the serial console
            if not cmd.startswith(
                self.before[  # pylint: disable=unsubscriptable-object
                    : self.before.index("\r")
                ].strip()
            ):
                raise

        # This deals with disappearing newlines on tty
        try:
            self.expect("\r\n", timeout=10)
        except TIMEOUT:
            self.sendline()
            self.expect("\r\n", timeout=10)

    # This deals with disappearing SIGINTs on tty
    def sendintr(self, retries=5, timeout=5, reset=0, wait=True):
        for i in range(retries):
            try:
                pexpect.spawn.sendintr(self)
                self.expect(re.escape("^C"), timeout)
                if wait:
                    return self.prompt(timeout, reset)
                break
            except TIMEOUT:
                if i == (retries - 1):
                    raise
        return None

    def is_at_prompt(self):
        if not self.after or not self._prompt:
            return False
        if not isinstance(self.after, six.string_types):
            return False
        match = re.match(self._prompt, self.after)
        return match is not None


class CLI(Shell):
    def __init__(  # pylint: disable=dangerous-default-value,too-many-arguments
        self,
        url,
        username="admin",
        password="",
        timeout=30,
        enable_cli_timeout=False,
        cli_flavor="mos",
        extra_args=[],
    ):
        o = six.moves.urllib.parse.urlparse(url)  # pylint: disable=invalid-name
        self.cmd = o.scheme
        if self.cmd == "ssh":
            self.args = ["%s@%s" % (username, o.hostname)]
            self.args += ["-o LogLevel ERROR"]
            self.args += ["-o StrictHostKeyChecking no"]
            self.args += ["-o UserKnownHostsFile /dev/null"]
            # default is whatever TCP timeout at OS level
            # self.args += ['-o ConnectTimeout 10']
            # self.args += ['-o ServerAliveCountMax 3']   # default 3
            # self.args += ['-o ServerAliveInterval 30']  # default 0
            self.args += ["-p %s" % (o.port or "22")]
            self.args += extra_args
        elif self.cmd in ("tcp", "telnet"):
            self.cmd = "mc"
            self.args = ["%s:%s" % (o.hostname, o.port)]
            self.args += extra_args
        elif self.cmd == "conserver":
            # Sample console spec: conserver://<netloc>/<path>
            # Executes:  console -f -M <netloc> -e^^^^ <path>
            conserver = o.netloc
            conport = o.path.strip("/")
            self.cmd = "console"
            self.args = ["-f", "-M", conserver, "-e^^^^", conport]
            self.args += extra_args
        else:
            self.args = [o.hostname, str(o.port)]
            self.args += extra_args
        Shell.__init__(
            self,
            self.cmd,
            self.args,
            timeout,
            dimensions=(60, 500),
            encoding="utf-8" if six.text_type == str else None,
        )
        self.logfile_read = sys.stdout
        self.delayafterterminate = 1
        self.delayafterclose = 1
        self.username = username
        self.password = password
        self.enable_cli_timeout = enable_cli_timeout
        self.cli_timeout = 0
        self.cli_flavor = cli_flavor
        self.device_generation = None
        self.plm_wd_supported = None
        self.serial = None
        self.micro_version = None

    def login(self, timeout=30):  # noqa: MC0001
        if self.cmd != "ssh":
            time0 = time.time()
            i = 0
            while True:
                if time.time() - time0 > timeout:
                    raise TIMEOUT("failed to login")

                index = self.expect(
                    [
                        TIMEOUT,
                        self.login_prompt_re_mos,
                        self.login_prompt_re_eos,
                        self.login_prompt_re_aboot,
                    ],
                    timeout=2,
                )

                print(" -- Got a login prompt index of {} -- ".format(index))

                if index == 1:
                    self.cli_flavor = "mos"
                    break

                if index == 2:
                    self.cli_flavor = "eos"
                    break

                if index == 3:
                    self.cli_flavor = "aboot"
                    break

                # Note that blindly sending EOFs and INTRs may break
                # some of the init scripts if the device is rebooting.
                if i % 2 == 0:
                    self.sendeof()
                else:
                    pexpect.spawn.sendintr(self)

                i += 1

            if self.cli_flavor != "aboot":
                self.sendline(self.username)
                self.expect(self.username + "(\r)?\r\n", timeout=10)
            else:
                self.sendline()

        print("\n -- Logged in. Sending password, etc. -- \n")

        if self.cli_flavor != "aboot":
            # This should also handle the case where a password prompt is presented
            # because a TACACS server has been configured even though there is no
            # password actually configured for the user.
            index = self.expect(
                [TIMEOUT, "Last login:.*\r\n", "Password:", "Aboot#"], timeout=10
            )
            if index == 2:
                self.sendline(self.password)

        print("\n -- Waiting for prompt -- \n")

        try:
            self.prompt(reset=1)
        except TIMEOUT:
            # Check if the CLI is busted or if previous tests left a password set
            try:
                index = self.expect(
                    ["Traceback", "Login incorrect", "Password:"], timeout=10
                )
                if index == 0:
                    raise Exception(  # pylint: disable=raise-missing-from
                        "CLI is busted, try logging in as root!"
                    )
                if index == 1:
                    self.expect("login:", timeout=2)
                    self.sendline(self.username)
                    self.expect(self.username + "(\r)?\r\n", timeout=10)
                    self.expect("Password:", timeout=10)
                    self.sendline("opensesame")  # This is used in some tests.
                    self.expect("Last login:.*\r\n", timeout=10)
                elif index == 2:
                    self.sendline("opensesame")  # This is used in some tests.
                    self.expect("Last login:.*\r\n", timeout=10)
                self.expect("Traceback", timeout=10)
                raise Exception(  # pylint: disable=raise-missing-from
                    "CLI is busted, try logging in as root!"
                )
            except TIMEOUT:
                self.prompt(reset=1)

        # Sometime there are weird control characters printed as "^[[0n"
        # on the first line that escape the control code filtering.
        # Resync just in case.
        self.sendline()
        self.prompt(reset=1)

        # Do standard setup for MOS/EOS.
        if self.cli_flavor != "aboot" and self.username != "root":
            # Sendcmd via Shell directly to avoid messing with cli_timeouts
            # since we do not yet know for sure what OS the device is running.
            show_version = self.sendcmd_simple("show version", timeout=10)
            matcher = re.search("Serial number:[ \t]*(.*)", show_version)
            if matcher:
                self.serial = matcher.group(1)

            matcher = re.search(
                r"System management controller version: (\d+)", show_version
            )
            if matcher:
                self.micro_version = matcher.group(1)

            # More reliably determine the CLI flavor
            # MOS does not have a 'Hardware version' field in "show version'
            matcher = re.search("Hardware version:", show_version)
            if matcher:
                self.cli_flavor = "eos"
            else:
                self.cli_flavor = "mos"

            # Check if previous tests left a password set
            try:
                self.sendcmd_simple("enable")
            except TIMEOUT:
                self.expect("Password:", timeout=10)
                self.sendline("opensesame")  # This is used in some tests.
                output = self.prompt(timeout=timeout, reset=1)
                self.process_output(output)

            self.sendcmd_simple(
                "bash echo ===> px Determined the {} CLI flavor".format(self.cli_flavor)
            )

            if self.cli_flavor == "mos":
                self.sendcmd_simple("set debug 1", timeout=10)

                # Set default cli timeout which
                # is the 2x the command timeout
                if self.enable_cli_timeout:
                    self.set_cli_timeout()

                # Determine device generation
                try:
                    output = self.sendcmd(
                        "bash python -m hal property chassis chassis_gen"
                    )
                    self.device_generation = int(output.strip())
                except Exception:  # pylint: disable=broad-except
                    plm_ver = self.sendcmd("bash i2cget -f -y 1 0x77 0x8 w").strip()
                    self.device_generation = 1 if int(plm_ver, 16) < 0x200 else 2

                # If Gen2 device, determine PLM watchdog support by
                # querying register PLM_VER_PATCH(0x7e)
                try:
                    if self.device_generation == 2:
                        plm_ver_patch = self.sendcmd(
                            "bash i2cget -f -y 1 0x77 0x7e b"
                        ).strip()
                        self.plm_wd_supported = plm_ver_patch != "0xdb"
                except Exception:  # pylint: disable=broad-except
                    pass

            self.sendcmd("show clock", timeout=timeout)

        if self.cmd != "ssh":
            # EOS and Aboot wrap lines at 80 chars on the console by default
            # and this breaks the command line echo regex, so tell it we have
            # a really wide terminal.  If our command lines ever hit 1000
            # chars we're doing something wrong :)
            if self.cli_flavor == "aboot":
                self.sendcmd("stty cols 1000")
            elif self.cli_flavor == "eos":
                self.sendcmd("bash stty cols 1000")

    def _can_insert_cli_timeout(self):
        return self.is_at_prompt()

    def set_cli_timeout(self, cli_timeout=-1):
        """Set the CLI timeout with the set timeout command.

        Does nothing if the timeout was already set.
        :param cli_timeout: CLI timeout in seconds. 0 is no timeout, -1 is the
        default (2 * self.timeout).
        :return:
        """
        if self.cli_flavor != "mos" or not self.enable_cli_timeout:
            return

        # If a CLI timeout is not specified set the default cli
        # timeout which is the 2x the command timeout.
        if cli_timeout == -1:
            cli_timeout = 2 * self.timeout

        if cli_timeout != self.cli_timeout:
            # We are at the prompt, safe to insert a timeout command
            if self._can_insert_cli_timeout():
                # Cache the cli timeout
                self.cli_timeout = cli_timeout

                # Failsafe in case the provided timeout is funky
                if cli_timeout > 0:
                    self.sendcmd_simple("set timeout {}".format(cli_timeout))
                else:
                    self.sendcmd_simple("no timeout")
            else:
                raise Exception("Not at CLI prompt")

    def sendcmd_simple(self, cmd="", timeout=-1, reset=0, wait=True):
        if wait:
            output = Shell.sendcmd(self, cmd, timeout, reset, wait)
            return self.process_output(output)

        Shell.sendcmd(self, cmd, timeout, reset, wait)
        return None

    def sendcmd(self, cmd="", timeout=-1, reset=0, wait=True):
        if timeout == -1:
            timeout = self.timeout

        cli_timeout = 0
        shell_timeout = 2 * timeout

        if self.enable_cli_timeout:
            # Timeout does not work as expected in sub-shells, stop it here.
            if wait and not cmd.strip().startswith(("bash", "python")):
                cli_timeout = 2 * timeout
                shell_timeout = 3 * timeout

            self.set_cli_timeout(cli_timeout)

        if wait:
            start_time = time.time()
            output = self.sendcmd_simple(cmd, shell_timeout, reset, wait)
            elapsed_time = time.time() - start_time

            if elapsed_time > timeout:
                if self.is_at_prompt():
                    raise CommandTimeoutError(cmd, timeout, elapsed_time)

                raise PromptTimeoutError(cmd, timeout, elapsed_time)

            return output

        self.sendcmd_simple(cmd, shell_timeout, reset, wait)
        return None

    @property
    def login_prompt_re(self):
        if self.cli_flavor == "mos":
            return self.login_prompt_re_mos
        if self.cli_flavor == "aboot":
            return self.login_prompt_re_aboot

        assert self.cli_flavor == "eos"
        return self.login_prompt_re_eos

    @property
    def login_prompt_re_eos(self):
        # "\S+" here is the host name, which is unset as EOS does not
        # Configure the management network by default
        return r"\r\n\S+ login: "

    @property
    def login_prompt_re_mos(self):
        return r"Metamako MOS \S+ \S+ (/dev/)?ttyS0\r\n\s*\r\n.*login: "

    @property
    def login_prompt_re_aboot(self):
        return r"Aboot# "

    def strip_control_codes(self, value):
        value = re.sub(r"\x1B([@-_][0-?]*[ -/]*[@-~]|.)", "", value)
        value = value.replace("\r", "")
        return value

    def process_output(self, output):
        output = self.strip_control_codes(output)
        matcher = re.search("^% (.*)$", output, re.M)
        if matcher:
            error = ExceptionPexpect(matcher.group(1))
            error.output = output
            raise error
        return output


class FlakyTimeoutError(Exception):
    def __init__(self, cmd, timeout, actual_time):
        super(FlakyTimeoutError, self).__init__(  # pylint: disable=super-with-arguments
            cmd, timeout, actual_time
        )
        self.cmd = cmd
        self.timeout = timeout
        self.actual_time = actual_time

    def __repr__(self):
        return "{}(cmd={!r}, timeout={!r}, actual_time={!r})".format(
            self.__class__.__name__, self.cmd, self.timeout, self.actual_time
        )

    def __str__(self):
        return self.__repr__()


class CommandTimeoutError(FlakyTimeoutError):
    def __repr__(self):
        return (
            "{}: "
            "command {!r} took longer than expected "
            "(actual time {!r}s, expected time {!r}s)"
        ).format(self.__class__.__name__, self.cmd, self.actual_time, self.timeout)


class PromptTimeoutError(FlakyTimeoutError):
    def __repr__(self):
        return (
            "{}: command {!r} didn't finish after {!r}s (expected time {!r}s)".format(
                self.__class__.__name__, self.cmd, self.actual_time, self.timeout
            )
        )


def run(  # pylint: disable=keyword-arg-before-vararg
    command, quiet=False, *args, **kwargs
):
    output, status = pexpect.run(command, withexitstatus=1, *args, **kwargs)
    if status != 0:
        if not quiet:
            print(output)
        raise subprocess.CalledProcessError(status, command)
    return output

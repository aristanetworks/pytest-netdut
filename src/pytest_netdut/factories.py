# -------------------------------------------------------------------------------
# - Copyright (c) 2021-2024 Arista Networks, Inc. All rights reserved.
# -------------------------------------------------------------------------------
# - Author:
# -   fdk-support@arista.com
# -
# - Description:
# -   Factories to create DUT fixtures
# -
# -   Licensed under BSD 3-clause license:
# -     https://opensource.org/licenses/BSD-3-Clause
# -
# - Tags:
# -   license-bsd-3-clause
# -
# -------------------------------------------------------------------------------
import logging
import re
import pytest
from packaging import version
from .wrappers import CLI, xapi
from functools import wraps

logger = logging.getLogger(__name__)


def create_dut_fixture(name):
    @pytest.fixture(name=f"{name}")
    def _dut(request):
        skipper = request.getfixturevalue(f"{name}_skipper")
        skipper(request.node)

        class Dut:
            def __getattr__(self, attr):
                return request.getfixturevalue(f"{name}_{attr}")

            @property
            def is_eos(self):
                return self.ssh.cli_flavor == "eos"

            @property
            def is_mos(self):
                return self.ssh.cli_flavor == "mos"

        yield Dut()

    return _dut


def create_eapi_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_eapi")
    def _eapi(eapi_enabled, request):
        hostname = request.getfixturevalue(f"{name}_hostname")
        ssh = request.getfixturevalue(f"{name}_ssh")
        with eapi_enabled(hostname, ssh, "http") as eapi:
            yield eapi

    return _eapi


def create_hostname_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_hostname")
    def _hostname(request):
        yield request.getfixturevalue(f"{name}_info")["hostname"]

    return _hostname


def create_console_url_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_console_url")
    def _console_url(request):
        yield request.getfixturevalue(f"{name}_info")["console_url"]

    return _console_url


def parse_version(v):
    """Return series of dot separated digits from beginning of string
    as release and the last group delimited by - as change number."""
    _regex = r"""
        (?P<release>[0-9]+(?:\.[0-9]+)*)
        (?:
            [-]?
            (?P<change_number>[\w]+)
        )*
    """
    _regex = re.compile(_regex, re.VERBOSE)
    # _regex = r"(?P<release>[\d\.]*)"
    parsed = re.match(_regex, v)
    return (parsed.group("release"), parsed.group("change_number"))


def version_skipper(found, expected):
    try:
        found = version.Version(str(found))
        expected = version.Version(str(expected))
        if found < expected:
            pytest.skip(f"min_version {expected} not satisfied: {found}")
    except version.InvalidVersion:
        logging.error("Could not parse versions: %s < %s", found, expected)


def create_skipper_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_skipper")
    def _skipper(request):
        def skipper(node):
            allowed_os = set()
            min_version = None
            min_chg_num = None

            # Restrict SKUs
            try:
                for marker in node.iter_markers():
                    if marker.name in {"mos", "eos"}:
                        allowed_os.add(marker.name)
                        min_chg_num = marker.kwargs.get("min_change_number", None)
                        min_version = marker.kwargs.get("min_version", None)

                    elif marker.name == "only_device_type":
                        pattern = marker.args[0]
                        sku = request.getfixturevalue(f"{name}_sku")
                        if not re.search(pattern, sku):
                            pytest.skip(f"Skipped on this SKU: {sku} (only runs on {pattern})")

                    elif marker.name == "skip_device_type":
                        pattern = marker.args[0]
                        sku = request.getfixturevalue(f"{name}_sku")
                        if re.search(pattern, sku):
                            pytest.skip(f"Skipped on this SKU: {sku}")

                if allowed_os:
                    dut_ssh = request.getfixturevalue(f"{name}_ssh")
                    dut_os_version = request.getfixturevalue(f"{name}_os_version")
                    if dut_ssh.cli_flavor not in allowed_os:
                        pytest.skip(f"Cannot run on platform {dut_ssh.cli_flavor}")
                    if min_version or min_chg_num:
                        # matches the pattern X.XX.X.XX with digits only
                        release, change_number = parse_version(dut_os_version)
                        if min_chg_num:
                            version_skipper(change_number, min_chg_num)
                        else:
                            version_skipper(release, min_version)
            except pytest.FixtureLookupError:
                logger.debug("Pytest fixture recursion caught.")

        return skipper

    return _skipper


def create_sku_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_sku")
    def _sku(request):
        ssh = request.getfixturevalue(f"{name}_ssh")
        assert ssh.cli_flavor in {"eos", "mos"}
        output = ssh.sendcmd("show version", timeout=300)
        match = re.search(r"(DCS-7.*)", output)
        logging.info("Got SKU: %s", match.group(1))
        yield match.group(1)

    return _sku


def create_os_version_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_os_version")
    def _os_version(request):
        ssh = request.getfixturevalue(f"{name}_ssh")
        assert ssh.cli_flavor in {"eos", "mos"}
        output = ssh.sendcmd("show version", timeout=300)
        if ssh.cli_flavor == "mos":
            match = re.search(r"Software image version: (\S*)", output)
        else:
            # On release SWIs the "Sofware image version" only contains the version, e.g.
            #   Software image version: 4.31.0F
            #   Architecture: x86_64
            #   Internal build version: 4.31.0F-33797590.4310F
            match = re.search(r"Internal build version: (\S*)", output)
        logging.info("Got OS version: %s", match.group(1))
        yield match.group(1)

    return _os_version


def create_softened_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_softened")
    def _softened(dut_ssh):
        # Set up a standard operating environment.
        dut_ssh.sendcmds(
            """
            enable
                configure
                    username admin privilege 15 nopassword
                    aaa authorization exec default local
        """
        )
        yield

        # FIXME: Return the running config to its pre-test state.

    return _softened


def retry(limit):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            attempt, limit_ = 0, limit
            result = None
            while attempt < limit_:
                try:
                    result = fn(*args, **kwargs)
                    break
                except Exception as e:
                    attempt += 1
                    logging.error(
                        "An error occurred in %s, attempt %d of %d: %s",
                        fn.__name__,
                        attempt,
                        limit_,
                        e,
                    )
            return result

        return wrapper

    return decorator


class _CLI_wrapper:
    _cli = None

    def __init__(self, *args, **kwargs):
        self._reinit_args = args
        self._reinit_kwargs = kwargs
        self.close_and_re_init()

    def close_and_re_init(self):
        if self._cli:
            del self._cli
        self._cli = CLI(*self._reinit_args, **self._reinit_kwargs)
        self.login()

    def close(self, *args, **kwargs):
        return self._cli.close(*args, **kwargs)

    @retry(3)
    def login(self, *args, **kwargs):
        return self._cli.login(*args, **kwargs)

    def set_cli_timeout(self, *args, **kwargs):
        return self._cli.set_cli_timeout(*args, **kwargs)

    def send(self, *args, **kwargs):
        return self._cli.send(*args, **kwargs)

    def sendcmd_simple(self, *args, **kwargs):
        return self._cli.sendcmd_simple(*args, **kwargs)

    def sendcmd_unchecked(self, *args, **kwargs):
        return self._cli.sendcmd_unchecked(*args, **kwargs)

    def sendcmd(self, *args, **kwargs):
        return self._cli.sendcmd(*args, **kwargs)

    def sendcmds(self, *args, **kwargs):
        return self._cli.sendcmds(*args, **kwargs)

    def expect(self, *args, **kwargs):
        return self._cli.expect(*args, **kwargs)

    def sendline(self, *args, **kwargs):
        return self._cli.sendline(*args, **kwargs)

    def sendintr(self, *args, **kwargs):
        return self._cli.sendintr(*args, **kwargs)

    def prompt(self, *args, **kwargs):
        return self._cli.prompt(*args, **kwargs)

    @property
    def cli_flavor(self):
        return self._cli.cli_flavor

    @cli_flavor.setter
    def cli_flavor(self, value):
        self._cli.cli_flavor = value

    @property
    def device_generation(self):
        return self._cli.device_generation

    @property
    def plm_wd_supported(self):
        return self._cli.plm_wd_supported

    @plm_wd_supported.setter
    def plm_wd_supported(self, value):
        self._cli.plm_wd_supported = value

    @property
    def serial(self):
        return self._cli.serial

    @property
    def micro_version(self):
        return self._cli.micro_version

    @property
    def username(self):
        return self._cli.username

    @property
    def password(self):
        return self._cli.password

    @property
    def before(self):
        return self._cli.before

    @property
    def args(self):
        return self._cli.args


def create_ssh_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_ssh")
    def _ssh(request):
        ssh = _CLI_wrapper(f"ssh://{request.getfixturevalue(f'{name}_hostname')}")
        # do not break the fixture if SSH failed
        # pass the failure into the test
        try:
            if ssh.cli_flavor == "mos":
                ssh.sendcmd("enable")
            # Disable pagination
            ssh.sendcmd("terminal length 0")
        except AttributeError:
            pass
        yield ssh

    return _ssh


def create_console_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_console")
    def _console(request):
        try:
            console_url = request.getfixturevalue(f"{name}_console_url")
            # Ignore encoding errors for the console -- various conditions
            # cause non-UTF-8 characters to be received.
            console = _CLI_wrapper(console_url, ignore_encoding_errors=True)
        except Exception as exc:
            logging.error("Failed to create console fixture and log in")
            raise exc
        if console.cli_flavor == "mos":
            console.sendcmd("enable")
        yield console

    return _console


def create_xapi_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_x")
    def _xapi(request):
        yield xapi(request.getfixturevalue(f"{name}_eapi"))

    return _xapi

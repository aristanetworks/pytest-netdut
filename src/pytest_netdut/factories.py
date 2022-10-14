# -------------------------------------------------------------------------------
# - Copyright (c) 2021 Arista Networks, Inc. All rights reserved.
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
from .wrappers import CLI, xapi


def create_dut_fixture(name):
    @pytest.fixture(name=f"{name}")
    def _dut(request):
        skipper = request.getfixturevalue(f"{name}_skipper")
        skipper(request.node)

        class Dut:
            def __getattr__(self, attr):
                return request.getfixturevalue(f"{name}_{attr}")

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


def create_skipper_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_skipper")
    def _skipper(request):
        def skipper(node):
            allowed_os = set()

            # Restrict SKUs
            for marker in node.iter_markers():
                if marker.name in {"mos", "eos"}:
                    allowed_os.add(marker.name)

                elif marker.name == "only_device_type":
                    pattern = marker.args[0]
                    sku = request.getfixturevalue(f"{name}_sku")
                    if not re.search(pattern, sku):
                        pytest.skip(
                            f"Skipped on this SKU: {sku} (only runs on {pattern})"
                        )

                elif marker.name == "skip_device_type":
                    pattern = marker.args[0]
                    sku = request.getfixturevalue(f"{name}_sku")
                    if re.search(pattern, sku):
                        pytest.skip(f"Skipped on this SKU: {sku}")

            if allowed_os:
                dut_ssh = request.getfixturevalue(f"{name}_ssh")
                if dut_ssh.cli_flavor not in allowed_os:
                    pytest.skip(f"cannot run on platform {dut_ssh.cli_flavor}")

        return skipper

    return _skipper


def create_sku_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_sku")
    def _sku(request):
        ssh = request.getfixturevalue(f"{name}_ssh")
        assert ssh.cli_flavor in {"eos", "mos"}
        output = ssh.sendcmd("show version", timeout=300)
        matcher = re.search(r"(DCS-7.*)", output)
        logging.info("Got SKU: %s", matcher.group(1))
        yield matcher.group(1)

    return _sku


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


def create_ssh_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_ssh")
    def _ssh(request):
        try:
            ssh = CLI(f"ssh://{request.getfixturevalue(f'{name}_hostname')}")
            ssh.login()
        except Exception as exc:
            logging.error("Failed to create ssh fixture and log in")
            raise exc
        if ssh.cli_flavor == "mos":
            ssh.sendcmd("enable")
        yield ssh

    return _ssh


def create_xapi_fixture(name):
    @pytest.fixture(scope="session", name=f"{name}_x")
    def _xapi(request):
        yield xapi(request.getfixturevalue(f"{name}_eapi"))

    return _xapi

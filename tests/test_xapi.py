# -------------------------------------------------------------------------------
# - Copyright (c) 2021-2022 Arista Networks, Inc. All rights reserved.
# -------------------------------------------------------------------------------
# - Author:
# -   fdk-support@arista.com
# -
# - Description:
# -   Tests for the xapi fixture.
# -
# -   Licensed under BSD 3-clause license:
# -     https://opensource.org/licenses/BSD-3-Clause
# -
# - Tags:
# -   license-bsd-3-clause
# -
# -------------------------------------------------------------------------------

import pytest
import pytest_netdut

pytest_plugins = ["pytest_mock"]


@pytest.fixture
def mock_eapi(mocker):
    def sendcmds(cmds):
        if cmds == ["show version"]:
            return [
                {
                    "architecture": "x86_64",
                    "bootupTimestamp": 1628827627.0,
                    "configMacAddress": "00:00:00:00:00:00",
                    "hardwareRevision": "01.03",
                    "hwMacAddress": "7c:53:4a:d3:67:80",
                    "imageFormatVersion": "01.00",
                    "internalBuildId": "43757e25-1545-4d6c-b200-c768cb3053fb",
                    "internalVersion": "4.26.1FX-7130-22950577.4261FX7130",
                    "isIntlVersion": False,
                    "memFree": 6021356,
                    "memTotal": 8083948,
                    "mfgName": "Metamako",
                    "modelName": "DCS-7130-48L-R",
                    "serialNumber": "M48L-A3-54119-2",
                    "systemMacAddress": "7c:53:4a:d3:67:80",
                    "uptime": 29857.29,
                    "version": "4.26.1FX-7130",
                },
            ]

    eapi = mocker.MagicMock()
    eapi.sendcmds = mocker.MagicMock(side_effect=sendcmds)
    yield eapi


@pytest.fixture
def mock_xapi(mock_eapi):
    yield pytest_netdut.xapi(mock_eapi)


def test_xapi_show_version(mock_xapi):
    result = mock_xapi.show_version()
    assert result["version"] == "4.26.1FX-7130"

# -------------------------------------------------------------------------------
# - Copyright (c) 2021-2022 Arista Networks, Inc. All rights reserved.
# -------------------------------------------------------------------------------
# - Author:
# -   fdk-support@arista.com
# -
# - Description:
# -   Tests for the EAPI translator.
# -
# -   Licensed under BSD 3-clause license:
# -     https://opensource.org/licenses/BSD-3-Clause
# -
# - Tags:
# -   license-bsd-3-clause
# -
# -------------------------------------------------------------------------------

import pytest

pytest_plugins = ["pytest_mock"]


@pytest.fixture
def mock_pyeapi():
    class pyeapi:
        def connect(self, host=None, transport=None):
            return self

        def execute(self, cmds):
            if len(cmds) > 1:
                return {
                    "result": [
                        {"appName": "null"},
                        {"app_name": "null"},
                        "Application is already running",
                    ]
                }
            else:
                return {"result": [{"appName": "null"}]}

    yield pyeapi


def test_eapi_translator(mocker, mock_pyeapi):
    mocker.patch("pytest_netdut.wrappers.pyeapi", mock_pyeapi())
    import pytest_netdut

    eapi = pytest_netdut.wrappers.EAPI("mock_host", "mock_transport")
    eapi.set_translator(pytest_netdut.wrappers.MosTranslator())

    result = eapi.sendcmd(["one_command"])
    assert "app_name" in result

    result = eapi.sendcmds(["one_command", "two_command"])
    assert "app_name" in result[0]
    assert "app_name" in result[1]
    assert "Application is already running" in result[2]

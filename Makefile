# -------------------------------------------------------------------------------
# - Copyright (c) 2021-2022 Arista Networks, Inc. All rights reserved.
# -------------------------------------------------------------------------------
# - Author:
# -   fdk-support@arista.com
# -
# - Description:
# -   Makefile to build pytest-netdut tests.
# -
# -   Licensed under BSD 3-clause license:
# -     https://opensource.org/licenses/BSD-3-Clause
# -
# - Tags:
# -   license-bsd-3-clause
# -
# -------------------------------------------------------------------------------

BUILD_DIR=$(CURDIR)/build

.PHONY:tox_docker package_docker mkdocs_docker ci all clean
.SECONDEXPANSION:

all: package_docker
ci: tox_docker

# Any target that ends in a slash is a directory to be mkdir'd
%/:
	mkdir -p $@

tox_docker: |$(BUILD_DIR)/
	rm -rf $(BUILD_DIR)/test-reports
	DOCKER_BUILDKIT=1 docker build . --target=results  --output=type=local,dest=$(BUILD_DIR)/test-reports && \
		touch $(BUILD_DIR)/test-reports/*.xml

mkdocs_docker: |$(BUILD_DIR)
	DOCKER_BUILDKIT=1 docker build . --target=docs  --output=type=local,dest=$(BUILD_DIR)/docs

package_docker: |$(BUILD_DIR)/
	DOCKER_BUILDKIT=1 docker build . --target=package --output=type=local,dest=$(BUILD_DIR)/dist

clean:
	rm -rf $(BUILD_DIR)

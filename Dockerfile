FROM fedora:42 AS base

RUN dnf -y update && dnf clean all
RUN dnf -y install python3.9 python3.10 python3.11 python3.12 python3.13 tox git && dnf clean all
RUN python3 -m pip install --upgrade build twine mkdocs && dnf clean all

FROM base AS build
ADD . /src
WORKDIR /src

CMD ["tox"]

# Recipes to run tox
FROM build AS run
RUN tox

FROM scratch AS results
COPY --from=run /src/test-reports /

# Recipes to build the documentation
FROM build AS build_docs
RUN pip3 install pyeapi pexpect
RUN mkdocs build

FROM scratch AS docs
COPY --from=build_docs /src/site /

# Recipes to build the distribution package
FROM build AS build_package
RUN python3 -m build && twine check dist/*

FROM scratch AS package
COPY --from=build_package /src/dist/ /

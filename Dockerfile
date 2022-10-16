FROM fedora:34 as base

RUN dnf -y update && dnf clean all
RUN dnf -y install python3.6 python3.7 python3.8 python3.9 python3.10 pypy3 tox git && dnf clean all
RUN python3 -m pip install --upgrade build twine mkdocs && dnf clean all

FROM base as build
ADD . /src
WORKDIR /src

CMD ["tox"]

# Recipes to run tox
FROM build as run
RUN tox --parallel

FROM scratch as results
COPY --from=run /src/test-reports /

# Recipes to build the documentation
FROM build as build_docs
RUN pip3 install pyeapi pexpect
RUN mkdocs build

FROM scratch as docs
COPY --from=build_docs /src/site /

# Recipes to build the distribution package
FROM build as build_package
RUN python3 -m build && twine check dist/*

FROM scratch as package
COPY --from=build_package /src/dist/ /
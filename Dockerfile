FROM python:3.10.6

RUN useradd --create-home --shell /bin/bash gingerbread

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        libpotrace-dev \
        cmake \
        libcairo2 \
        libpango1.0-0 \
        libpangocairo-1.0-0 \
        libvips42 \
    ; \
    rm -rf /var/lib/apt/lists/*;

WORKDIR /home/gingerbread
USER gingerbread

COPY . gingerbread
RUN pip --version
RUN pip install ./gingerbread

VOLUME /workdir
WORKDIR /workdir

entrypoint ["python3", "-m"]

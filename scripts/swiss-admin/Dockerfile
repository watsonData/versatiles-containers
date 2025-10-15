# syntax=docker/dockerfile:1
FROM ghcr.io/osgeo/gdal:ubuntu-full-latest AS base
WORKDIR /code
RUN apt-get update
RUN apt-get install -y git build-essential gcc g++ make libsqlite3-dev zlib1g-dev
RUN git clone https://github.com/felt/tippecanoe.git --depth=1
WORKDIR /code/tippecanoe
RUN make
RUN make install

FROM base AS versatiles

RUN apt-get install -y curl
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"
RUN cargo install versatiles

FROM versatiles AS final
WORKDIR /code
CMD ["/bin/bash", "-l"]

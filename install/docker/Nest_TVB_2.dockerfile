#Copyright 2020 Forschungszentrum Jülich GmbH and Aix-Marseille Université
#Licensed to the Apache Software Foundation (ASF) under one
#or more contributor license agreements.  See the NOTICE file
#distributed with this work for additional information
#regarding copyright ownership.  The ASF licenses this file
#to you under the Apache License, Version 2.0 (the
#"License"); you may not use this file except in compliance
#with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing,
#software distributed under the License is distributed on an
#"AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
#KIND, either express or implied.  See the License for the
#specific language governing permissions and limitations
#under the License.

# ---- Builder Stage ----
# This stage compiles the application and all its dependencies.
FROM debian:bullseye-slim AS builder

SHELL ["/bin/bash", "-c"]

# Set environment variables to non-interactive
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# 1. Install build-time system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    g++ gcc gfortran \
    make wget cmake curl \
    python3 python3-dev python3-pip python3-venv \
    libltdl-dev libreadline-dev libncurses-dev libgsl-dev liblapack-dev \
    llvm-11-dev llvm-11 \
    sudo jq \
    && rm -rf /var/lib/apt/lists/*

# 2. Install MPICH
RUN wget -q http://www.mpich.org/static/downloads/3.1.4/mpich-3.1.4.tar.gz && \
    tar xf mpich-3.1.4.tar.gz && \
    cd mpich-3.1.4 && \
    ./configure --disable-fortran && make -j$(nproc) && make install && \
    cd .. && rm -rf mpich-3.1.4.tar.gz mpich-3.1.4

# 3. Install and configure uv
RUN --mount=type=cache,target=/root/.cache/uv \
    curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# 4. Install Python BUILD dependencies for NEST
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system nose numpy cython mpi4py

# 5. Copy and build NEST
COPY ./nest-io-dev /home/nest-io-dev
RUN mkdir /home/nest_build && cd /home/nest_build && \
    cmake /home/nest-io-dev \
    -DCMAKE_INSTALL_PREFIX:PATH=/opt/nest \
    -Dwith-mpi=ON -Dwith-python=ON -Dwith-openmp=ON -Dwith-gsl=ON -Dwith-readline=ON \
    && make -j$(nproc) && make install

# 6a. Install core Python runtime dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system Pillow matplotlib scipy numpy

# 6b. Install scientific analysis dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system elephant networkx viziphant

# 6c. Install development and testing tools
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system jupyterlab ipykernel pyyaml pydantic

# 6d. Install CLI and configuration tools
# RUN --mount=type=cache,target=/root/.cache/uv \
#     uv pip install --system typer rich hydra-core omegaconf cerberus

# 6e. Install testing framework
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system pytest pytest-cov

# 6f. Install TVB dependencies with LLVM configuration
RUN --mount=type=cache,target=/root/.cache/uv \
    export LLVM_CONFIG=$(which llvm-config-11) && \
    uv pip install --system tvb-data tvb-gdist tvb-library

# 7. Configure Jupyter Kernel
ENV PYTHONPATH="/opt/nest/lib/python3.9/site-packages:/usr/local/lib/python3.9/dist-packages:/home"
ENV LD_LIBRARY_PATH="/opt/nest/lib:/opt/nest/lib/nest:/usr/local/lib"
RUN KERNEL_PATH=$(jupyter kernelspec list | grep python3 | awk '{print $2}') && \
    if [ -f "$KERNEL_PATH/kernel.json" ]; then \
        jq --arg pypath "$PYTHONPATH" --arg ldpath "$LD_LIBRARY_PATH" \
           '. + {"env": {"PYTHONPATH": $pypath, "LD_LIBRARY_PATH": $ldpath}}' \
           "$KERNEL_PATH/kernel.json" > "$KERNEL_PATH/kernel.json.tmp" && \
        mv "$KERNEL_PATH/kernel.json.tmp" "$KERNEL_PATH/kernel.json"; \
    fi

# ---- Final Stage ----
FROM debian:bullseye-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Etc/UTC

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgsl25 liblapack3 libltdl7 libreadline8 libncurses6 python3 libgomp1 sudo \
    python3-dev make procps htop \
    && rm -rf /var/lib/apt/lists/*

# Copy all compiled artifacts from builder
COPY --from=builder /opt/nest /opt/nest
COPY --from=builder /usr/local /usr/local
COPY --from=builder /root/.local /root/.local
# Copy missing Python utility files from source
COPY --from=builder /home/nest-io-dev/pynest/ /opt/nest/lib/python3.9/site-packages/

# Set final environment variables
ENV PATH=/opt/nest/bin:/root/.local/bin:$PATH
ENV PYTHONPATH=/opt/nest/lib/python3.9/site-packages:/usr/local/lib/python3.9/dist-packages:/home
ENV LD_LIBRARY_PATH=/opt/nest/lib:/opt/nest/lib/nest:/usr/local/lib

WORKDIR /home
CMD ["/bin/bash"]


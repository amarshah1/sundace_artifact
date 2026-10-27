# syntax=docker/dockerfile:1
#
# Reproducibility image for "Sundance: A Simple SMT Solver for Program Verification".
# Z3, cvc5 and Alt-Ergo are the versions of the paper's evaluation; Sundance is built from GitHub. See README.md.
#
# Build:
#   docker buildx build -t sundance-artifact .
#
# Never publish ports from this image; nothing in it listens on a socket.

ARG UBUNTU=ubuntu:24.04@sha256:68ee22004a9109b44973313b02ff7b1de250f1de0f5ecb628d73f579aaff33ac

###############################################################################
# Prebuilt solver binaries (amd64 and arm64), verified by sha256
###############################################################################
FROM ${UBUNTU} AS solvers
# Set by Docker (BuildKit) to the architecture being built: amd64 or arm64.
ARG TARGETARCH
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates curl unzip && rm -rf /var/lib/apt/lists/*
WORKDIR /dl
# Z3 5.3.0: the z3 executable from the PyPI wheel (amd64: the exact binary the paper's run used).
# cvc5 1.4.2: the static, non-GPL release build (amd64: the exact binary the paper's run used).
# libz3 4.13.4: linked into Sundance (cargo feature local-z3) for --arithmetic z3incremental.
# The release archives are checked by sha256; on amd64 the extracted binaries are checked too.
RUN set -eu; arch=${TARGETARCH:-$(dpkg --print-architecture)}; \
    case "$arch" in \
      amd64) \
        z3_url=https://files.pythonhosted.org/packages/c6/e4/89f493134882bf3c4e5e932ba593562fd5b59b8f36fd5caaa95be7c426b4/z3_solver-5.3.0.0-py3-none-manylinux_2_27_x86_64.whl; \
        z3_sha=b69e5ae0d82ecfc93cfdf19c4096daff479a1c59476590418d115b7f80d73a45; \
        z3_bin_sha=4da6a0f78424098b600a9112ebb9d8ce45de248a4913c26dd7d472e6dabef6d3; \
        cvc5_url=https://github.com/cvc5/cvc5/releases/download/cvc5-1.4.2/cvc5-Linux-x86_64-static.zip; \
        cvc5_sha=7eb18f8c814c36a46c5a7d003983e9cfbc4b0a9828d6dd596239291bd4cc61d8; \
        cvc5_bin_sha=6aecddf466552b83bb5883756c7955e0c9d5ddcc6d7f45b48c2f6e06a741b102; \
        libz3=z3-4.13.4-x64-glibc-2.35; \
        libz3_sha=93f91f9c6f4a00a041c19fc7a74adc1f441c8244ce70d486e19abcd89c6a014b ;; \
      arm64) \
        z3_url=https://files.pythonhosted.org/packages/45/c5/447e09a152b4e676624c92912635b9f41076280926eaa5524f857acea521/z3_solver-5.3.0.0-py3-none-manylinux_2_38_aarch64.whl; \
        z3_sha=11d1d29ba33727f062bf91b717a2a5bc52d543a6c84891f121358cc3586f69e7; \
        z3_bin_sha=9b60ef8d25a9679fd62b1996e4b6b2c605ff1423a1209430c08fe517fd24b430; \
        cvc5_url=https://github.com/cvc5/cvc5/releases/download/cvc5-1.4.2/cvc5-Linux-arm64-static.zip; \
        cvc5_sha=765ebee59d9e5efccb60a445fa66fbddfb07a8de9fe7a5b6d128e5c2aafec974; \
        cvc5_bin_sha=; \
        libz3=z3-4.13.4-arm64-glibc-2.34; \
        libz3_sha=37533e7a06f82ac28d9dfe9c10dc143013afbca2515dc236cce35b952808b2b9 ;; \
      *) echo "unsupported architecture: $arch (supported: amd64, arm64)" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o z3.whl "$z3_url" && echo "$z3_sha  z3.whl" | sha256sum -c -; \
    unzip -q z3.whl 'z3_solver-5.3.0.0.data/data/bin/z3'; \
    install -D -m 755 z3_solver-5.3.0.0.data/data/bin/z3 /opt/solvers/z3-5.3.0/z3; \
    echo "$z3_bin_sha  /opt/solvers/z3-5.3.0/z3" | sha256sum -c -; \
    curl -fsSL -o cvc5.zip "$cvc5_url" && echo "$cvc5_sha  cvc5.zip" | sha256sum -c -; \
    mkdir cvc5 && unzip -q cvc5.zip -d cvc5; \
    install -D -m 755 "$(find cvc5 -path '*/bin/cvc5' | head -1)" /opt/solvers/cvc5-1.4.2/cvc5; \
    cp "$(find cvc5 -name COPYING | head -1)" /opt/solvers/cvc5-1.4.2/COPYING; \
    if [ -n "$cvc5_bin_sha" ]; then echo "$cvc5_bin_sha  /opt/solvers/cvc5-1.4.2/cvc5" | sha256sum -c -; fi; \
    curl -fsSL -o libz3.zip "https://github.com/Z3Prover/z3/releases/download/z3-4.13.4/$libz3.zip"; \
    echo "$libz3_sha  libz3.zip" | sha256sum -c -; \
    unzip -q libz3.zip; \
    mkdir -p /opt/z3-4.13.4/lib && cp -r "$libz3/include" /opt/z3-4.13.4/; \
    cp "$libz3/bin/libz3.so" /opt/z3-4.13.4/lib/ && cp "$libz3/LICENSE.txt" /opt/z3-4.13.4/; \
    cp "$libz3/LICENSE.txt" /opt/solvers/z3-5.3.0/LICENSE.txt; \
    /opt/solvers/z3-5.3.0/z3 --version && /opt/solvers/cvc5-1.4.2/cvc5 --version | head -1

###############################################################################
# Alt-Ergo: alt-ergo-free 2.4.3 (CeCILL-C), built with opam on OCaml 5.2.1, as in the run
###############################################################################
FROM ${UBUNTU} AS altergo
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates curl git opam build-essential m4 pkg-config autoconf libgmp-dev zlib1g-dev unzip \
    && rm -rf /var/lib/apt/lists/*
ENV OPAMYES=1 OPAMROOTISOK=1
# opam-repository pinned to the commit current when the run's switch was created (2026-10-14 ~15:54 UTC)
RUN opam init --bare --disable-sandboxing -n default \
        "git+https://github.com/ocaml/opam-repository.git#820008e4fe2dba60074e90839ffd21f9da0f7ff3" \
 && opam switch create ae-free-ocaml5 ocaml-base-compiler.5.2.1
# Package versions = the run's switch (~/.opam/ae-free-ocaml5/.opam-switch/switch-state)
RUN opam install --switch=ae-free-ocaml5 alt-ergo-free.2.4.3 camlzip.1.14 cmdliner.1.3.0 dune.3.24.2 \
        menhir.20260209 num.1.6 ocamlfind.1.9.8 ocplib-simplex.0.4.1 psmt2-frontend.0.4.0 \
        stdlib-shims.0.3.0 zarith.1.14 csexp.1.5.2 \
 && install -D -m 755 "$(opam var --switch=ae-free-ocaml5 bin)/alt-ergo" /opt/solvers/alt-ergo-2.4.3-free/alt-ergo \
 && /opt/solvers/alt-ergo-2.4.3-free/alt-ergo --version \
 && opam list --switch=ae-free-ocaml5 --installed --columns=name,version > /opt/solvers/alt-ergo-2.4.3-free/opam-packages.txt \
 && (cp "$(opam var --switch=ae-free-ocaml5 doc)"/alt-ergo-free/LICENSE* /opt/solvers/alt-ergo-2.4.3-free/ 2>/dev/null \
     || find "$(opam var --switch=ae-free-ocaml5 prefix)" -path '*alt-ergo*' -iname 'LICENSE*' -exec cp {} /opt/solvers/alt-ergo-2.4.3-free/ \; ) \
 && ls /opt/solvers/alt-ergo-2.4.3-free/

###############################################################################
# Sundance: built from source (github.com/yaspar-org/Sundance-SMT). Its configurations are runtime flags.
###############################################################################
FROM ${UBUNTU} AS sundance
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates curl git build-essential pkg-config clang libclang-dev cmake zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
ENV RUSTUP_HOME=/opt/rustup CARGO_HOME=/opt/cargo PATH=/opt/cargo/bin:$PATH
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain 1.96.0
COPY --from=solvers /opt/z3-4.13.4 /opt/z3-4.13.4
ARG SUNDANCE_REPO=https://github.com/yaspar-org/Sundance-SMT.git
# Latest main at the time of writing (2026-10-26, #247). Override with --build-arg SUNDANCE_COMMIT=<commit>.
ARG SUNDANCE_COMMIT=c17505996a5405135d989334f45738903960bccf
COPY --chmod=755 docker/build_sundance.sh /usr/local/bin/build_sundance.sh
COPY docker/ /ctx/docker/
# Features: local-z3 (links libz3 4.13.4, for --arithmetic z3incremental) and minisat (for --sat-backend minisat)
RUN build_sundance.sh "$SUNDANCE_REPO" "$SUNDANCE_COMMIT" local-z3,minisat

###############################################################################
# tokei 15.0.0: the line counter used for the paper's LoC numbers
###############################################################################
FROM sundance AS tools
RUN cargo +1.96.0 install tokei --version 15.0.0 --locked --root /opt/tokei

###############################################################################
# Runtime image
###############################################################################
FROM ${UBUNTU}
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3 python3-matplotlib libgmp10 zlib1g git ca-certificates curl xz-utils \
    && rm -rf /var/lib/apt/lists/*
COPY --from=solvers /opt/solvers /opt/solvers
COPY --from=solvers /opt/z3-4.13.4 /opt/z3-4.13.4
COPY --from=altergo /opt/solvers/alt-ergo-2.4.3-free /opt/solvers/alt-ergo-2.4.3-free
COPY --from=sundance /opt/sundance /opt/sundance
COPY --from=tools /opt/tokei/bin/tokei /usr/local/bin/tokei
COPY scripts/ /artifact/scripts/
COPY manifests/ /artifact/manifests/
COPY paper_results/ /artifact/paper_results/
COPY README.md run.sh /artifact/
ENV LD_LIBRARY_PATH=/opt/z3-4.13.4/lib \
    PATH=/artifact/scripts:/opt/sundance/bin:/opt/solvers/z3-5.3.0:/opt/solvers/cvc5-1.4.2:/opt/solvers/alt-ergo-2.4.3-free:$PATH \
    BENCH_ROOT=/benchmarks RESULTS_ROOT=/results
WORKDIR /artifact
CMD ["bash", "-lc", "cat /artifact/README.md"]

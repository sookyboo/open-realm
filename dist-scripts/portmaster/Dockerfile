# syntax=docker/dockerfile:1

# Build a pinned FFmpeg shared runtime for the PortMaster AArch64 package.
FROM ubuntu:22.04 AS ffmpeg-builder
ARG TARGETARCH
ARG FFMPEG_VERSION=6.1.6
ARG FFMPEG_SHA256=d4fcb164028dd3beee5d92c0ac72e46aac6973c75ea12dc14de07bf8f407370a
ENV DEBIAN_FRONTEND=noninteractive
RUN test "${TARGETARCH}" = arm64 && test "$(dpkg --print-architecture)" = arm64
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates curl pkg-config xz-utils zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    curl --fail --location --retry 3 --output /tmp/ffmpeg.tar.xz \
        "https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.xz"; \
    echo "${FFMPEG_SHA256}  /tmp/ffmpeg.tar.xz" | sha256sum -c -; \
    mkdir -p /usr/src/ffmpeg /opt/ffmpeg-aarch64; \
    tar -xJf /tmp/ffmpeg.tar.xz --strip-components=1 -C /usr/src/ffmpeg
WORKDIR /usr/src/ffmpeg
# Keep the decoder/demuxer set broad for WC3 music and movies; omit GPL and
# nonfree components and build only the shared libraries used by the engine.
RUN set -eux; \
    ./configure \
        --prefix=/opt/ffmpeg-aarch64 \
        --target-os=linux --arch=aarch64 \
        --enable-shared --disable-static \
        --disable-programs --disable-doc --disable-debug \
        --disable-avdevice --disable-avfilter --disable-postproc \
        --disable-encoders --disable-muxers \
        --disable-network --disable-autodetect --enable-zlib \
        --disable-gpl --disable-nonfree; \
    make -j4; \
    make install

# PortMaster-supported CFWs use an Ubuntu 22.04-compatible libc baseline.
FROM ubuntu:22.04 AS builder
ARG TARGETARCH
ENV DEBIAN_FRONTEND=noninteractive
RUN test "${TARGETARCH}" = arm64
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential ca-certificates pkg-config findutils gawk binutils \
    libsdl2-dev libegl1-mesa-dev libgles2-mesa-dev \
    zlib1g-dev libjpeg-dev zip unzip \
 && rm -rf /var/lib/apt/lists/*
RUN test "$(dpkg --print-architecture)" = arm64
COPY --from=ffmpeg-builder /opt/ffmpeg-aarch64 /opt/ffmpeg-aarch64

# build.sh supplies the repository root as the Docker build context.
WORKDIR /src
COPY . .

# Build against the pinned FFmpeg shared libraries and keep the normal dynamic
# pkg-config link mode used by developer builds.
RUN make clean && \
    make \
      BUILD=release \
      GL_BACKEND=gles3 \
      MSAA=0 \
      FFMPEG=1 \
      PKG_CONFIG_PATH=/opt/ffmpeg-aarch64/lib/pkgconfig \
      openwarcraft3 \
      build/bin/isoextract \
      build/bin/wc3setup

RUN set -eux; \
    mkdir -p /src/release; \
    cp build/bin/openwarcraft3 /src/release/openwarcraft3.aarch64; \
    cp -a build/lib/. /src/release/; \
    cp build/bin/isoextract /src/release/isoextract.aarch64; \
    cp build/bin/wc3setup /src/release/wc3setup.aarch64

# Assemble the PortMaster ZIP and bundle the five FFmpeg runtime libraries.
RUN set -eux; \
    PM_SRC=/src/dist-scripts/portmaster; \
    PKG_ROOT=/src/portmaster.package; \
    PKG_DIR="${PKG_ROOT}/open-realm-wc3"; \
    rm -rf "${PKG_ROOT}"; \
    mkdir -p \
        "${PKG_DIR}/libs.aarch64" \
        "${PKG_DIR}/gamefiles/warcraft-3" \
        "${PKG_DIR}/licenses"; \
    for file in open-realm-wc3.sh openrealm-wc3.gptk2.ini port.json gameinfo.xml; do \
        test -f "${PM_SRC}/${file}"; \
    done; \
    cp "${PM_SRC}/open-realm-wc3.sh" "${PKG_ROOT}/open-realm-wc3.sh"; \
    chmod +x "${PKG_ROOT}/open-realm-wc3.sh"; \
    cp "${PM_SRC}/port.json" "${PM_SRC}/gameinfo.xml" \
        "${PM_SRC}/openrealm-wc3.gptk2.ini" \
        "${PM_SRC}/WC3-ISO-IMPORT.md" "${PKG_DIR}/"; \
    cp /src/release/openwarcraft3.aarch64 "${PKG_DIR}/"; \
    chmod +x "${PKG_DIR}/openwarcraft3.aarch64"; \
    cp /src/release/isoextract.aarch64 /src/release/wc3setup.aarch64 "${PKG_DIR}/"; \
    chmod +x "${PKG_DIR}/isoextract.aarch64" "${PKG_DIR}/wc3setup.aarch64"; \
    for lib in /src/release/*.so* /opt/ffmpeg-aarch64/lib/*.so*; do \
        [ -e "${lib}" ] || continue; \
        cp -a "${lib}" "${PKG_DIR}/libs.aarch64/"; \
    done; \
    if [ -d /src/build/share ]; then \
        cp -a /src/build/share "${PKG_DIR}/share"; \
    fi; \
    if [ -f /src/LICENSE ]; then \
        cp /src/LICENSE "${PKG_DIR}/licenses/open-realm-LICENSE.txt"; \
    fi; \
    mkdir -p "${PKG_DIR}/licenses/ffmpeg"; \
    cp /usr/src/ffmpeg/LICENSE.md /usr/src/ffmpeg/COPYING.LGPLv2.1 \
        "${PKG_DIR}/licenses/ffmpeg/"; \
    printf '%s\n' \
        'FFmpeg 6.1.6 (LGPL shared-library build)' \
        'Source: https://ffmpeg.org/releases/ffmpeg-6.1.6.tar.xz' \
        'SHA256: d4fcb164028dd3beee5d92c0ac72e46aac6973c75ea12dc14de07bf8f407370a' \
        'Build: Ubuntu 22.04, AArch64; configure flags in Dockerfile' \
        > "${PKG_DIR}/licenses/ffmpeg/BUILD-INFO.txt"; \
    touch "${PKG_DIR}/gamefiles/warcraft-3/.gitkeep"; \
    "${PM_SRC}/verify-dynamic-ffmpeg.sh" "${PKG_DIR}"; \
    rm -f /src/release/open-realm-wc3.zip; \
    cd "${PKG_ROOT}"; \
    zip -9 -r /src/release/open-realm-wc3.zip .; \
    unzip -t /src/release/open-realm-wc3.zip; \
    "${PM_SRC}/verify-dynamic-ffmpeg.sh" "${PKG_DIR}" /src/release/open-realm-wc3.zip

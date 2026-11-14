# PortMaster AArch64: shared FFmpeg build and packaging

## Build

`dist-scripts/portmaster/build.sh` builds the Warcraft III PortMaster package in
an Ubuntu 22.04 AArch64 Docker environment. Its first stage builds pinned
FFmpeg 6.1.6 shared libraries from the upstream source archive. The build
checks the source SHA-256 before compiling:

```text
d4fcb164028dd3beee5d92c0ac72e46aac6973c75ea12dc14de07bf8f407370a
```

The configure options omit GPL and nonfree components, disable FFmpeg command
line programs, encoding, muxing, network support, and unused device/filter
libraries, while retaining built-in decoders and demuxers for WC3 music and
movies. The OpenRealm executable links dynamically through the standard
`pkg-config` packages. No `FFMPEG_STATIC` mode is used; regular developer builds
continue to use their system FFmpeg packages with `FFMPEG=1`.

On x86_64, ARM64 Docker emulation is required. The build script checks for it;
install binfmt support if needed:

```sh
docker run --privileged --rm tonistiigi/binfmt --install arm64
./dist-scripts/portmaster/build.sh
```

The output is `build/open-realm-wc3.zip`.

## Runtime packaging

The five FFmpeg shared libraries (`libavformat`, `libavcodec`, `libavutil`,
`libswscale`, and `libswresample`) are copied into `open-realm-wc3/libs.aarch64/`
with the other engine runtime libraries. The executable's `DT_NEEDED` entries
resolve to those files at runtime through the PortMaster launcher's existing
`LD_LIBRARY_PATH`. The package includes the upstream LGPL license notices.
No FFmpeg static archives, headers, or relink object are needed for this shared
runtime package.

`verify-dynamic-ffmpeg.sh` runs before and after ZIP creation. It checks that
the executable and each bundled FFmpeg library are AArch64 ELF files, that the
five FFmpeg shared dependencies resolve to packaged library files, that the
license notices are present, and that the ZIP contains the resolved libraries.

The general Warcraft III media documentation covers decoder behavior:
[music](../games/warcraft-3/music.md) and
[pre-rendered movies](../games/warcraft-3/pre-rendered-movies.md).

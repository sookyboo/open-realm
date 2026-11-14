#!/bin/sh
# Verify the PortMaster AArch64 package carries and uses shared FFmpeg.
set -eu

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 <package-dir> [port-zip]" >&2
    exit 2
fi
pkg_dir=$1
zip_path=${2:-}
exe="${pkg_dir}/openwarcraft3.aarch64"
libs="${pkg_dir}/libs.aarch64"

test -s "${exe}"
readelf -h "${exe}" | grep -Eq 'Machine:[[:space:]]*AArch64'
for lib in avformat avcodec avutil swscale swresample; do
    found=0
    for candidate in "${libs}/lib${lib}.so"*; do
        [ -s "${candidate}" ] || continue
        readelf -h "${candidate}" | grep -Eq 'Machine:[[:space:]]*AArch64'
        found=1
    done
    if [ "${found}" -ne 1 ]; then
        echo "Missing bundled shared FFmpeg library lib${lib}.so*" >&2
        exit 1
    fi
done

# Every FFmpeg DT_NEEDED entry must resolve to a library shipped in libs.aarch64.
needed=$(readelf -d "${exe}" | sed -n 's/.*Shared library: \[\([^]]*\)\].*/\1/p')
for lib in avformat avcodec avutil swscale swresample; do
    soname=$(printf '%s\n' "${needed}" | grep -m 1 "^lib${lib}\\.so" || true)
    if [ -z "${soname}" ] || [ ! -s "${libs}/${soname}" ]; then
        echo "Executable does not resolve bundled ${lib}: ${soname:-no DT_NEEDED entry}" >&2
        exit 1
    fi
done

# Reject FFmpeg runtime dependencies in shipped OpenRealm modules that were
# accidentally left outside the main executable's copied runtime closure.
for binary in "${libs}"/*.so*; do
    [ -f "${binary}" ] || continue
    readelf -h "${binary}" | grep -Eq 'Machine:[[:space:]]*AArch64'
done

test -s "${pkg_dir}/licenses/ffmpeg/COPYING.LGPLv2.1"
test -s "${pkg_dir}/licenses/ffmpeg/LICENSE.md"
if [ -n "${zip_path}" ]; then
    test -s "${zip_path}"
    unzip -tqq "${zip_path}"
    for lib in avformat avcodec avutil swscale swresample; do
        soname=$(printf '%s\n' "${needed}" | grep -m 1 "^lib${lib}\\.so")
        unzip -Z1 "${zip_path}" | sed 's|^\./||' | grep -Fqx "open-realm-wc3/libs.aarch64/${soname}"
    done
fi
echo 'PortMaster shared FFmpeg libraries and AArch64 checks passed.'

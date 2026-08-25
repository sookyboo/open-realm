# Texture Pixel Formats

`R_LoadTextureMipLevel` accepts RGBA bytes (`COLOR32 { r, g, b, a }`) and is used for renderer-generated pixels. `R_LoadTextureMipLevelBGRA` accepts BGRA bytes and is used by BLP1, BLP2, PCX, and the STB fallback, whose decoders deliberately preserve legacy BGRA byte order.

Desktop OpenGL/gl4es uploads BGRA sources with `GL_BGRA`. Native GLES3 swaps B/R on the CPU and uploads `GL_RGBA`, because core GLES3 does not guarantee BGRA input. DDS remains separate: `r_dds.c` derives its GL input format from the DDS channel masks.

Pixel byte order belongs to the decoded source, not the operating system. Do not select RGBA/BGRA with `#if __linux__`.

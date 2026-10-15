# Retail evidence capture notes

Shared screenshot and evidence capture procedures. These are optional; consult only when reproducing visual artifacts.

## Capturing Retail screenshots under Wine

Use Warcraft III's own Print Screen handling for Retail evidence. In a Wine
profile it writes a TGA under:

    $WINEPREFIX/drive_c/users/<wine-user>/Documents/Warcraft III/ScreenShots/

The filename is timestamped, for example
`WC3ScrnShot_100426_210616_01.tga`. The exact capitalization of `ScreenShots`
is not significant on the Wine filesystem. Convert the newest TGA to PNG under
the repository's ignored `screenshots/tmp/` directory; the converter removes
the TGA only after validating the PNG. Do not derive Retail evidence PNGs from
XWD captures: the earlier XWD conversion produced striped pixels even though
its PNG metadata reported RGB.

For an automated headless run, follow the map-specific launch procedure in
this document, then send `Print` to the focused Warcraft window with `xdotool`.
This exact input sequence successfully captured the prepared TFT Serpent Ward
rank comparison map on October 4, 2026:

```sh
export WINEPREFIX=/home/agent/.wine-war3
MAP=/tmp/wc3-serpentward-rank-compare-v3/run/OrcX01-SerpentWard-TFT-Ranks-v3.w3x
xvfb-run -a -s '-screen 0 1280x720x24' bash -lc '
  export WINEPREFIX=/home/agent/.wine-war3
  MAP=/tmp/wc3-serpentward-rank-compare-v3/run/OrcX01-SerpentWard-TFT-Ranks-v3.w3x
  wine "data/Warcraft III/Warcraft III.exe" -window -graphicsapi OpenGL2 \
    -loadfile "$(winepath -w "$MAP")" &
  game_pid=$!
  trap "kill $game_pid 2>/dev/null || true" EXIT
  sleep 30
  xdotool mousemove 642 600 click 1
  sleep 20
  xdotool key Escape
  sleep 10
  xdotool key Print
  sleep 5
  find "$WINEPREFIX/drive_c/users/agent/Documents/Warcraft III/ScreenShots" \
    -type f -iname "*.tga" -mmin -2 -printf "%TY-%Tm-%Td %TH:%TM %s %p\\n"
'
```

The click advances the campaign chapter card, Escape skips the cinematic, and
Print asks Warcraft itself to capture the gameplay screen. Keep the key event
focused on the game window. Confirm a newly timestamped TGA appears before
converting it; a command completing without that file is not a successful
capture. If the map does not reach the expected screen or no fresh file is
written, use the existing replay troubleshooting guidance above rather than
changing the launch route by guesswork.

Convert the newest TGA with the repository tool. It validates the output PNG
as RGB with the original dimensions and deletes the TGA only after validation
succeeds. By default it searches `$WINEPREFIX` (or `~/.wine-war3`) and writes
beside the repository under `screenshots/tmp/`:

```sh
/opt/openrealm-tools/frida-venv/bin/python tools/convert_wc3_retail_screenshot.py \
  --wine-prefix /home/agent/.wine-war3 --wine-user agent
```

The output keeps the TGA's timestamped basename with a `.png` extension. If
the corresponding PNG already exists, the tool stops and leaves the TGA in
place. The verified sample TGA was RGBA at 1024×576; its converted PNG was RGB
at the same dimensions. This is a property of that capture, not a guarantee
about all Retail window sizes. The tool needs Pillow; use a Python environment
that has it installed. `screenshots/` is ignored by Git, so these local
evidence images are not committed by default. See
[`tools/README.md`](../../../../tools/README.md#convert_wc3_retail_screenshotpy)
for options and behavior.

The sample image showed the in-game JASS comparison output for the test:
rank 2 was accepted and produced unit type `1869836338` (`osp2`). The screenshot
is supplementary visual evidence; the saved JASS result and the written
ability observation remain the behavior record.

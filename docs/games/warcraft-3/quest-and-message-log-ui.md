# Warcraft III Quest And Message Log UI

## Contract

Warcraft III's Quests journal and single-player Message Log are separate
server-authored HUD dialogs.

- The quest model (`level.quests`) owns quest state. The dialog only renders
  enabled, discovered quests and their objectives.
- `DisplayText*` owns one transient `LAYER_MESSAGE` presentation slot per
  player. A separate bounded `client_s.message_log` retains the text after the
  transient message expires or `ClearTextMessages` clears it.
- Command errors use `UI_ShowTransientText` and do not enter the Message Log.
- `UpperButtonBarQuestsButton` sends the existing `quests` client command.
- `UpperButtonBarChatButton` currently sends `log`, implementing the
  single-player Log role of Warcraft's fourth system button. Multiplayer Chat
  mode selection is separate work.
- Quest and Log are modal on the client: opening either disables the four upper
  system buttons, suppresses world hover/tooltips, and prevents lower gameplay
  UI from receiving modal clicks. The earlier server-clock pause experiment was
  removed because it starved normal frame/network cadence and could time out or
  crash on modal close. A safe Warcraft-style pause remains separate work.
- Default system-button key bindings use the same configurable input path as
  Hero/idle-worker shortcuts: F9 sends `cmd quests`, F10 `cmd menu`, F11
  `cmd allies`, and F12 `cmd log`. Mouse clicks on the four authored upper
  buttons send the same server actions. `UpperButtonBar.fdf` stores these labels
  as `KEY_QUESTS`, `KEY_MENU`, `KEY_ALLIES`, and `KEY_CHAT`; load
  `GlobalStrings.fdf` before the button bar so they resolve to strings such as
  `Menu (F10)` instead of appearing as raw keys.

The dialogs are rendered through stock Warcraft FDF roots:

```text
UI\FrameDef\UI\QuestDialog.fdf
UI\FrameDef\UI\LogDialog.fdf
UI\FrameDef\UI\UpperButtonBar.fdf
```

Generated bindings under `games/warcraft-3/game/generated/` are outputs of
`fdfbindgen`; do not hand-edit them.

## Quest Data Flow

```text
CreateQuest / QuestSet* / QuestCreateItem
        -> level.quests / QUESTITEM state
        -> quests command
        -> hud/hud_quests.c
        -> svc_window Quest instance
```

`CreateQuest` initializes `enabled = true`; Blizzard's standard `CreateQuestBJ`
sets required/discovered/completed state but does not separately enable the
quest. A quest is visible only when both are true:

```c
quest->enabled && quest->discovered
```

Required and optional quests are rendered into separate authored containers.
`UI_ShowQuests` chooses the first visible required quest, then the first visible
optional quest. `UI_ShowQuest` populates the authored tree and sends one complete
window snapshot; the server does not retain client-window open or selection state.

Quest rows and objective rows are cloned lazily and then reused. This is
important because FDF frames live in a fixed `MAX_UI_CLASSES` pool; cloning a
new row tree on every quest click/refresh permanently consumes frame slots.
Unused cached rows are hidden before serialization.

The selected quest renders:

- its title in `QuestTitleValue`;
- its description in `QuestDisplay`;
- its `QuestSetIconPath` art in each visible `QuestListItemIconContainer`;
- its objectives in `QuestItemListContainer`;
- authored selected/completed/failed row highlights when those named children
  exist in the retail FDF.

Standalone FDF `HIGHLIGHT` frames are serialized with their alpha texture and
blend mode. `QuestListItemSelectedHighlight` is also rebound to the cloned
`QuestListItemButton` bounds before each write, matching the retail
`SetAllPoints` relationship. This keeps selected art the same width as the
mouse-over art instead of clipping around only part of a quest title.

If an authored selected-highlight child is absent (notably small test fixtures),
the existing `> ` / yellow-title fallback remains in use.

## Quest Update Semantics

`ForceQuestDialogUpdate` is retained as a compatibility no-op because gameplay
windows are send-once snapshots:

```text
any state -> no UI write
```

`FlashQuestDialogButton` uses Warcraft's separate quest-change particle art; it
does **not** pulse the `SIMPLEBUTTON` normal/hover texture. The active player's
skin resolves `QuestChangedParticles` (stock data points to
`UI\Feedback\QuestButton\UI-QuestButtonOn.mdl`), and the console writer emits
that model as an `FT_SPRITE` parented to `UpperButtonBarQuestsButton`. The
sprite carries the button's authored width/height, with its left edge anchored
to the Quest button's right edge. `SCR_LayoutDrawSprite` submits the sprite's
bottom-left model origin, so the parent-edge anchor contributes exactly one
button width to X while retaining the button height contributes exactly one
button height below the top edge. This uses the live FDF dimensions rather than
hard-coded UI offsets. For temporary alignment tuning, the console writer also
accepts authored-pixel offsets through `wc3_quest_sparkle_x_px` and
`wc3_quest_sparkle_y_px`; one pixel is `0.001` FDF units, negative X moves
left, and positive Y moves up. Defaults are `-4` X and `+4` Y. These values are sampled when the Quest
sparkle frame is written, so set them before the flash is triggered (or
force the console layer to be re-sent). The quest
effect opts into the generic `UIFLAG_DRAW_AFTER_PARENT` compositor path, so the
normal/pushed/hover button art is drawn first and the animated particles are
then layered on top. Other `FT_SPRITE` frames retain the legacy underlay pass.

The stock effect uses PRE2 particle emitters. During the current bounded Quest
attention diagnostic, the renderer preserves all authored Head/Tail content and
can isolate either the head/tail part (`r_mdx_ui_pre2_parts`) or one authored
emitter by one-based ordinal (`r_mdx_ui_pre2_emitter`, with 0 meaning all).
Runtime A/B testing established that head-only produces no visible Quest effect
while tail-only still contains both the desired sweep and the unwanted mirrored
copy. The remaining diagnostic therefore isolates the two authored emitters; do
not blanket-disable PRE2 tails because that also removes the visible Quest effect.

Quest attention remains active until the Quest button command is activated.
Opening Quest through that button clears the particle state and re-sends
`LAYER_CONSOLE`; repeated `FlashQuestDialogButton` calls while already active do
not invent a timer or toggle the button art. The state reuses the legacy
quest-dialog presentation byte as a bitfield and is cleared as transient runtime
state when loading a save.

The quest-change model is particle-only in the stock data. UI sprite rendering
therefore preserves the main frame's elapsed time for emitter accumulation while
using a separate particle render scope. Particle simulation itself advances once
per top-level renderer frame, so nested HUD sprite views do not age or re-draw
world particles through the UI camera. `RDF_NOWORLDMODEL`/`RDF_NOFOG` also keeps
these HUD particles independent of the world fog-of-war texture.

`ParticleScaling` in PRE2 is floating-point model data. The shared particle list
keeps a compact byte curve plus a value scale, so MDX emission quantizes the
three authored values relative to their maximum instead of casting each float
directly to `BYTE`; direct casts erase the very small values used by UI models.
The curve time is normalized across the particle lifespan. `UI-QuestButtonOn`
is positioned as a Quest-button-sized sprite whose left edge is anchored to the
button's right edge. The parent edge supplies one button width of X displacement,
and the client's normal top-down-rectangle to bottom-left model-origin conversion
contributes exactly one button height to Y. Both offsets therefore follow the
authored button dimensions rather than fixed numbers.

FDF simple-button normal/pushed/disabled states are serialized explicitly.
When Quest or Log owns the modal UI, the server temporarily clears the saved
click actions for Quest, Menu, Allies, and Log and re-sends `LAYER_CONSOLE`;
the client therefore draws their authored disabled state and cannot dispatch
those commands until the modal dialog closes. Their original commands are
restored afterward.

## Developer quest/script cheats

`docs/cheat-commands.md` documents the `sv_cheats`-gated quest and JASS trigger
debugging commands. Keep the semantic split explicit:

```text
quest complete <index|all>
    -> mutates QUEST/QUESTITEM completed flags only

trigger fire <index> [selected]
    -> executes the map trigger's registered actions directly
```

Changing `QUEST.completed` is not a campaign-progression event. Maps normally
call `QuestSetCompleted` as one action inside a larger trigger that can also
play dialogue, enable later triggers, spawn/remove units, and update other
mission state. Use direct trigger firing when testing/skipping that authored
progression; use quest completion when testing journal presentation.

## Message Log Data Flow

`DisplayTextToPlayer`, `DisplayTimedTextToPlayer`, and
`DisplayTimedTextFromPlayer` use `UI_ShowText`:

```text
resolve TRIGSTR / level string
        -> format display text
        -> store transient client_s.message
        -> append same formatted text to client_s.message_log
        -> presentation_dirty flushes LAYER_MESSAGE
```

`client_s.message_log` is a 128-entry ring. When full, the oldest entry is
replaced. This implements bounded Warcraft-style history without coupling the
history lifetime to transient HUD messages.

`ClearTextMessages` only clears `client_s.message`:

```text
transient message -> cleared
message_log       -> preserved
```

`G_ShowCommandErrorText` deliberately calls `UI_ShowTransientText`; resource,
placement, cooldown, and similar command errors therefore remain transient and
do not pollute F12-style history.

## Log Dialog

The `log` command sends the current history as a stock `LogDialog` client-managed
window. Its authored `LogOkButton` uses the generic client-only close action.

Quest/Log dialog buttons inherit `EscMenuButtonTemplate`. Their backdrop art is
race-specific data in `war3skins.txt`. FDF templates are cached globally, so a
shared Esc-menu template can be parsed before a player skin context exists. In
addition to resolving `DecorateFileNames` during FDF loading, the layout
serializer re-resolves cached symbolic image keys for the client being sent.
This keeps the Done/OK normal, pushed, and disabled backdrops intact even when
the template was first loaded by an earlier cinematic/menu path.

The ring is assembled in chronological order into `LogArea`, separated by
blank lines. New entries are included the next time the client requests the log;
the server does not track whether the client window remains open.

Quest and Log use `svc_window` with opaque WC3-local class IDs. Both are movable,
unique, modal windows. They do not consume `UILAYOUTLAYER` entries. Frame text,
tooltips, and commands reference the packet's trailing text arena, so long quest
descriptions and message history are not constrained by the one-byte typed payload.

## Modal Behavior

`QuestDialog` and `LogDialog` are centered on the UI root when their FDF is
loaded. The dialogs do not currently pause the simulation. An earlier attempt
paused by changing the server frame clock; that broke normal network/frame
cadence, could trigger disconnect timeouts during a long-open dialog, and could
crash/freeze when Done/OK resumed the server. Do not reintroduce UI pause by
mutating `SV_Frame` scheduling.

On the client, an active Quest/Log window consumes gameplay hit testing across
the world. Mouse and layout-key dispatch are restricted to the topmost modal window, lower
HUD tooltips are suppressed, and `LAYER_WORLD_HOVER` is not rendered until the
dialog closes. Normal gameplay key bindings are also suppressed on key-down
while a modal root is active; this includes Hero/control-group/system-button
bindings, while key-up still releases any previously held `+command`. Manual
camera input is modal too: arrow-key scrolling, screen-edge scrolling,
middle-button drag panning, and minimap drag/recenter are ignored while the
dialog is open. This prevents transparent portions of a centered dialog from
selecting units, activating command UI, or moving the gameplay camera underneath it.

Done/OK uses a client-only close action. The linked-list manager releases its
retained frame/text packet and transfers focus to the new top window; no server
command or close packet is required.

The client modal window consumes input before the underlying HUD, so the four
upper system buttons cannot be activated while a Quest/Log window is open. The
server does not clear and resend their commands based on stale window state.

## Quest Text Diagnostics

Quest text diagnostics are compiled in and off by default. Run with:

```text
+set wc3_quest_debug 1
```

Opening or selecting a quest emits stable `WC3_QUEST_TEXT` lines containing the
quest index, field name, raw map/JASS value, and resolved display value. Fields
include `title`, `description`, `subtitle`, required/optional/details headings,
Done-button text, list titles, and each objective. A `WC3_QUEST_STATE` line also
prints required/discovered/enabled/completed/failed flags plus raw/resolved icon
path, whether the authored icon frame was found, and its resulting image index.
Newlines/tabs/quotes are escaped so a bad string can be copied from the log
without ambiguity. Leave the cvar at `0` for normal play.

## Function-Key And Upper-Button Routing

`games/warcraft-3/share/config.cfg` owns the default F-key bindings so users can
override them through the existing key system rather than a WC3-specific hard
coded dispatcher:

```text
F9  -> cmd quests
F10 -> cmd menu
F11 -> cmd allies
F12 -> cmd log
```

`hud_console.c` assigns the same four command names to the authored upper
system buttons. F10 therefore no longer defaults to the engine screenshot
command: the retail `(F10)` Menu label and the default key action now agree.
The `menu` and `allies` command routes are present for mouse/key parity. The
Menu route opens the separate modal Esc-menu window documented in
[in-game-menu.md](in-game-menu.md); Allies rendering is implemented separately.

## Known Gaps

- The fourth upper button is wired to the single-player `log` command. Runtime
  selection between single-player Log and multiplayer Chat is not yet modeled.
- Server-authored `FT_TEXTAREA` windows now keep a client-local scroll fraction
  across layout reparses. Mouse wheel input over the text area or its scrollbar,
  arrow clicks, track clicks, and thumb dragging all update the same viewport
  state. `LogAreaScrollBar` is attached to the text area's authored right edge
  and is hidden automatically when the wrapped history fits without scrolling.
- Message history is bounded by 128 logical entries. Retail's FDF expresses a
  128-line text-area limit; wrapped-line-equivalent eviction is not yet modeled.
- `FlashQuestDialogButton` renders the skin-authored `QuestChangedParticles`
  sprite one Quest-button cell to the right, sized to the button so the model
  origin resolves one button height down at its bottom-left, after the button
  art is drawn
  and clears it when that button is activated; the button's own
  normal/pushed/disabled/hover presentation is not flashed.
- `PauseGame` JASS remains a separate unimplemented native. Quest/Log currently
  do not pause the simulation; pause must be implemented without disturbing the
  server/network frame cadence.
- Save-game serialization is not yet available for quest/dialog/log state.

## Verification

Relevant tests live under `games/warcraft-3/game/tests/`:

- `wc3_game.hud_quest_visibility_requires_enabled_and_discovered`
- `wc3_game.hud_quest_rows_bind_authored_children`
- `wc3_api.display_text_tracks_lifetime_and_clear`
- `wc3_api.transient_command_style_text_does_not_enter_message_log`
- `wc3_api.message_log_is_bounded_and_evicts_oldest_entry`
- `net.layout_textarea_clips_to_inset_viewport`
- `net.layout_textarea_value_scrolls_wrapped_content_inside_clip`

When validating this work, run the normal WC3 test target and then verify a
campaign map manually:

```sh
make test-wc3-engine
```

Manual checks:

1. Click **Quests** with discovered/enabled required and optional quests; hidden
   or disabled quests must not appear.
2. Close Quest with **Done**, reopen it with Quests/F9, and confirm it is rebuilt
   from the current authoritative quest data.
3. Click another quest repeatedly and confirm rows do not duplicate.
4. Confirm the description and objective list follow the selected quest.
5. Display timed game text, clear/expire the transient message, click the fourth
   upper button, and confirm the historical text remains in Message Log.
6. Trigger a command error and confirm it is not added to Message Log.
7. Open Quest and Log and confirm simulation/timers continue, manual camera
   movement is blocked, upper system buttons are consumed by the modal client
   window, lower HUD/world hover does not react, and Done/OK closes locally.
8. Confirm F9 and F12 open the same Quest/Log routes as the corresponding mouse
   buttons; F10/F11 should reach the current Menu/Allies command stubs without
   falling back to screenshot or an unknown command.
9. Confirm visible quest rows use `QuestSetIconPath` art. If any quest wording is
   wrong, rerun with `+set wc3_quest_debug 1` and capture the corresponding
   `WC3_QUEST_TEXT` / `WC3_QUEST_STATE` lines.

## See Also

- [Triggered Dialogue](triggered-dialogue.md)
- [Warcraft III UI System](architecture/ui.md)
- [Server-Authored UI Payloads](../../architecture/ui-payloads.md)
- [FDF Reference](file-docs/fdf.md)


## FDF button wire payloads

Quest rows, the upper system buttons, and dialog OK buttons are authored FDF
controls. When the game module serializes those controls through `svc_layout`,
`SIMPLEBUTTON` frames carry `uiSimpleButton_t` state and the normal FDF button
families (`BUTTON`, `TEXTBUTTON`, `GLUEBUTTON`, and related popup controls)
carry `uiGlueTextButton_t` state. The client renderer rejects a short or missing
button payload rather than dereferencing it. This preserves Blizzard's
normal/pushed/disabled artwork and prevents malformed control frames from
crashing the client.

Diagnostic note: raw PRE2 pivots cannot be applied directly to UI trail origins; compare working zero-origin and pivot-transformed positions before converting model coordinates to FDF space.

/* hud_menu.c — Server-authored in-game pause menu using Blizzard's Esc FDF. */

#include "hud_local.h"
#include <time.h>

typedef enum {
    MENU_PANEL_MAIN,
    MENU_PANEL_END_GAME,
    MENU_PANEL_CONFIRM_QUIT,
} menuPanel_t;

typedef enum {
    MENU_SAVE_PANEL_SAVE,
    MENU_SAVE_PANEL_LOAD,
} menuSavePanel_t;

/* The Save/Load controls are cloned into ChatDialog after its authored
 * backdrop/history tree has loaded. Keeping the active controls as late
 * clones makes their wire/draw order unambiguously frontmost; simply changing
 * Parent on the Esc-menu instances left them behind the chat backdrop. The
 * clone bindings live in hud_t so UI_ResetHud() clears them with the FDF arena. */

static int MenuSaveDebugLevel(void) {
    LPCSTR value = gi.CvarString ? gi.CvarString("wc3_save_menu_debug", "0") : "0";
    return value ? atoi(value) : 0;
}

static LPFRAMEDEF MenuPanel(menuPanel_t panel) {
    switch (panel) {
        case MENU_PANEL_END_GAME: return hud.menu.EndGamePanel;
        case MENU_PANEL_CONFIRM_QUIT: return hud.menu.ConfirmQuitPanel;
        case MENU_PANEL_MAIN:
        default: return hud.menu.MainPanel;
    }
}

static LPFRAMEDEF MenuSaveListBox(void) {
    LPFRAMEDEF list = hud.save_dialog.ChatHistoryDisplay;

    if (!list) return NULL;

    /* Reuse the in-game Chat dialog's authored history viewport and scrollbar.
     * CHATDISPLAY is a scrolling text control, but named saves need row
     * selection as well as scrolling. The transient window bridge already has
     * selectable LISTBOX semantics, so promote only this process-local FDF copy
     * while preserving ChatHistoryScrollBar as its child control. */
    if (list->Type == FT_CHATDISPLAY || list->Type == FT_TEXTAREA ||
        list->Type == FT_CONTROL) {
        FLOAT line_height = list->TextArea.LineHeight;
        FLOAT inset = list->TextArea.Inset;
        list->Type = FT_LISTBOX;
        if (inset > 0.0f) list->ListBox.Border = inset;
        if (!list->Font.Index && hud.save_dialog.ChatInfoText)
            list->Font = hud.save_dialog.ChatInfoText->Font;
        if (list->Font.Size <= 0.0f && line_height > 0.0f)
            list->Font.Size = line_height;
        if (list->Font.Size <= 0.0f && hud.save_dialog.ChatHistoryLabel)
            list->Font.Size = hud.save_dialog.ChatHistoryLabel->Font.Size;
    }
    return list->Type == FT_LISTBOX ? list : NULL;
}

static void MenuDefaultSaveName(LPSTR out, DWORD out_size) {
    time_t now;
    struct tm const *local;

    if (!out || out_size == 0) return;
    out[0] = '\0';
    now = time(NULL);
    local = localtime(&now);
    if (local && strftime(out, out_size, "%Y-%m-%d_%H-%M-%S", local) > 0)
        return;
    snprintf(out, out_size, "Save Game");
}

static void MenuResetPoints(LPFRAMEDEF frame) {
    if (!frame) return;
    memset(&frame->Points, 0, sizeof(frame->Points));
    frame->AnyPointsSet = false;
}

static LPFRAMEDEF MenuCloneSaveControl(LPCFRAMEDEF source, LPFRAMEDEF root) {
    LPFRAMEDEF copy;

    if (!source || !root) return NULL;
    copy = UI_CloneFrameTree(source, root);
    if (copy) UI_SetHidden(copy, false);
    return copy;
}

static BOOL MenuSaveControlsCurrent(LPCFRAMEDEF root) {
    return root &&
           hud.save_edit && hud.save_edit->inuse && hud.save_edit->Parent == root &&
           hud.save_edit_text && hud.save_edit_text->inuse &&
           hud.save_edit_text->Parent == hud.save_edit &&
           hud.save_button && hud.save_button->inuse && hud.save_button->Parent == root &&
           hud.save_cancel_button && hud.save_cancel_button->inuse &&
           hud.save_cancel_button->Parent == root &&
           hud.load_button && hud.load_button->inuse && hud.load_button->Parent == root &&
           hud.load_cancel_button && hud.load_cancel_button->inuse &&
           hud.load_cancel_button->Parent == root;
}

static void MenuDiscardSaveControls(void) {
    hud.save_edit = NULL;
    hud.save_edit_text = NULL;
    hud.save_button = NULL;
    hud.save_cancel_button = NULL;
    hud.load_button = NULL;
    hud.load_cancel_button = NULL;
}

static void MenuPrepareSaveDialogLayout(void) {
    LPFRAMEDEF root = hud.save_dialog.ChatDialog;
    LPFRAMEDEF list = MenuSaveListBox();
    LPFRAMEDEF history = hud.save_dialog.ChatHistoryDisplayBackdrop;

    if (!root || !list || !history || !hud.save_menu.SaveGameFileEditBox ||
        !hud.save_menu.SaveGameSaveButton || !hud.save_menu.SaveGameCancelButton ||
        !hud.save_menu.LoadGameLoadButton || !hud.save_menu.LoadGameCancelButton)
        return;

    /* The Chat dialog supplies the Warcraft window chrome and scrollbar.  The
     * cinematic/mission chooser is the layout model for the content: one
     * bounded list viewport with deterministic top-down rows and controls
     * anchored inside the same panel. */
    UI_SetHidden(hud.save_dialog.ChatPlayerRadioButton, true);
    UI_SetHidden(hud.save_dialog.ChatAlliesRadioButton, true);
    UI_SetHidden(hud.save_dialog.ChatObserversRadioButton, true);
    UI_SetHidden(hud.save_dialog.ChatEveryoneRadioButton, true);
    UI_SetHidden(hud.save_dialog.ChatPlayerLabel, true);
    UI_SetHidden(hud.save_dialog.ChatAlliesLabel, true);
    UI_SetHidden(hud.save_dialog.ChatObserversLabel, true);
    UI_SetHidden(hud.save_dialog.ChatEveryoneLabel, true);
    UI_SetHidden(hud.save_dialog.ChatPlayerMenu, true);
    UI_SetHidden(hud.save_dialog.ChatAcceptButton, true);
    UI_SetHidden(hud.save_dialog.ChatInfoText, true);
    UI_SetHidden(hud.save_dialog.ChatHistoryScrollBar, false);
    UI_SetText(hud.save_dialog.ChatHistoryLabel, "Saved Games");

    /* Give the dialog a stable chooser-sized viewport instead of inheriting
     * the chat history's conversation-oriented placement. */
    UI_SetSize(root, 0.420f, 0.320f);
    MenuResetPoints(hud.save_dialog.ChatBackdrop);
    UI_SetPoint(hud.save_dialog.ChatBackdrop, FRAMEPOINT_TOPLEFT,
                root, FRAMEPOINT_TOPLEFT, 0.0f, 0.0f);
    UI_SetPoint(hud.save_dialog.ChatBackdrop, FRAMEPOINT_BOTTOMRIGHT,
                root, FRAMEPOINT_BOTTOMRIGHT, 0.0f, 0.0f);

    MenuResetPoints(history);
    UI_SetPoint(history, FRAMEPOINT_TOPLEFT, root, FRAMEPOINT_TOPLEFT,
                0.032f, -0.060f);
    UI_SetPoint(history, FRAMEPOINT_BOTTOMRIGHT, root, FRAMEPOINT_BOTTOMRIGHT,
                -0.032f, 0.105f);
    MenuResetPoints(hud.save_dialog.ChatHistoryLabel);
    UI_SetPoint(hud.save_dialog.ChatHistoryLabel, FRAMEPOINT_BOTTOMLEFT,
                history, FRAMEPOINT_TOPLEFT, 0.0f, 0.006f);

    /* LoadGame/map changes rebuild the global FDF frame arena. Cached clone
     * pointers from an older arena can remain non-NULL if they are stored
     * outside hud_t, yet no longer belong to this ChatDialog. Treat the clone
     * set atomically: if any binding is stale or incomplete, rebuild all six. */
    if (!MenuSaveControlsCurrent(root)) {
        if (MenuSaveDebugLevel() >= 1 &&
            (hud.save_edit || hud.save_button || hud.load_button)) {
            fprintf(stderr,
                    "WC3_SAVE_MENU clone-refresh root=%s editCurrent=%d "
                    "saveCurrent=%d loadCurrent=%d\n",
                    root->Name,
                    hud.save_edit && hud.save_edit->inuse && hud.save_edit->Parent == root,
                    hud.save_button && hud.save_button->inuse && hud.save_button->Parent == root,
                    hud.load_button && hud.load_button->inuse && hud.load_button->Parent == root);
        }
        MenuDiscardSaveControls();
    }

    if (!hud.save_edit) {
        hud.save_edit = MenuCloneSaveControl(hud.save_menu.SaveGameFileEditBox, root);
        if (hud.save_edit) {
            hud.save_edit_text = UI_FindChildFrame(hud.save_edit, "SaveGameFileEditBoxText");
            if (MenuSaveDebugLevel() >= 1) {
                fprintf(stderr,
                        "WC3_SAVE_MENU edit-clone root=%s rootHidden=%d rootVisible=%d "
                        "textFound=%d textHidden=%d textVisible=%d textType=%d "
                        "textFont=%u textFontSize=%.4f text=\"%s\"\n",
                        hud.save_edit->Name, hud.save_edit->hidden,
                        !!(hud.save_edit->ui_flags & UIFLAG_VISIBLE),
                        hud.save_edit_text != NULL,
                        hud.save_edit_text ? hud.save_edit_text->hidden : -1,
                        hud.save_edit_text ? !!(hud.save_edit_text->ui_flags & UIFLAG_VISIBLE) : 0,
                        hud.save_edit_text ? hud.save_edit_text->Type : -1,
                        hud.save_edit_text ? hud.save_edit_text->Font.Index : 0,
                        hud.save_edit_text ? hud.save_edit_text->Font.Size : 0.0f,
                        hud.save_edit_text ? hud.save_edit_text->Text : "");
            }
            /* The Esc-menu template can leave its child STRING hidden because
             * the retail edit-box controller owns that child's visibility.
             * Transient gameplay windows serialize only non-hidden children, so
             * force the cloned text child visible along with the edit control. */
            UI_SetHidden(hud.save_edit_text, false);
            if (MenuSaveDebugLevel() >= 1 && hud.save_edit_text) {
                fprintf(stderr,
                        "WC3_SAVE_MENU edit-clone-visible text=%s hidden=%d visible=%d\n",
                        hud.save_edit_text->Name, hud.save_edit_text->hidden,
                        !!(hud.save_edit_text->ui_flags & UIFLAG_VISIBLE));
            }
        }
    }
    if (!hud.save_button)
        hud.save_button = MenuCloneSaveControl(hud.save_menu.SaveGameSaveButton, root);
    if (!hud.save_cancel_button)
        hud.save_cancel_button = MenuCloneSaveControl(hud.save_menu.SaveGameCancelButton, root);
    if (!hud.load_button)
        hud.load_button = MenuCloneSaveControl(hud.save_menu.LoadGameLoadButton, root);
    if (!hud.load_cancel_button)
        hud.load_cancel_button = MenuCloneSaveControl(hud.save_menu.LoadGameCancelButton, root);

    if (!hud.save_edit || !hud.save_edit_text || !hud.save_button ||
        !hud.save_cancel_button || !hud.load_button || !hud.load_cancel_button)
        return;

    /* The original Esc-menu controls keep their original frame-array order.
     * Do not transplant them into ChatDialog: cloned controls were spawned
     * after the dialog tree, so they serialize/draw above the window chrome. */
    UI_SetHidden(hud.save_menu.SaveGameFileEditBox, true);
    UI_SetHidden(hud.save_menu.SaveGameSaveButton, true);
    UI_SetHidden(hud.save_menu.SaveGameCancelButton, true);
    UI_SetHidden(hud.save_menu.LoadGameLoadButton, true);
    UI_SetHidden(hud.save_menu.LoadGameCancelButton, true);

    MenuResetPoints(hud.save_edit);
    UI_SetPoint(hud.save_edit, FRAMEPOINT_TOPLEFT,
                history, FRAMEPOINT_BOTTOMLEFT, 0.0f, -0.012f);
    UI_SetPoint(hud.save_edit, FRAMEPOINT_TOPRIGHT,
                history, FRAMEPOINT_BOTTOMRIGHT, 0.0f, -0.012f);

    MenuResetPoints(hud.save_button);
    UI_SetPoint(hud.save_button, FRAMEPOINT_BOTTOMRIGHT,
                root, FRAMEPOINT_BOTTOMRIGHT, -0.025f, 0.022f);
    MenuResetPoints(hud.save_cancel_button);
    UI_SetPoint(hud.save_cancel_button, FRAMEPOINT_BOTTOMRIGHT,
                hud.save_button, FRAMEPOINT_BOTTOMLEFT, -0.010f, 0.0f);

    MenuResetPoints(hud.load_button);
    UI_SetPoint(hud.load_button, FRAMEPOINT_BOTTOMRIGHT,
                root, FRAMEPOINT_BOTTOMRIGHT, -0.025f, 0.022f);
    MenuResetPoints(hud.load_cancel_button);
    UI_SetPoint(hud.load_cancel_button, FRAMEPOINT_BOTTOMRIGHT,
                hud.load_button, FRAMEPOINT_BOTTOMLEFT, -0.010f, 0.0f);
}

static BOOL MenuSavePanelReady(void) {
    return hud.save_dialog.ChatDialog &&
           hud.save_dialog.ChatBackdrop &&
           hud.save_dialog.ChatTitle &&
           hud.save_dialog.ChatHistoryDisplayBackdrop &&
           hud.save_dialog.ChatHistoryDisplay &&
           hud.save_dialog.ChatHistoryScrollBar &&
           hud.save_dialog.ChatHistoryLabel &&
           hud.save_edit && hud.save_edit_text &&
           hud.save_button && hud.save_cancel_button &&
           hud.load_button && hud.load_cancel_button;
}

#define MENU_SAVE_LIST_TEXT 2048
#define MENU_SAVE_ENUM_TEXT 4096

static BOOL MenuSaveNameSafe(LPCSTR name) {
    DWORD len;

    if (!name || !*name) return false;
    len = (DWORD)strlen(name);
    if (len >= CMDARG_LEN || !strcmp(name, ".") || !strcmp(name, "..") ||
        name[len - 1] == '.') return false;
    for (DWORD i = 0; name[i]; i++) {
        unsigned char ch = (unsigned char)name[i];
        if (ch < 0x20 || strchr("\\/:*?\"<>|\t\r\n", ch)) return false;
    }
    return true;
}

static BOOL MenuAppendSaveRow(LPSTR out, DWORD out_size, LPDWORD used,
                              LPCSTR display, LPCSTR value) {
    int written;

    if (!out || !out_size || !used || !display || !value || *used >= out_size)
        return false;
    written = snprintf(out + *used, out_size - *used, "%s%s\t%s",
                       *used ? "\n" : "", display, value);
    if (written < 0 || (DWORD)written >= out_size - *used) return false;
    *used += (DWORD)written;
    return true;
}

/* Build the authored LISTBOX payload as `display\thidden-value` rows. The
 * hidden basename is submitted by the transient-window placeholder expander.
 * Only saves whose headers still resolve to a map are exposed to Load. */
static DWORD MenuBuildSaveList(void) {
    char names[MENU_SAVE_ENUM_TEXT] = { 0 };
    char rows[MENU_SAVE_LIST_TEXT] = { 0 };
    DWORD count = 0, used = 0;
    LPFRAMEDEF list = MenuSaveListBox();

    if (!MenuSavePanelReady() || !list || !gi.ListSaves || !gi.SavePath) {
        if (MenuSaveDebugLevel())
            fprintf(stderr,
                    "WC3_SAVE_MENU build-list unavailable panel=%d list=%d listSaves=%d savePath=%d\n",
                    MenuSavePanelReady(), list != NULL,
                    gi.ListSaves != NULL, gi.SavePath != NULL);
        return 0;
    }
    gi.ListSaves(names, sizeof(names));
    if (MenuSaveDebugLevel())
        fprintf(stderr, "WC3_SAVE_MENU enumerate begin list=%s\n", list->Name);
    for (LPCSTR name = names; *name; name += strlen(name) + 1) {
        PATHSTR path = { 0 };
        PATHSTR map = { 0 };
        LPCSTR display;

        if (!MenuSaveNameSafe(name)) {
            if (MenuSaveDebugLevel())
                fprintf(stderr, "WC3_SAVE_MENU enumerate skip name=\"%s\" reason=unsafe\n", name);
            continue;
        }
        gi.SavePath(name, path, sizeof(path));
        if (!path[0]) {
            if (MenuSaveDebugLevel())
                fprintf(stderr, "WC3_SAVE_MENU enumerate skip name=\"%s\" reason=no-path\n", name);
            continue;
        }
        if (!G_GetSaveMap(path, map, sizeof(map))) {
            if (MenuSaveDebugLevel())
                fprintf(stderr,
                        "WC3_SAVE_MENU enumerate skip name=\"%s\" path=\"%s\" reason=unreadable-header\n",
                        name, path);
            continue;
        }
        display = !strcasecmp(name, "quick") ? "Quick Save" : name;
        if (!MenuAppendSaveRow(rows, sizeof(rows), &used, display, name)) {
            if (MenuSaveDebugLevel())
                fprintf(stderr, "WC3_SAVE_MENU enumerate stop reason=row-buffer-full count=%u\n",
                        (unsigned)count);
            break;
        }
        if (MenuSaveDebugLevel())
            fprintf(stderr,
                    "WC3_SAVE_MENU enumerate add index=%u display=\"%s\" value=\"%s\" map=\"%s\"\n",
                    (unsigned)count, display, name, map);
        count++;
    }
    UI_SetText(list, "%s", rows);
    if (MenuSaveDebugLevel())
        fprintf(stderr,
                "WC3_SAVE_MENU enumerate done count=%u bytes=%u list=%s size=%.4fx%.4f "
                "font=%u fontSize=%.4f text=\"%s\"\n",
                (unsigned)count, (unsigned)used, list->Name, list->Width, list->Height,
                (unsigned)list->Font.Index, list->Font.Size, rows);
    return count;
}

static void MenuSetButton(LPFRAMEDEF button, BOOL enabled, LPCSTR command) {
    if (!button) return;
    UI_SetEnabled(button, enabled);
    if (enabled && command) UI_SetOnClick(button, "%s", command);
    else UI_SetOnClick(button, "");
}

/* Main-menu availability is intentionally independent of the authored list
 * control and save-header parser. A save directory entry is enough to offer
 * the Load panel; that panel performs the stricter readable-save filtering
 * before enabling its Load action. */
static BOOL MenuAnySaveExists(void) {
    char names[MENU_SAVE_ENUM_TEXT] = { 0 };

    if (!gi.ListSaves) return false;
    gi.ListSaves(names, sizeof(names));
    for (LPCSTR name = names; *name; name += strlen(name) + 1) {
        if (MenuSaveNameSafe(name)) return true;
    }
    return false;
}

static void MenuConfigureMainSaveLoad(void) {
    BOOL available = MenuSavePanelReady() && G_IsSinglePlayer();

    MenuSetButton(hud.menu.SaveGameButton, available, "menu_save_game");
    {
        BOOL any_save = MenuAnySaveExists();
        MenuSetButton(hud.menu.LoadGameButton,
                      available && any_save,
                      "menu_load_game");
        if (MenuSaveDebugLevel())
            fprintf(stderr,
                    "WC3_SAVE_MENU main-buttons available=%d anySave=%d saveEnabled=%d loadEnabled=%d\n",
                    available, any_save, available, available && any_save);
    }
}

void UI_LoadHudMenu(void) {
    if (hud.menu.EscMenuBackdrop) return;
    if (!EscMenuMainPanelGame_Load(&hud.menu)) return;
    if (!hud.menu.EscMenuBackdrop) {
        fprintf(stderr, "WC3 menu: missing EscMenuBackdrop\n");
        return;
    }

    /* Save/load is optional at bind time so reduced test/UI data can still use
     * the rest of the pause menu. Retail Warcraft data provides this panel. */
    EscMenuSaveGamePanel_Load(&hud.save_menu);
    ChatDialog_Load(&hud.save_dialog);
    MenuPrepareSaveDialogLayout();

    UI_SetParent(hud.menu.EscMenuBackdrop, hud.menu.EscMenuMainPanel);
    /* The separate backdrop root loads after the panels. Nest all Esc-menu
     * panel subtrees below it so decoration serializes/draws before controls;
     * explicit anchors still target the bounded controller. */
    UI_SetParent(hud.menu.MainPanel, hud.menu.EscMenuBackdrop);
    UI_SetParent(hud.menu.EndGamePanel, hud.menu.EscMenuBackdrop);
    UI_SetParent(hud.menu.ConfirmQuitPanel, hud.menu.EscMenuBackdrop);
    UI_SetParent(hud.menu.HelpPanel, hud.menu.EscMenuBackdrop);
    UI_SetParent(hud.menu.TipsPanel, hud.menu.EscMenuBackdrop);

    /* Warsmash leaves these authored controls present but disabled. OpenRealm
     * wires the retail Save/Load panel to the existing serializer while keeping
     * unsupported Delete/overwrite-confirm behavior disabled for now. */
    MenuConfigureMainSaveLoad();
    UI_SetEnabled(hud.menu.OptionsButton, false);
    UI_SetEnabled(hud.menu.HelpButton, false);
    UI_SetEnabled(hud.menu.TipsButton, false);
    UI_SetEnabled(hud.menu.RestartButton, false);

    UI_SetText(hud.menu.PauseButtonText, "Resume Game");
    UI_SetText(hud.menu.ReturnButtonText, "Return to Game");
    UI_SetOnClick(hud.menu.PauseButton, UI_WINDOW_CLOSE_NOTIFY_ACTION);
    UI_SetOnClick(hud.menu.ReturnButton, UI_WINDOW_CLOSE_NOTIFY_ACTION);
    UI_SetOnClick(hud.menu.EndGameButton, "menu_endgame");
    UI_SetOnClick(hud.menu.PreviousButton, "menu");
    UI_SetOnClick(hud.menu.QuitButton, UI_WINDOW_DISCONNECT_ACTION);
    UI_SetOnClick(hud.menu.ExitButton, "menu_confirm_exit");
    UI_SetOnClick(hud.menu.ConfirmQuitCancelButton, "menu_endgame");
    UI_SetOnClick(hud.menu.ConfirmQuitQuitButton, UI_WINDOW_QUIT_ACTION);

    if (MenuSavePanelReady()) {
        hud.save_edit->Edit.MaxChars = CMDARG_LEN - 1;
        UI_SetText(hud.save_edit_text, "");

        MenuSetButton(hud.save_button, true,
                      UI_WINDOW_CLOSE_COMMAND_PREFIX
                      "menu_save_named \"{SaveGameFileEditBox}\"");
        MenuSetButton(hud.save_menu.SaveGameDeleteButton, false, NULL);
        MenuSetButton(hud.save_cancel_button, true, "menu");
        MenuSetButton(hud.load_cancel_button, true, "menu");
    }
}

static void MenuSelectPanel(menuPanel_t panel) {
    LPFRAMEDEF active = MenuPanel(panel);

    MenuConfigureMainSaveLoad();
    UI_SetHidden(hud.menu.EscMenuMainPanel, false);
    UI_SetHidden(hud.menu.EscMenuBackdrop, false);
    UI_SetHidden(hud.menu.MainPanel, panel != MENU_PANEL_MAIN);
    UI_SetHidden(hud.menu.EndGamePanel, panel != MENU_PANEL_END_GAME);
    UI_SetHidden(hud.menu.ConfirmQuitPanel, panel != MENU_PANEL_CONFIRM_QUIT);
    UI_SetHidden(hud.menu.HelpPanel, true);
    UI_SetHidden(hud.menu.TipsPanel, true);

    /* Warsmash sizes both the wrapper and backdrop from the active authored
     * panel. Keep the latest OpenRealm centering policy while updating those
     * dimensions for EndGame/ConfirmQuit instead of retaining MainPanel size. */
    if (active && active->Width > 0.0f && active->Height > 0.0f) {
        UI_SetSize(hud.menu.EscMenuMainPanel, active->Width, active->Height);
        UI_SetSize(hud.menu.EscMenuBackdrop, active->Width, active->Height);
    }
    UI_CenterFrame(hud.menu.EscMenuMainPanel);
    UI_CenterFrame(hud.menu.EscMenuBackdrop);
}

static void MenuWrite(LPEDICT ent, menuPanel_t panel) {
    if (!ent || !ent->client || !ent->client->connected) return;
    /* Decorated Esc-menu art is resolved while the FDF is first loaded, so
     * establish the recipient's race skin before entering the template cache. */
    UI_SetCurrentClient(ent->client);
    if (!hud.menu.EscMenuBackdrop) {
        UI_SetCurrentClient(NULL);
        return;
    }
    MenuSelectPanel(panel);
    UI_WriteWindow(ent, hud.menu.EscMenuMainPanel, &MAKE(uiWindowDef_t,
        .id = BZ_WC3_WINDOW_MENU, .class_id = BZ_WC3_WINDOW_MENU,
        .flags = UI_WINDOW_MODAL | UI_WINDOW_UNIQUE));
    UI_SetCurrentClient(NULL);
}

static void MenuSelectSavePanel(menuSavePanel_t panel) {
    BOOL saving = panel == MENU_SAVE_PANEL_SAVE;
    LPFRAMEDEF list = MenuSaveListBox();
    DWORD saves = MenuBuildSaveList();
    BOOL can_load = G_IsSinglePlayer() && list && saves > 0;
    LPFRAMEDEF root = hud.save_dialog.ChatDialog;
    char load_command[128] = { 0 };
    char default_name[CMDARG_LEN] = { 0 };

    UI_SetHidden(root, false);
    UI_SetText(hud.save_dialog.ChatTitle, saving ? "Save Game" : "Load Game");
    UI_SetText(hud.save_dialog.ChatHistoryLabel, "Saved Games");

    UI_SetHidden(hud.save_edit, !saving);
    UI_SetHidden(hud.save_button, !saving);
    UI_SetHidden(hud.save_cancel_button, !saving);
    UI_SetHidden(hud.load_button, saving);
    UI_SetHidden(hud.load_cancel_button, saving);

    if (saving) {
        MenuDefaultSaveName(default_name, sizeof(default_name));
        UI_SetText(hud.save_edit_text, "%s", default_name);
    }

    if (can_load) {
        snprintf(load_command, sizeof(load_command),
                 UI_WINDOW_CLOSE_COMMAND_PREFIX
                 "menu_load_named \"{%s}\"",
                 list->Name);
    }
    MenuSetButton(hud.load_button,
                  !saving && can_load,
                  can_load ? load_command : NULL);

    if (MenuSaveDebugLevel())
        fprintf(stderr,
                "WC3_SAVE_MENU chat-panel mode=%s default=\"%s\" saves=%u "
                "list=%s listType=%d listSize=%.4fx%.4f loadEnabled=%d command=\"%s\"\n",
                saving ? "save" : "load", saving ? default_name : "",
                (unsigned)saves, list ? list->Name : "<missing>",
                list ? (int)list->Type : -1,
                list ? list->Width : 0.0f, list ? list->Height : 0.0f,
                !saving && can_load, can_load ? load_command : "");

    UI_CenterFrame(root);
}

static void MenuWriteSavePanel(LPEDICT ent, menuSavePanel_t panel) {
    if (!ent || !ent->client || !ent->client->connected ||
        !G_IsSinglePlayer() || !MenuSavePanelReady()) return;

    UI_SetCurrentClient(ent->client);
    MenuSelectSavePanel(panel);
    /* Reuse the same unique menu identity as MainPanel. Replacing the window
     * preserves modal ownership while Main <-> Save/Load transitions occur. */
    UI_WriteWindow(ent, hud.save_dialog.ChatDialog, &MAKE(uiWindowDef_t,
        .id = BZ_WC3_WINDOW_MENU, .class_id = BZ_WC3_WINDOW_MENU,
        .flags = UI_WINDOW_MODAL | UI_WINDOW_UNIQUE));
    UI_SetCurrentClient(NULL);
}

void UI_ShowMainMenu(LPEDICT ent) {
    MenuWrite(ent, MENU_PANEL_MAIN);
}

void UI_ShowGameMenuEndGame(LPEDICT ent) {
    MenuWrite(ent, MENU_PANEL_END_GAME);
}

void UI_ShowGameMenuConfirmExit(LPEDICT ent) {
    MenuWrite(ent, MENU_PANEL_CONFIRM_QUIT);
}

void UI_ShowGameMenuSave(LPEDICT ent) {
    MenuWriteSavePanel(ent, MENU_SAVE_PANEL_SAVE);
}

void UI_ShowGameMenuLoad(LPEDICT ent) {
    MenuWriteSavePanel(ent, MENU_SAVE_PANEL_LOAD);
}

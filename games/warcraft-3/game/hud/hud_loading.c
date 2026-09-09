/* Serializes the stock Loading.fdf tree before gameplay UI exists. */
#include "hud_local.h"

void UI_LoadHudLoading(void) {
    if (!LoadingScreen_Load(&hud.loading)) {
        fprintf(stderr, "UI_LoadHudLoading: missing Loading.fdf\n");
        return;
    }
    if (hud.loading.LoadingCustomPanel) UI_SetHidden(hud.loading.LoadingCustomPanel, false);
    if (hud.loading.LoadingMeleePanel) UI_SetHidden(hud.loading.LoadingMeleePanel, true);
    if (hud.loading.LoadingBar) {
        /* Loading art is registered in the shared model table; portrait frames use the separate portrait table. */
        hud.loading.LoadingBar->Portrait.model = UI_LoadModel("LoadingProgressBar", true);
        hud.loading.LoadingBar->Type = FT_LOADING_BAR;
    }
}

void UI_WriteLoadingLayout(LPEDICT ent) {
    LPCMAPINFO info = level.mapinfo;
    LPCSTR title = info && info->loadingScreenTitle && *info->loadingScreenTitle ? info->loadingScreenTitle :
                   info ? info->mapName : NULL;
    LPCSTR background = info && info->loadingScreenModel && *info->loadingScreenModel ? info->loadingScreenModel :
                        "LoadingMeleeBackground";

    if (!ent || !hud.loading.Loading) return;
    if (hud.loading.LoadingTitleText)
        UI_SetText(hud.loading.LoadingTitleText, "%s", UI_LevelStringSafe(title));
    if (hud.loading.LoadingSubtitleText)
        UI_SetText(hud.loading.LoadingSubtitleText, "%s", UI_LevelStringSafe(info ? info->loadingScreenSubtitle : NULL));
    if (hud.loading.LoadingText)
        UI_SetText(hud.loading.LoadingText, "%s", UI_LevelStringSafe(info ? info->loadingScreenText : NULL));
    if (hud.loading.LoadingBackground)
        /* Keep LoadingBackground as FT_SPRITE so its model index resolves via cl.models. */
        hud.loading.LoadingBackground->Portrait.model = gi.ModelIndex(background);
    UI_WriteLayout(ent, hud.loading.Loading, LAYER_LOADING);
}

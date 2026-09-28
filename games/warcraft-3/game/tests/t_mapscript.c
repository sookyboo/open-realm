#ifdef BZ_TESTS
/*
 * t_mapscript.c — DotA-style scripts\war3map.j lookup and null mapscript safety.
 *
 * CM_ReadMapScript must prefer war3map.j, then scripts\war3map.j. Missing both
 * leaves mapscript NULL without inventing an empty buffer. jass_dobuffer must
 * refuse NULL instead of crashing in jass_remove_comments.
 */
#include "test.h"
#include "../g_local.h"
#include "jass/jass.h"

#include <stdio.h>
#include <unistd.h>

extern jassModule_t jass_funcs[];
void CM_ReadMapScript(handle_t archive);
bool G_TestFixCampaignHeroRestoreScripts(char **script);
bool run_test_jass(cstring_t src);

static cstring_t const kMinimalMapScript =
    "function config takes nothing returns nothing\n"
    "endfunction\n"
    "function main takes nothing returns nothing\n"
    "endfunction\n";

static void mapscript_ignore_error(cstring_t message) { (void)message; }

static bool mapscript_pack_mpq(cstring_t path, cstring_t member, cstring_t text) {
    handle_t archive;

    unlink(path);
    if (!SFileCreateArchive(path, 0, 16, &archive))
        return false;
    if (member && text) {
        if (!SFileAddFileFromBuffer(archive, member, text, (uint32_t)strlen(text))) {
            SFileCloseArchive(archive);
            unlink(path);
            return false;
        }
    } else if (!SFileAddFileFromBuffer(archive, "dummy.txt", "x", 1)) {
        SFileCloseArchive(archive);
        unlink(path);
        return false;
    }
    if (!SFileCloseArchive(archive)) {
        unlink(path);
        return false;
    }
    return true;
}

static void mapscript_clear_loaded(void) {
    if (world.info.mapscript) {
        gi.MemFree(world.info.mapscript);
        world.info.mapscript = NULL;
    }
}

TEST(wc3_mapscript, jass_dobuffer_null_returns_false) {
    jass_t *j;

    jass_sethost(&MAKE(jassHost_t,
        .MemAlloc = gi.MemAlloc,
        .MemFree = gi.MemFree,
        .GetTime = gi.GetTime,
        .ReadFile = gi.ReadFile,
        .natives = jass_funcs,
        .GetPlayerByNumber = G_GetPlayerByNumber,
        .TimerCoroutineValid = G_TimerCoroutineValid,
        .RuntimeError = mapscript_ignore_error,
        .SaveHandle = G_SaveJassHandle,
        .LoadHandle = G_LoadJassHandle,
        .VariableChanged = G_JassVariableChanged,
    ));
    j = jass_newstate();
    T_NOT_NULL(j);
    T_ASSERT(!jass_dobuffer(j, NULL));
    T_ASSERT(jass_rterror_pending(j));
    T_ASSERT(!jass_dobuffer_ex(j, NULL, JASS_MODE_JASS));
    T_ASSERT(jass_rterror_pending(j));
    jass_close(j);
}

TEST(wc3_mapscript, read_scripts_war3map_j_when_root_absent) {
    cstring_t path = "/tmp/openwarcraft3-mapscript-scripts.mpq";
    handle_t archive;

    T_ASSERT(mapscript_pack_mpq(path, "scripts\\war3map.j", kMinimalMapScript));
    T_ASSERT(SFileOpenArchive(path, 0, 0, &archive));
    mapscript_clear_loaded();
    CM_ReadMapScript(archive);
    SFileCloseArchive(archive);
    unlink(path);
    T_NOT_NULL(world.info.mapscript);
    T_ASSERT(strstr(world.info.mapscript, "function config") != NULL);
    T_ASSERT(strstr(world.info.mapscript, "function main") != NULL);
    mapscript_clear_loaded();
}

TEST(wc3_mapscript, root_war3map_j_preferred_over_scripts) {
    cstring_t path = "/tmp/openwarcraft3-mapscript-both.mpq";
    handle_t archive;
    cstring_t root = "function config takes nothing returns nothing\nendfunction\n"
                  "function main takes nothing returns nothing\nendfunction\n"
                  "// root\n";
    cstring_t nested = "function config takes nothing returns nothing\nendfunction\n"
                    "function main takes nothing returns nothing\nendfunction\n"
                    "// scripts\n";

    unlink(path);
    T_ASSERT(SFileCreateArchive(path, 0, 16, &archive));
    T_ASSERT(SFileAddFileFromBuffer(archive, "war3map.j", root, (uint32_t)strlen(root)));
    T_ASSERT(SFileAddFileFromBuffer(archive, "scripts\\war3map.j", nested, (uint32_t)strlen(nested)));
    T_ASSERT(SFileCloseArchive(archive));
    T_ASSERT(SFileOpenArchive(path, 0, 0, &archive));
    mapscript_clear_loaded();
    CM_ReadMapScript(archive);
    SFileCloseArchive(archive);
    unlink(path);
    T_NOT_NULL(world.info.mapscript);
    T_ASSERT(strstr(world.info.mapscript, "// root") != NULL);
    T_ASSERT(strstr(world.info.mapscript, "// scripts") == NULL);
    mapscript_clear_loaded();
}

TEST(wc3_mapscript, cached_campaign_heroes_get_map_authored_baseline_merge) {
    char source[] =
        "globals\n"
        "  unit udg_Thrall = null\n"
        "  unit udg_Cairne = null\n"
        "endglobals\n"
        "function CacheMissThrall takes nothing returns boolean\n"
        "  return ( udg_Thrall == null )\n"
        "endfunction\n"
        "function CacheMissCairne takes nothing returns boolean\n"
        "  return ( udg_Cairne == null )\n"
        "endfunction\n"
        "function Trig_LoadCampaignHeroes_Actions takes nothing returns nothing\n"
        "    call InitGameCacheBJ( \"Campaigns.w3v\" )\n"
        "    call RestoreUnitLocFacingAngleBJ( \"Thrall\", \"Orc07\", GetLastCreatedGameCacheBJ(), Player(0), GetRectCenter(gg_rct_Thrall), 320.00 )\n"
        "    set udg_Thrall = GetLastRestoredUnitBJ()\n"
        "    if ( CacheMissThrall() ) then\n"
        "        call CreateNUnitsAtLoc( 1, 'Othr', Player(0), GetRectCenter(gg_rct_Thrall), 320.00 )\n"
        "        set udg_Thrall = GetLastCreatedUnit()\n"
        "        call SetHeroLevel( udg_Thrall, 7, false )\n"
        "        call SetHeroXP( udg_Thrall, 3500, false )\n"
        "        call SelectHeroSkill( udg_Thrall, 'AOcl' )\n"
        "        call SelectHeroSkill( udg_Thrall, 'AOcl' )\n"
        "        call SelectHeroSkill( udg_Thrall, 'AOsf' )\n"
        "        call SetWidgetLife( udg_Thrall, 250.00 )\n"
        "        call SetUnitState( udg_Thrall, UNIT_STATE_MANA, 180.00 )\n"
        "    else\n"
        "        call DoNothing()\n"
        "    endif\n"
        "    call RestoreUnitLocFacingAngleBJ( \"Cairne\", \"Orc07\", GetLastCreatedGameCacheBJ(), Player(0), GetRectCenter(gg_rct_Cairne), 280.00 )\n"
        "    set udg_Cairne = GetLastRestoredUnitBJ()\n"
        "    if ( CacheMissCairne() ) then\n"
        "        call CreateNUnitsAtLoc( 1, 'Ocbh', Player(0), GetRectCenter(gg_rct_Cairne), 280.00 )\n"
        "        set udg_Cairne = GetLastCreatedUnit()\n"
        "        call SetHeroLevel( udg_Cairne, 8, false )\n"
        "        call SelectHeroSkill( udg_Cairne, 'AOae' )\n"
        "        call SelectHeroSkill( udg_Cairne, 'AOre' )\n"
        "    else\n"
        "        call DoNothing()\n"
        "    endif\n"
        "endfunction\n"
        "function main takes nothing returns nothing\n"
        "endfunction\n";
    char *script = gi.MemAlloc(sizeof(source));
    char *first;
    char *thrall, *cairne;

    T_NOT_NULL(script);
    memcpy(script, source, sizeof(source));
    T_ASSERT(G_TestFixCampaignHeroRestoreScripts(&script));
    T_ASSERT(strstr(script, "local unit campaign_fallback_hero_0") != NULL);
    T_ASSERT(strstr(script, "local unit campaign_fallback_hero_1") != NULL);
    thrall = strstr(script, "'Othr'");
    cairne = strstr(script, "'Ocbh'");
    T_NOT_NULL(thrall);
    T_NOT_NULL(cairne);
    T_ASSERT(strstr(thrall, "SetHeroLevel( campaign_fallback_hero_0, 7, false )") != NULL);
    T_ASSERT(strstr(thrall, "SetHeroXP( campaign_fallback_hero_0, 3500, false )") != NULL);
    T_ASSERT(strstr(thrall, "SelectHeroSkill( campaign_fallback_hero_0, 'AOcl' )") != NULL);
    T_ASSERT(strstr(thrall, "SetWidgetLife( campaign_fallback_hero_0, 250.00 )") != NULL);
    T_ASSERT(strstr(thrall, "SetUnitState( campaign_fallback_hero_0, UNIT_STATE_MANA, 180.00 )") != NULL);
    T_ASSERT(strstr(cairne, "SetHeroLevel( campaign_fallback_hero_1, 8, false )") != NULL);
    T_ASSERT(strstr(cairne, "SelectHeroSkill( campaign_fallback_hero_1, 'AOre' )") != NULL);
    T_ASSERT(strstr(script, "GetWidgetLife(campaign_fallback_hero_0)") != NULL);
    T_ASSERT(strstr(script, "UNIT_STATE_MANA") != NULL);
    T_ASSERT(strstr(script, "call RemoveUnit( campaign_fallback_hero_0 )") != NULL);
    T_ASSERT(strstr(script, "call RemoveUnit( udg_Thrall )") == NULL);
    T_ASSERT(run_test_jass(script));
    first = script;
    T_ASSERT(G_TestFixCampaignHeroRestoreScripts(&script));
    T_ASSERT(script == first);
    gi.MemFree(script);
}

TEST(wc3_mapscript, cached_campaign_hero_uses_separate_default_trigger) {
    char source[] =
        "globals\n"
        "  unit udg_Arthas = null\n"
        "  player udg_Player = null\n"
        "  trigger gg_trg_Default_Arthas = null\n"
        "endglobals\n"
        "function CacheMissArthas takes nothing returns boolean\n"
        "  return ( udg_Arthas == null )\n"
        "endfunction\n"
        "function Trig_LoadArthas_Actions takes nothing returns nothing\n"
        "    call InitGameCacheBJ( \"Campaigns.w3v\" )\n"
        "    call RestoreUnitLocFacingAngleBJ( \"Arthas\", \"Undead07\", GetLastCreatedGameCacheBJ(), udg_Player, GetRectCenter(gg_rct_Arthas), 90.00 )\n"
        "    set udg_Arthas = GetLastRestoredUnitBJ()\n"
        "    if ( CacheMissArthas() ) then\n"
        "        call ConditionalTriggerExecute( gg_trg_Default_Arthas )\n"
        "    else\n"
        "        call DoNothing()\n"
        "    endif\n"
        "endfunction\n"
        "function Trig_Default_Arthas_Actions takes nothing returns nothing\n"
        "    call CreateNUnitsAtLocFacingLocBJ( 1, 'Hart', udg_Player, GetRectCenter(gg_rct_Arthas), GetCameraTargetPositionLoc() )\n"
        "    set udg_Arthas = GetLastCreatedUnit()\n"
        "    call SetHeroLevelBJ( udg_Arthas, 6, false )\n"
        "    call SelectHeroSkill( udg_Arthas, 'AUdc' )\n"
        "    call SelectHeroSkill( udg_Arthas, 'AUdc' )\n"
        "    call SelectHeroSkill( udg_Arthas, 'AUau' )\n"
        "endfunction\n"
        "function main takes nothing returns nothing\n"
        "endfunction\n";
    char *script = gi.MemAlloc(sizeof(source));

    T_NOT_NULL(script);
    memcpy(script, source, sizeof(source));
    T_ASSERT(G_TestFixCampaignHeroRestoreScripts(&script));
    T_ASSERT(strstr(script, "SetHeroLevel( campaign_fallback_hero_0, 6, false )") != NULL);
    T_ASSERT(strstr(script, "'Hart'") != NULL);
    T_ASSERT(strstr(script, "SelectHeroSkill( campaign_fallback_hero_0, 'AUau' )") != NULL);
    T_ASSERT(strstr(script, "call RemoveUnit( campaign_fallback_hero_0 )") != NULL);
    T_ASSERT(strstr(script, "call RemoveUnit( udg_Arthas )") == NULL);
    T_ASSERT(run_test_jass(script));
    gi.MemFree(script);
}

TEST(wc3_mapscript, cached_campaign_hero_combines_fallback_create_and_setup_trigger) {
    char source[] =
        "globals\n"
        "  unit udg_Arthas = null\n"
        "  player udg_Player = null\n"
        "  trigger gg_trg_SetArthasLevelsSkills = null\n"
        "endglobals\n"
        "function CacheMissArthas takes nothing returns boolean\n"
        "  return ( udg_Arthas != null )\n"
        "endfunction\n"
        "function Trig_LoadArthas_Actions takes nothing returns nothing\n"
        "    call InitGameCacheBJ( \"Campaigns.w3v\" )\n"
        "    call RestoreUnitLocFacingPointBJ( \"Arthas\", \"Human07\", GetLastCreatedGameCacheBJ(), udg_Player, GetRectCenter(gg_rct_Arthas), GetRectCenter(gg_rct_Facing) )\n"
        "    set udg_Arthas = GetLastRestoredUnitBJ()\n"
        "    if ( CacheMissArthas() ) then\n"
        "        return\n"
        "    else\n"
        "        call DoNothing()\n"
        "    endif\n"
        "    call CreateNUnitsAtLocFacingLocBJ( 1, 'Hart', udg_Player, GetRectCenter(gg_rct_Arthas), GetRectCenter(gg_rct_Facing) )\n"
        "    set udg_Arthas = GetLastCreatedUnit()\n"
        "    call TriggerExecute( gg_trg_SetArthasLevelsSkills )\n"
        "endfunction\n"
        "function Trig_SetArthasLevelsSkills_Actions takes nothing returns nothing\n"
        "    call SetHeroLevel( udg_Arthas, 7, false )\n"
        "    call SelectHeroSkill( udg_Arthas, 'AHhb' )\n"
        "    call SelectHeroSkill( udg_Arthas, 'AHhb' )\n"
        "    call SelectHeroSkill( udg_Arthas, 'AHre' )\n"
        "endfunction\n"
        "function main takes nothing returns nothing\n"
        "endfunction\n";
    char *script = gi.MemAlloc(sizeof(source));

    T_NOT_NULL(script);
    memcpy(script, source, sizeof(source));
    T_ASSERT(G_TestFixCampaignHeroRestoreScripts(&script));
    T_ASSERT(strstr(script, "SetHeroLevel( campaign_fallback_hero_0, 7, false )") != NULL);
    T_ASSERT(strstr(script, "SelectHeroSkill( campaign_fallback_hero_0, 'AHre' )") != NULL);
    T_ASSERT(run_test_jass(script));
    gi.MemFree(script);
}

TEST(wc3_mapscript, cached_campaign_hero_supports_tft_restore_helper_and_xp_bonus) {
    char source[] =
        "globals\n"
        "  unit udg_Kael = null\n"
        "  player udg_Player = null\n"
        "endglobals\n"
        "function Trig_Load_Kael_Func004001 takes nothing returns boolean\n"
        "    return ( GetLastRestoredUnitBJ() != null )\n"
        "endfunction\n"
        "function Trig_Load_Kael_Actions takes nothing returns nothing\n"
        "    call InitGameCacheBJ( \"Campaigns.w3v\" )\n"
        "    call RestoreUnitLocFacingAngleBJ( \"Kael\", \"HumanX02\", GetLastCreatedGameCacheBJ(), udg_Player, GetRectCenter(gg_rct_Kael), 350.00 )\n"
        "    set udg_Kael = GetLastRestoredUnitBJ()\n"
        "    if ( Trig_Load_Kael_Func004001() ) then\n"
        "        return\n"
        "    else\n"
        "        call DoNothing()\n"
        "    endif\n"
        "    call CreateNUnitsAtLoc( 1, 'Hkal', udg_Player, GetRectCenter(gg_rct_Kael), 350.00 )\n"
        "    set udg_Kael = GetLastCreatedUnit()\n"
        "    call SetHeroLevelBJ( GetLastCreatedUnit(), 5, false )\n"
        "    call AddHeroXP( GetLastCreatedUnit(), 400, false )\n"
        "    call SelectHeroSkill( GetLastCreatedUnit(), 'AHfs' )\n"
        "endfunction\n"
        "function main takes nothing returns nothing\n"
        "endfunction\n";
    char *script = gi.MemAlloc(sizeof(source));

    T_NOT_NULL(script);
    memcpy(script, source, sizeof(source));
    T_ASSERT(G_TestFixCampaignHeroRestoreScripts(&script));
    T_ASSERT(strstr(script, "IsUnitType(udg_Kael, UNIT_TYPE_HERO)") != NULL);
    T_ASSERT(strstr(script, "AddHeroXP( campaign_fallback_hero_0, 400, false )") != NULL);
    T_ASSERT(strstr(script, "SelectHeroSkill( campaign_fallback_hero_0, 'AHfs' )") != NULL);
    T_ASSERT(strstr(script, "GetHeroXP(udg_Kael) < GetHeroXP(campaign_fallback_hero_0)") != NULL);
    T_ASSERT(run_test_jass(script));
    gi.MemFree(script);
}

TEST(wc3_mapscript, missing_script_leaves_null_without_crash) {
    cstring_t path = "/tmp/openwarcraft3-mapscript-missing.mpq";
    handle_t archive;

    T_ASSERT(mapscript_pack_mpq(path, NULL, NULL));
    T_ASSERT(SFileOpenArchive(path, 0, 0, &archive));
    mapscript_clear_loaded();
    CM_ReadMapScript(archive);
    SFileCloseArchive(archive);
    unlink(path);
    T_NULL(world.info.mapscript);
}

#endif /* BZ_TESTS */

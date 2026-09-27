uint32_t CreateQuest(jass_t *j) {
    quest_t *quest = G_MakeQuest();
    return jass_pushlighthandle(j, quest, "quest");
}
uint32_t DestroyQuest(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (G_QuestValid(whichQuest)) G_RemoveQuest(whichQuest);
    return 0;
}
uint32_t QuestSetTitle(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    cstring_t title = jass_checkstring(j, 2);
    if (!G_QuestValid(whichQuest)) return 0;
    whichQuest->title = strdup(title);
    return 0;
}
uint32_t QuestSetDescription(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    cstring_t description = jass_checkstring(j, 2);
    if (!G_QuestValid(whichQuest)) return 0;
    whichQuest->description = strdup(description);
    return 0;
}
uint32_t QuestSetIconPath(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    cstring_t iconPath = jass_checkstring(j, 2);
    if (!G_QuestValid(whichQuest)) return 0;
    whichQuest->iconPath = strdup(iconPath);
    return 0;
}
uint32_t QuestSetRequired(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return 0;
    whichQuest->required = jass_checkboolean(j, 2);
    return 0;
}
uint32_t QuestSetCompleted(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return 0;
    whichQuest->completed = jass_checkboolean(j, 2);
    return 0;
}
uint32_t QuestSetDiscovered(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return 0;
    whichQuest->discovered = jass_checkboolean(j, 2);
    return 0;
}
uint32_t QuestSetFailed(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return 0;
    whichQuest->failed = jass_checkboolean(j, 2);
    return 0;
}
uint32_t QuestSetEnabled(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return 0;
    whichQuest->enabled = jass_checkboolean(j, 2);
    return 0;
}
uint32_t IsQuestRequired(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return jass_pushboolean(j, 0);
    return jass_pushboolean(j, whichQuest->required);
}
uint32_t IsQuestCompleted(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return jass_pushboolean(j, 0);
    return jass_pushboolean(j, whichQuest->completed);
}
uint32_t IsQuestDiscovered(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return jass_pushboolean(j, 0);
    return jass_pushboolean(j, whichQuest->discovered);
}
uint32_t IsQuestFailed(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return jass_pushboolean(j, 0);
    return jass_pushboolean(j, whichQuest->failed);
}
uint32_t IsQuestEnabled(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return jass_pushboolean(j, 0);
    return jass_pushboolean(j, whichQuest->enabled);
}
uint32_t QuestCreateItem(jass_t *j) {
    quest_t *whichQuest = jass_checkhandle(j, 1, "quest");
    if (!G_QuestValid(whichQuest)) return jass_pushnullhandle(j, "questitem");
    FOR_LOOP(i, MAX_QUESTITEMS) if (!whichQuest->items[i].inuse) {
        questItem_t *item = &whichQuest->items[i];
        memset(item, 0, sizeof(*item)); item->inuse = true; whichQuest->num_items++;
        return jass_pushlighthandle(j, item, "questitem");
    }
    fprintf(stderr, "WC3: quest item slot limit %u reached\n", MAX_QUESTITEMS);
    return jass_pushnullhandle(j, "questitem");
}
uint32_t QuestItemSetDescription(jass_t *j) {
    questItem_t *whichQuestItem = jass_checkhandle(j, 1, "questitem");
    cstring_t description = jass_checkstring(j, 2);
    if (!G_QuestItemValid(whichQuestItem)) return 0;
    whichQuestItem->description = strdup(description);
    return 0;
}
uint32_t QuestItemSetCompleted(jass_t *j) {
    questItem_t *whichQuestItem = jass_checkhandle(j, 1, "questitem");
    if (!G_QuestItemValid(whichQuestItem)) return 0;
    whichQuestItem->completed = jass_checkboolean(j, 2);
    if (WC3_TUTORIAL_DEBUG_ENABLED()) {
        uint32_t quest_index = UINT32_MAX, item_index = UINT32_MAX;
        FOR_LOOP(qi, MAX_QUESTS) {
            FOR_LOOP(ii, level.quests[qi].num_items) {
                if (&level.quests[qi].items[ii] == whichQuestItem) {
                    quest_index = qi; item_index = ii; break;
                }
            }
            if (quest_index != UINT32_MAX) break;
        }
        fprintf(stderr, "WC3_HORN_TRACE quest-item-complete quest-index=%u title=\"%s\" item-index=%u item=%p completed=%d\n",
                quest_index, quest_index != UINT32_MAX && level.quests[quest_index].title ?
                    level.quests[quest_index].title : "(unknown)", item_index,
                (void *)whichQuestItem, (int)whichQuestItem->completed);
        if (quest_index != UINT32_MAX && item_index == 3) {
            fprintf(stderr,
                    "WC3_MOONGLADE_TRACE quest-item item-index=3 title=\"%s\" completed=%d\n",
                    level.quests[quest_index].title ? level.quests[quest_index].title : "(unknown)",
                    (int)whichQuestItem->completed);
        }
    }
    return 0;
}
uint32_t IsQuestItemCompleted(jass_t *j) {
    questItem_t *whichQuestItem = jass_checkhandle(j, 1, "questitem");
    if (!G_QuestItemValid(whichQuestItem)) return jass_pushboolean(j, 0);
    return jass_pushboolean(j, whichQuestItem->completed);
}
uint32_t CreateDefeatCondition(jass_t *j) {
    return jass_pushnullhandle(j, "defeatcondition");
}
uint32_t DestroyDefeatCondition(jass_t *j) {
    //handle_t whichCondition = jass_checkhandle(j, 1, "defeatcondition");
    return 0;
}
uint32_t DefeatConditionSetDescription(jass_t *j) {
    //handle_t whichCondition = jass_checkhandle(j, 1, "defeatcondition");
    //cstring_t description = jass_checkstring(j, 2);
    return 0;
}
/* Blizzard.j requests this per recipient; MiscData owns the notification timeout. */
uint32_t FlashQuestDialogButton(jass_t *j) {
    cstring_t value = Stb_IniCacheFind(&game.config.misc, "QuestIndicatorTimeout", "QuestIndicatorTimeout");
    float seconds;
    (void)j;
    if (!value || sscanf(value, "%f", &seconds) != 1 || !isfinite(seconds) || seconds <= 0) {
        fprintf(stderr, "WC3: missing or invalid QuestIndicatorTimeout\n");
        return 0;
    }
    FOR_LOOP(i, game.max_clients) {
        gameClient_t *client = &game.clients[i];
        if (!currentplayer || client == PLAYER_CLIENT(currentplayer))
            client->quest_until = level.time + (uint32_t)(seconds * 1000.0f);
    }
    return 0;
}
uint32_t ForceQuestDialogUpdate(jass_t *j) {
    /* Quest windows are send-once client presentation; the native has no server-side window to refresh. */
    (void)j;
    return 0;
}

#include "g_local.h"

BOOL jass_calltrigger(LPJASS j, LPTRIGGER trigger, LPEDICT unit, LPEDICT source);

static BOOL G_DispatchEventTrigger(GAMEEVENT *evt, LPEVENT handler, LPEDICT subject) {
    BOOL ran;

    if (G_EndgameDebug() && G_EndgameEventInteresting(evt->type)) {
        G_EndgameDebugf(
            "handler match event=%s(%d) trigger=%p subject=%ld class=%.4s owner=%u\n",
            G_EventName(evt->type),
            (int)evt->type,
            (void *)handler->trigger,
            subject ? (long)subject->s.number : -1L,
            subject ? (LPCSTR)&subject->class_id : "----",
            subject ? (unsigned)subject->s.player : 0u);
    }
    ran = jass_calltrigger(level.vm, handler->trigger, subject, evt->source);
    if (G_EndgameDebug() && G_EndgameEventInteresting(evt->type)) {
        G_EndgameDebugf(
            "handler result event=%s trigger=%p conditions=%s\n",
            G_EventName(evt->type),
            (void *)handler->trigger,
            ran ? "passed" : "failed-or-disabled");
    }
    return ran;
}

static void G_ExecuteEvent(GAMEEVENT *evt) {
    LPEDICT subject = evt->edict;
    BOOL matched = false;
    FOR_EACH_LIST(EVENT, e, level.events.handlers) {
        switch (e->type) {
            case EVENT_GAME_VICTORY:
                break;
            case EVENT_GAME_END_LEVEL:
                break;
            case EVENT_GAME_VARIABLE_LIMIT:
                break;
            case EVENT_GAME_STATE_LIMIT:
                break;
            case EVENT_GAME_TIMER_EXPIRED:
                break;
            case EVENT_GAME_ENTER_REGION:
                if (evt->responseTo == e) {
                    matched = true;
                    G_DispatchEventTrigger(evt, e, subject);
                }
                break;
            case EVENT_GAME_LEAVE_REGION:
                if (evt->responseTo == e) {
                    matched = true;
                    G_DispatchEventTrigger(evt, e, subject);
                }
                break;
            case EVENT_UNIT_IN_RANGE:
                if (evt->responseTo == e) {
                    matched = true;
                    G_DispatchEventTrigger(evt, e, subject);
                }
                break;
            case EVENT_GAME_TRACKABLE_HIT:
                break;
            case EVENT_GAME_TRACKABLE_TRACK:
                break;
            case EVENT_GAME_SHOW_SKILL:
                break;
            case EVENT_GAME_BUILD_SUBMENU:
                break;
            default:
                /* Two subject conventions share this path:
                 *  - widget/unit events (e.g. EVENT_UNIT_DEATH): the handler's
                 *    subject is a specific unit, matched directly.
                 *  - player-unit events (EVENT_PLAYER_UNIT_*): registered via
                 *    TriggerRegisterPlayerUnitEvent with subject = the player's
                 *    edict; they fire for ANY of that player's units, so match
                 *    the dying/triggering unit's owner against the handler's
                 *    player.  Either way the triggering unit is passed as the
                 *    context unit so GetTriggerUnit()/GetDyingUnit() resolve to
                 *    it (e.g. Naga_Victory_Check counts the dying naga). */
                if (e->type == evt->type && subject &&
                    (e->subject == subject ||
                     e->subject == G_GetPlayerEntityByNumber(subject->s.player))) {
                    matched = true;
                    G_DispatchEventTrigger(evt, e, subject);
                }
                break;
        }
    }
    if (G_EndgameDebug() && G_EndgameEventInteresting(evt->type) && !matched) {
        G_EndgameDebugf(
            "dispatch event=%s(%d) no-matching-handler subject=%ld class=%.4s owner=%u\n",
            G_EventName(evt->type),
            (int)evt->type,
            subject ? (long)subject->s.number : -1L,
            subject ? (LPCSTR)&subject->class_id : "----",
            subject ? (unsigned)subject->s.player : 0u);
    }
}

static void G_TouchTriggers(LPEDICT ent) {
    FOR_EACH_LIST(EVENT, evt, level.events.handlers) {
        switch (evt->type) {
            case EVENT_GAME_ENTER_REGION:
                if (G_RegionContains(&evt->region, &ent->s.origin2) &&
                    !G_RegionContains(&evt->region, &ent->old_origin))
                {
                    G_PublishEvent(ent, evt->type)->responseTo = evt;
                }
                break;
            case EVENT_GAME_LEAVE_REGION:
                if (!G_RegionContains(&evt->region, &ent->s.origin2) &&
                    G_RegionContains(&evt->region, &ent->old_origin))
                {
                    G_PublishEvent(ent, evt->type)->responseTo = evt;
                }
                break;
            case EVENT_UNIT_IN_RANGE:
                if (ent != evt->subject &&
                    Vector2_distance(&((LPEDICT)evt->subject)->old_origin, &ent->old_origin) > evt->range &&
                    Vector2_distance(&((LPEDICT)evt->subject)->s.origin2, &ent->s.origin2) <= evt->range)
                {
                    GAMEEVENT *e = G_PublishEvent(ent, evt->type);
                    e->edict = ent;
                    e->responseTo = evt;
                }
                break;
            default:
                break;
        }
    }
}

void G_RunEntities(void) {
    FOR_LOOP(i, globals.num_edicts) {
        LPEDICT ent = globals.edicts+i;
        if (!ent->inuse) continue; /* freed edicts are memset and never re-sent; skip the per-frame clear */
        ent->old_origin = ent->s.origin2;
        if (ent->sound.pending) {
            gi.Sound(ent, CHAN_VOICE | CHAN_OWNER | CHAN_RELIABLE, ent->sound.pending, 1.0f, 0.0f, 0.0f);
            ent->sound.pending = 0;
        }
        if (ent->sound.owner_pending) {
            gi.Sound(ent, CHAN_VOICE | CHAN_OWNER | CHAN_RELIABLE, ent->sound.owner_pending, 1.0f, 0.0f, 0.0f);
            ent->sound.owner_pending = 0;
        }
        if (ent->sound.world_pending) {
            gi.Sound(ent, CHAN_VOICE, ent->sound.world_pending, 1.0f, 1.0f, 0.0f);
            ent->sound.world_pending = 0;
            ent->sound.world_pending_event = EV_NONE;
        }
    }
    FOR_LOOP(i, globals.num_edicts) {
        LPEDICT ent = globals.edicts+i;
        if (!ent->inuse) continue;
        G_RunEntity(ent);
    }
    FOR_LOOP(i, globals.num_edicts) {
        LPEDICT ent = globals.edicts+i;
        if (!ent->inuse) continue;
        if (!memcmp(&ent->old_origin, &ent->s.origin2, sizeof(VECTOR2)))
            continue;
        G_TouchTriggers(ent);
    }
}

void G_RunEvents(void) {
    for (LEVELEVENTS *e = &level.events; e->read < e->write; e->read++) {
        GAMEEVENT *evt = &e->queue[e->read % MAX_EVENT_QUEUE];
        G_ExecuteEvent(evt);
    }
}

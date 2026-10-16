function PS_Log takes string value returns nothing
    call BJDebugMsg(value)
    call Preload(value)
endfunction

function PS_SpellEffect takes nothing returns nothing
    local unit caster = GetTriggerUnit()
    local integer casterId = GetHandleId(caster)
    if casterId == PS_heroCasterId and GetSpellAbilityId() == 'AEsh' and GetSpellTargetUnit() == PS_heroTarget then
        set PS_heroCastSeen = 1
        set PS_heroCastTick = PS_tick
        call PS_Log("PS_CAST_EFFECT ability=AEsh tick=" + I2S(PS_tick) + " target=" + I2S(PS_heroTargetId))
    elseif casterId == PS_creepCasterId and GetSpellAbilityId() == 'ACss' and GetSpellTargetUnit() == PS_creepTarget then
        set PS_creepCastSeen = 1
        set PS_creepCastTick = PS_tick
        call PS_Log("PS_CAST_EFFECT ability=ACss tick=" + I2S(PS_tick) + " target=" + I2S(PS_creepTargetId))
    endif
    set caster = null
endfunction

function PS_Damaged takes nothing returns nothing
    local unit target = GetTriggerUnit()
    local unit source = GetEventDamageSource()
    local integer sourceId = GetHandleId(source)
    local integer targetId = GetHandleId(target)
    local real damage = GetEventDamage()
    if targetId == PS_heroTargetId and sourceId == PS_heroCasterId then
        set PS_heroHitCount = PS_heroHitCount + 1
        call PS_Log("PS_HIT ability=AEsh tick=" + I2S(PS_tick) + " age=" + I2S(PS_tick - PS_heroCastTick) + " damage=" + R2S(damage) + " count=" + I2S(PS_heroHitCount) + " source=" + I2S(sourceId) + " target=" + I2S(targetId))
    elseif targetId == PS_creepTargetId and sourceId == PS_creepCasterId then
        set PS_creepHitCount = PS_creepHitCount + 1
        call PS_Log("PS_HIT ability=ACss tick=" + I2S(PS_tick) + " age=" + I2S(PS_tick - PS_creepCastTick) + " damage=" + R2S(damage) + " count=" + I2S(PS_creepHitCount) + " source=" + I2S(sourceId) + " target=" + I2S(targetId))
    elseif targetId == PS_controlId then
        set PS_controlHitCount = PS_controlHitCount + 1
        call PS_Log("PS_CONTROL_HIT tick=" + I2S(PS_tick) + " damage=" + R2S(damage) + " count=" + I2S(PS_controlHitCount) + " source=" + I2S(sourceId))
    endif
    set target = null
    set source = null
endfunction

function PS_B2I takes boolean value returns integer
    if value then
        return 1
    endif
    return 0
endfunction

function PS_Tick takes nothing returns nothing
    local real heroSpeed
    local real creepSpeed
    local integer heroAge
    local integer creepAge
    set PS_tick = PS_tick + 1

    call SetUnitX(PS_heroTarget, I2R(PS_x))
    call SetUnitY(PS_heroTarget, I2R(PS_y))
    call SetUnitX(PS_creepTarget, I2R(PS_x))
    call SetUnitY(PS_creepTarget, I2R(PS_y + 300))
    call SetUnitX(PS_control, I2R(PS_x))
    call SetUnitY(PS_control, I2R(PS_y + 600))

    if ModuloInteger(PS_tick, 5) == 0 then
        set heroSpeed = GetUnitMoveSpeed(PS_heroTarget)
        set creepSpeed = GetUnitMoveSpeed(PS_creepTarget)
        set heroAge = -1
        set creepAge = -1
        if PS_heroCastTick >= 0 then
            set heroAge = PS_tick - PS_heroCastTick
        endif
        if PS_creepCastTick >= 0 then
            set creepAge = PS_tick - PS_creepCastTick
        endif
        call PS_Log("PS_SAMPLE tick=" + I2S(PS_tick) + " heroAge=" + I2S(heroAge) + " heroSpeed=" + R2S(heroSpeed) + " creepAge=" + I2S(creepAge) + " creepSpeed=" + R2S(creepSpeed) + " controlSpeed=" + R2S(GetUnitMoveSpeed(PS_control)))
    endif

    if PS_tick == 100 then
        call PS_Log("PS_BASELINE hero=" + R2S(GetUnitMoveSpeed(PS_heroTarget)) + " creep=" + R2S(GetUnitMoveSpeed(PS_creepTarget)) + " control=" + R2S(GetUnitMoveSpeed(PS_control)))
        call PS_Log("PS_CAST_ORDER ability=AEsh accepted=" + I2S(PS_B2I(IssueTargetOrder(PS_heroCaster, "shadowstrike", PS_heroTarget))))
    endif
    if PS_tick == 130 then
        call PS_Log("PS_CAST_ORDER ability=ACss accepted=" + I2S(PS_B2I(IssueTargetOrder(PS_creepCaster, "shadowstrike", PS_creepTarget))))
    endif
    if PS_tick == 500 then
        if PS_heroCastSeen != 1 or PS_creepCastSeen != 1 then
            call PS_Log("PS_SETUP_FAIL reason=spell_effect_missing")
        endif
        call PS_Log("PS_DONE heroCast=" + I2S(PS_heroCastSeen) + " creepCast=" + I2S(PS_creepCastSeen) + " heroHits=" + I2S(PS_heroHitCount) + " creepHits=" + I2S(PS_creepHitCount) + " controlHits=" + I2S(PS_controlHitCount))
        call PreloadGenEnd("shadow-strike-poison-run2.txt")
        call PauseTimer(PS_timer)
        call DestroyTimer(PS_timer)
        set PS_timer = null
    endif
endfunction

function PS_Start takes nothing returns nothing
    local real x = GetStartLocationX(0) + 1800.0
    local real y = GetStartLocationY(0) + 600.0
    call FogEnable(false)
    call FogMaskEnable(false)
    call PreloadGenClear()
    call PreloadGenStart()
    set PS_tick = 0
    set PS_heroCastTick = -1
    set PS_creepCastTick = -1
    set PS_heroCastSeen = 0
    set PS_creepCastSeen = 0
    set PS_heroHitCount = 0
    set PS_creepHitCount = 0
    set PS_controlHitCount = 0
    set PS_x = R2I(x + 200.0)
    set PS_y = R2I(y)
    call PS_Log("PS_META build=1.29.2.9231 tickSeconds=0.05 durationTicks=500 sampleEveryTicks=5 baselineTicks=100 AEshCastTick=100 ACssCastTick=130")

    set PS_heroCaster = CreateUnit(Player(0), 'Ewar', x, y, 0.0)
    set PS_creepCaster = CreateUnit(Player(0), 'Ewar', x, y + 300.0, 0.0)
    set PS_heroTarget = CreateUnit(Player(12), 'hfoo', x + 200.0, y, 180.0)
    set PS_creepTarget = CreateUnit(Player(12), 'hfoo', x + 200.0, y + 300.0, 180.0)
    set PS_control = CreateUnit(Player(12), 'hfoo', x + 200.0, y + 600.0, 180.0)
    // Prevent the Warden casters' ordinary attacks from mixing with poison
    // events. Explicit target spell orders still work with acquisition off.
    call SetUnitAcquireRange(PS_heroCaster, 0.0)
    call SetUnitAcquireRange(PS_creepCaster, 0.0)
    call SetUnitAcquireRange(PS_heroTarget, 0.0)
    call SetUnitAcquireRange(PS_creepTarget, 0.0)
    call SetUnitAcquireRange(PS_control, 0.0)
    call UnitAddAbility(PS_heroCaster, 'AEsh')
    call SetUnitAbilityLevel(PS_heroCaster, 'AEsh', 1)
    call UnitAddAbility(PS_creepCaster, 'ACss')
    call SetUnitAbilityLevel(PS_creepCaster, 'ACss', 1)
    call SetUnitState(PS_heroCaster, UNIT_STATE_MANA, 1000.0)
    call SetUnitState(PS_creepCaster, UNIT_STATE_MANA, 1000.0)
    call SetUnitMoveSpeed(PS_heroTarget, 400.0)
    call SetUnitMoveSpeed(PS_creepTarget, 400.0)
    call SetUnitMoveSpeed(PS_control, 400.0)
    call BlzSetUnitMaxHP(PS_heroTarget, 100000)
    call BlzSetUnitMaxHP(PS_creepTarget, 100000)
    call BlzSetUnitMaxHP(PS_control, 100000)
    call SetWidgetLife(PS_heroTarget, 100000.0)
    call SetWidgetLife(PS_creepTarget, 100000.0)
    call SetWidgetLife(PS_control, 100000.0)

    set PS_heroCasterId = GetHandleId(PS_heroCaster)
    set PS_creepCasterId = GetHandleId(PS_creepCaster)
    set PS_heroTargetId = GetHandleId(PS_heroTarget)
    set PS_creepTargetId = GetHandleId(PS_creepTarget)
    set PS_controlId = GetHandleId(PS_control)
    set PS_spellTrigger = CreateTrigger()
    call TriggerRegisterUnitEvent(PS_spellTrigger, PS_heroCaster, EVENT_UNIT_SPELL_EFFECT)
    call TriggerRegisterUnitEvent(PS_spellTrigger, PS_creepCaster, EVENT_UNIT_SPELL_EFFECT)
    call TriggerAddAction(PS_spellTrigger, function PS_SpellEffect)
    set PS_damageTrigger = CreateTrigger()
    call TriggerRegisterUnitEvent(PS_damageTrigger, PS_heroTarget, EVENT_UNIT_DAMAGED)
    call TriggerRegisterUnitEvent(PS_damageTrigger, PS_creepTarget, EVENT_UNIT_DAMAGED)
    call TriggerRegisterUnitEvent(PS_damageTrigger, PS_control, EVENT_UNIT_DAMAGED)
    call TriggerAddAction(PS_damageTrigger, function PS_Damaged)
    call PS_Log("PS_SETUP IDs=" + I2S(PS_heroTargetId) + "/" + I2S(PS_creepTargetId) + "/" + I2S(PS_controlId) + " speeds=" + R2S(GetUnitMoveSpeed(PS_heroTarget)) + "/" + R2S(GetUnitMoveSpeed(PS_creepTarget)) + "/" + R2S(GetUnitMoveSpeed(PS_control)) + " abilities=" + I2S(GetUnitAbilityLevel(PS_heroCaster, 'AEsh')) + "/" + I2S(GetUnitAbilityLevel(PS_creepCaster, 'ACss')))
    if PS_heroCasterId == 0 or PS_creepCasterId == 0 or PS_heroTargetId == 0 or PS_creepTargetId == 0 or PS_controlId == 0 then
        call PS_Log("PS_SETUP_FAIL reason=invalid_entity")
    endif
    set PS_timer = CreateTimer()
    set PS_clock = CreateTimer()
    call TimerStart(PS_clock, 1000.0, false, null)
    call TimerStart(PS_timer, 0.05, true, function PS_Tick)
    set x = 0.0
    set y = 0.0
endfunction

function PS_Reload takes nothing returns nothing
    call ExecuteFunc("JHCR_Init_parse")
    call PS_Log("PS_JHCR_STATUS=" + I2S(JHCR_API_GetLastStatus()))
endfunction

function PS_Init takes nothing returns nothing
    if PS_reloadTrigger == null then
        set PS_reloadTrigger = CreateTrigger()
        call TriggerRegisterPlayerChatEvent(PS_reloadTrigger, Player(0), "-jhcr", true)
        call TriggerAddAction(PS_reloadTrigger, function PS_Reload)
    endif
    call PS_Start()
endfunction

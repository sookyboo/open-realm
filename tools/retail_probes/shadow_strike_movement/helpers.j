function MV_B2I takes boolean value returns integer
    if value then
        return 1
    endif
    return 0
endfunction

function MV_Log takes string value returns nothing
    call BJDebugMsg(value)
    call Preload(value)
endfunction

function MV_SpellEffect takes nothing returns nothing
    local unit caster = GetTriggerUnit()
    local integer casterId = GetHandleId(caster)
    if casterId == MV_heroCasterId and GetSpellAbilityId() == 'AEsh' and GetSpellTargetUnit() == MV_heroTarget then
        set MV_heroCastSeen = 1
        set MV_heroCastTick = MV_tick
        call MV_Log("MV_CAST_EFFECT ability=AEsh tick=" + I2S(MV_tick) + " target=" + I2S(MV_heroTargetId))
    elseif casterId == MV_creepCasterId and GetSpellAbilityId() == 'ACss' and GetSpellTargetUnit() == MV_creepTarget then
        set MV_creepCastSeen = 1
        set MV_creepCastTick = MV_tick
        call MV_Log("MV_CAST_EFFECT ability=ACss tick=" + I2S(MV_tick) + " target=" + I2S(MV_creepTargetId))
    endif
    set caster = null
endfunction

function MV_Tick takes nothing returns nothing
    local real heroSpeed
    local real creepSpeed
    local real controlSpeed
    local integer heroAge
    local integer creepAge
    set MV_tick = MV_tick + 1

    // Position-lock targets so campaign AI cannot move them. Speed is read
    // from the unit state, independently of its displacement.
    call SetUnitX(MV_heroTarget, I2R(MV_x))
    call SetUnitY(MV_heroTarget, I2R(MV_y))
    call SetUnitX(MV_creepTarget, I2R(MV_x))
    call SetUnitY(MV_creepTarget, I2R(MV_y + 300))
    call SetUnitX(MV_control, I2R(MV_x))
    call SetUnitY(MV_control, I2R(MV_y + 600))

    if ModuloInteger(MV_tick, 5) == 0 then
        set heroSpeed = GetUnitMoveSpeed(MV_heroTarget)
        set creepSpeed = GetUnitMoveSpeed(MV_creepTarget)
        set controlSpeed = GetUnitMoveSpeed(MV_control)
        set heroAge = -1
        set creepAge = -1
        if MV_heroCastTick >= 0 then
            set heroAge = MV_tick - MV_heroCastTick
        endif
        if MV_creepCastTick >= 0 then
            set creepAge = MV_tick - MV_creepCastTick
        endif
        if MV_tick < 100 then
            set MV_baselineSamples = MV_baselineSamples + 1
        endif
        call MV_Log("MV_SAMPLE tick=" + I2S(MV_tick) + " heroAge=" + I2S(heroAge) + " heroSpeed=" + R2S(heroSpeed) + " creepAge=" + I2S(creepAge) + " creepSpeed=" + R2S(creepSpeed) + " controlSpeed=" + R2S(controlSpeed))
    endif

    if MV_tick == 100 then
        if MV_baselineSamples < 10 or GetUnitMoveSpeed(MV_heroTarget) < 300.0 or GetUnitMoveSpeed(MV_creepTarget) < 300.0 or GetUnitMoveSpeed(MV_control) < 300.0 then
            call MV_Log("MV_SETUP_FAIL reason=baseline_speed_or_samples hero=" + R2S(GetUnitMoveSpeed(MV_heroTarget)) + " creep=" + R2S(GetUnitMoveSpeed(MV_creepTarget)) + " control=" + R2S(GetUnitMoveSpeed(MV_control)) + " samples=" + I2S(MV_baselineSamples))
        endif
        call MV_Log("MV_BASELINE samples=" + I2S(MV_baselineSamples) + " hero=" + R2S(GetUnitMoveSpeed(MV_heroTarget)) + " creep=" + R2S(GetUnitMoveSpeed(MV_creepTarget)) + " control=" + R2S(GetUnitMoveSpeed(MV_control)))
        set MV_heroAccepted = IssueTargetOrder(MV_heroCaster, "shadowstrike", MV_heroTarget)
        call MV_Log("MV_CAST_ORDER ability=AEsh accepted=" + I2S(MV_B2I(MV_heroAccepted)))
        if not MV_heroAccepted then
            call MV_Log("MV_SETUP_FAIL reason=AEsh_order_rejected")
        endif
    endif

    if MV_tick == 130 then
        set MV_creepAccepted = IssueTargetOrder(MV_creepCaster, "shadowstrike", MV_creepTarget)
        call MV_Log("MV_CAST_ORDER ability=ACss accepted=" + I2S(MV_B2I(MV_creepAccepted)))
        if not MV_creepAccepted then
            call MV_Log("MV_SETUP_FAIL reason=ACss_order_rejected")
        endif
    endif

    if MV_tick >= 700 then
        if MV_heroCastSeen != 1 or MV_creepCastSeen != 1 then
            call MV_Log("MV_SETUP_FAIL reason=spell_effect_missing")
        endif
        call MV_Log("MV_DONE accepted=AEsh:" + I2S(MV_B2I(MV_heroAccepted)) + " ACss:" + I2S(MV_B2I(MV_creepAccepted)) + " effect=AEsh:" + I2S(MV_heroCastSeen) + " ACss:" + I2S(MV_creepCastSeen) + " baselineSamples=" + I2S(MV_baselineSamples))
        call PreloadGenEnd("shadow-strike-movement-curve-run2.txt")
        call PauseTimer(MV_timer)
        call DestroyTimer(MV_timer)
        set MV_timer = null
    endif
endfunction

function MV_Start takes nothing returns nothing
    local real x = GetStartLocationX(0) + 1800.0
    local real y = GetStartLocationY(0) + 600.0
    set MV_tick = 0
    set MV_heroCastTick = -1
    set MV_creepCastTick = -1
    set MV_heroCastSeen = 0
    set MV_creepCastSeen = 0
    set MV_baselineSamples = 0
    set MV_x = R2I(x + 200.0)
    set MV_y = R2I(y)
    call PreloadGenClear()
    call PreloadGenStart()
    call MV_Log("MV_META build=1.29.2.9231 tickSeconds=0.05 durationTicks=700 sampleEveryTicks=5 target=hfoo requestedSpeed=400 baselineTicks=100 AEshCastTick=100 ACssCastTick=130")

    set MV_heroCaster = CreateUnit(Player(0), 'Ewar', x, y, 0.0)
    set MV_creepCaster = CreateUnit(Player(0), 'Ewar', x, y + 300.0, 0.0)
    set MV_heroTarget = CreateUnit(Player(12), 'hfoo', x + 200.0, y, 180.0)
    set MV_creepTarget = CreateUnit(Player(12), 'hfoo', x + 200.0, y + 300.0, 180.0)
    set MV_control = CreateUnit(Player(12), 'hfoo', x + 200.0, y + 600.0, 180.0)
    call UnitAddAbility(MV_heroCaster, 'AEsh')
    call SetUnitAbilityLevel(MV_heroCaster, 'AEsh', 1)
    call UnitAddAbility(MV_creepCaster, 'ACss')
    call SetUnitAbilityLevel(MV_creepCaster, 'ACss', 1)
    call SetUnitState(MV_heroCaster, UNIT_STATE_MANA, 1000.0)
    call SetUnitState(MV_creepCaster, UNIT_STATE_MANA, 1000.0)
    call SetUnitMoveSpeed(MV_heroTarget, 400.0)
    call SetUnitMoveSpeed(MV_creepTarget, 400.0)
    call SetUnitMoveSpeed(MV_control, 400.0)
    call BlzSetUnitMaxHP(MV_heroTarget, 100000)
    call BlzSetUnitMaxHP(MV_creepTarget, 100000)
    call BlzSetUnitMaxHP(MV_control, 100000)
    call SetWidgetLife(MV_heroTarget, 100000.0)
    call SetWidgetLife(MV_creepTarget, 100000.0)
    call SetWidgetLife(MV_control, 100000.0)

    set MV_heroCasterId = GetHandleId(MV_heroCaster)
    set MV_creepCasterId = GetHandleId(MV_creepCaster)
    set MV_heroTargetId = GetHandleId(MV_heroTarget)
    set MV_creepTargetId = GetHandleId(MV_creepTarget)
    set MV_controlId = GetHandleId(MV_control)
    set MV_spellTrigger = CreateTrigger()
    call TriggerRegisterUnitEvent(MV_spellTrigger, MV_heroCaster, EVENT_UNIT_SPELL_EFFECT)
    call TriggerRegisterUnitEvent(MV_spellTrigger, MV_creepCaster, EVENT_UNIT_SPELL_EFFECT)
    call TriggerAddAction(MV_spellTrigger, function MV_SpellEffect)
    call MV_Log("MV_SETUP IDs=" + I2S(MV_heroTargetId) + "/" + I2S(MV_creepTargetId) + "/" + I2S(MV_controlId) + " speeds=" + R2S(GetUnitMoveSpeed(MV_heroTarget)) + "/" + R2S(GetUnitMoveSpeed(MV_creepTarget)) + "/" + R2S(GetUnitMoveSpeed(MV_control)) + " abilities=" + I2S(GetUnitAbilityLevel(MV_heroCaster, 'AEsh')) + "/" + I2S(GetUnitAbilityLevel(MV_creepCaster, 'ACss')))
    set MV_timer = CreateTimer()
    call TimerStart(MV_timer, 0.05, true, function MV_Tick)
    set x = 0.0
    set y = 0.0
endfunction

function MV_Reload takes nothing returns nothing
    call ExecuteFunc("JHCR_Init_parse")
    call MV_Log("MV_JHCR_STATUS=" + I2S(JHCR_API_GetLastStatus()))
endfunction

function MV_Init takes nothing returns nothing
    if MV_reloadTrigger == null then
        set MV_reloadTrigger = CreateTrigger()
        call TriggerRegisterPlayerChatEvent(MV_reloadTrigger, Player(0), "-jhcr", true)
        call TriggerAddAction(MV_reloadTrigger, function MV_Reload)
    endif
    call MV_Start()
endfunction

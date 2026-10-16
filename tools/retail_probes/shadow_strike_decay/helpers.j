function SD_B2I takes boolean value returns integer
    if value then
        return 1
    endif
    return 0
endfunction

function SD_Log takes string value returns nothing
    call BJDebugMsg(value)
    call Preload(value)
endfunction

function SD_DestroyRun takes nothing returns nothing
    if SD_timer != null then
        call PauseTimer(SD_timer)
        call DestroyTimer(SD_timer)
        set SD_timer = null
    endif
    if SD_damageTrigger != null then
        call DestroyTrigger(SD_damageTrigger)
        set SD_damageTrigger = null
    endif
    if SD_spellTrigger != null then
        call DestroyTrigger(SD_spellTrigger)
        set SD_spellTrigger = null
    endif
    if SD_caster != null then
        call RemoveUnit(SD_caster)
        call RemoveUnit(SD_treated)
        call RemoveUnit(SD_control)
        call RemoveUnit(SD_treatedDummy)
        call RemoveUnit(SD_controlDummy)
    endif
    set SD_caster = null
    set SD_treated = null
    set SD_control = null
    set SD_treatedDummy = null
    set SD_controlDummy = null
endfunction

function SD_Damaged takes nothing returns nothing
    local unit damaged = GetTriggerUnit()
    local unit source = GetEventDamageSource()
    local integer sourceId = GetHandleId(source)
    local integer targetId = GetHandleId(damaged)
    local integer interval = 0
    local integer age = -1

    if targetId == SD_treatedDummyId and sourceId == SD_treatedId then
        set SD_treatedHits = SD_treatedHits + 1
        if SD_lastTreated >= 0 then
            set interval = SD_tick - SD_lastTreated
        endif
        if SD_castTick >= 0 then
            set age = SD_tick - SD_castTick
        endif
        if SD_castTick < 0 then
            if interval > 0 then
                set SD_baseSum = SD_baseSum + interval
                set SD_baseCount = SD_baseCount + 1
            endif
            call SD_Log("SD_HIT lane=A phase=baseline tick=" + I2S(SD_tick) + " intervalTicks=" + I2S(interval) + " hit=" + I2S(SD_treatedHits))
        else
            call SD_Log("SD_HIT lane=A phase=treated tick=" + I2S(SD_tick) + " ageTicks=" + I2S(age) + " intervalTicks=" + I2S(interval) + " baselineTicks=" + I2S(SD_baseSum / IMaxBJ(1, SD_baseCount)) + " intervalRatio=" + R2S(I2R(interval) / I2R(IMaxBJ(1, SD_baseSum / IMaxBJ(1, SD_baseCount)))) + " hit=" + I2S(SD_treatedHits))
        endif
        set SD_lastTreated = SD_tick
    elseif targetId == SD_controlDummyId and sourceId == SD_controlId then
        set SD_controlHits = SD_controlHits + 1
        if SD_lastControl >= 0 then
            set interval = SD_tick - SD_lastControl
        endif
        call SD_Log("SD_HIT lane=B phase=control tick=" + I2S(SD_tick) + " intervalTicks=" + I2S(interval) + " hit=" + I2S(SD_controlHits))
        set SD_lastControl = SD_tick
    endif

    set damaged = null
    set source = null
endfunction

function SD_SpellEffect takes nothing returns nothing
    if GetSpellAbilityId() == 'ACss' and GetSpellTargetUnit() == SD_treated then
        set SD_castSeen = true
        set SD_castTick = SD_tick
        call SD_Log("SD_CAST_EFFECT tick=" + I2S(SD_tick) + " targetId=" + I2S(SD_treatedId))
    endif
endfunction

function SD_Tick takes nothing returns nothing
    set SD_tick = SD_tick + 1

    // Keep campaign AI from changing the tested range; log actual positions.
    call SetUnitX(SD_treated, SD_x)
    call SetUnitY(SD_treated, SD_y)
    call SetUnitX(SD_control, SD_x)
    call SetUnitY(SD_control, SD_y + 300.0)

    if ModuloInteger(SD_tick, 20) == 0 then
        call SD_Log("SD_SAMPLE tick=" + I2S(SD_tick) + " treatedXY=" + R2S(GetUnitX(SD_treated)) + "," + R2S(GetUnitY(SD_treated)) + " controlXY=" + R2S(GetUnitX(SD_control)) + "," + R2S(GetUnitY(SD_control)) + " cooldown=" + R2S(BlzGetUnitAttackCooldown(SD_treated, 0)) + "/" + R2S(BlzGetUnitAttackCooldown(SD_control, 0)) + " hits=" + I2S(SD_treatedHits) + "/" + I2S(SD_controlHits))
    endif

    if SD_tick == 240 then
        if SD_baseCount < 4 then
            call SD_Log("SD_SETUP_FAIL reason=insufficient_baseline_hits count=" + I2S(SD_baseCount))
        endif
        call SD_Log("SD_BASELINE meanTicks=" + I2S(SD_baseSum / IMaxBJ(1, SD_baseCount)) + " intervals=" + I2S(SD_baseCount))
        call SD_Log("SD_CAST_BEGIN tick=" + I2S(SD_tick))
        set SD_orderAccepted = IssueTargetOrder(SD_caster, "shadowstrike", SD_treated)
        call SD_Log("SD_CAST_ORDER accepted=" + I2S(SD_B2I(SD_orderAccepted)))
    endif

    if SD_tick >= 1200 then
        call PauseUnit(SD_treated, true)
        call PauseUnit(SD_control, true)
        call SD_Log("SD_DONE run=" + I2S(SD_run) + " accepted=" + I2S(SD_B2I(SD_orderAccepted)) + " castSeen=" + I2S(SD_B2I(SD_castSeen)) + " hits=" + I2S(SD_treatedHits) + "/" + I2S(SD_controlHits) + " baseMeanTicks=" + I2S(SD_baseSum / IMaxBJ(1, SD_baseCount)))
        call PreloadGenEnd("shadow-strike-decay-curve-2.txt")
        call SD_DestroyRun()
    endif
endfunction

function SD_Start takes nothing returns nothing
    call SD_DestroyRun()
    set SD_run = SD_run + 1
    set SD_tick = 0
    set SD_castTick = -1
    set SD_treatedHits = 0
    set SD_controlHits = 0
    set SD_lastTreated = -1
    set SD_lastControl = -1
    set SD_baseSum = 0
    set SD_baseCount = 0
    set SD_orderAccepted = false
    set SD_castSeen = false
    set SD_x = GetStartLocationX(0) + 1800.0
    set SD_y = GetStartLocationY(0) + 600.0

    call PreloadGenClear()
    call PreloadGenStart()
    call SD_Log("SD_META exactBuild=1.29.2.9231 ability=ACss durationTicks=1200 tickSeconds=0.05 weaponUnit=hfoo authoredCooldown=1.35 run=" + I2S(SD_run))

    set SD_caster = CreateUnit(Player(0), 'Ewar', SD_x, SD_y + 600.0, 270.0)
    call UnitAddAbility(SD_caster, 'ACss')
    call SetUnitAbilityLevel(SD_caster, 'ACss', 1)
    set SD_treated = CreateUnit(Player(1), 'hfoo', SD_x, SD_y, 0.0)
    set SD_control = CreateUnit(Player(1), 'hfoo', SD_x, SD_y + 300.0, 0.0)
    set SD_treatedDummy = CreateUnit(Player(12), 'hfoo', SD_x + 100.0, SD_y, 180.0)
    set SD_controlDummy = CreateUnit(Player(12), 'hfoo', SD_x + 100.0, SD_y + 300.0, 180.0)

    call SetUnitX(SD_treated, SD_x)
    call SetUnitY(SD_treated, SD_y)
    call SetUnitX(SD_control, SD_x)
    call SetUnitY(SD_control, SD_y + 300.0)
    call SetUnitAcquireRange(SD_treated, 0.0)
    call SetUnitAcquireRange(SD_control, 0.0)
    call SetUnitMoveSpeed(SD_treated, 0.0)
    call SetUnitMoveSpeed(SD_control, 0.0)
    call BlzSetUnitMaxHP(SD_treatedDummy, 100000)
    call BlzSetUnitMaxHP(SD_controlDummy, 100000)
    call SetUnitState(SD_treatedDummy, UNIT_STATE_LIFE, 100000.0)
    call SetUnitState(SD_controlDummy, UNIT_STATE_LIFE, 100000.0)
    call PauseUnit(SD_treatedDummy, true)
    call PauseUnit(SD_controlDummy, true)

    set SD_treatedId = GetHandleId(SD_treated)
    set SD_controlId = GetHandleId(SD_control)
    set SD_treatedDummyId = GetHandleId(SD_treatedDummy)
    set SD_controlDummyId = GetHandleId(SD_controlDummy)
    set SD_damageTrigger = CreateTrigger()
    call TriggerRegisterUnitEvent(SD_damageTrigger, SD_treatedDummy, EVENT_UNIT_DAMAGED)
    call TriggerRegisterUnitEvent(SD_damageTrigger, SD_controlDummy, EVENT_UNIT_DAMAGED)
    call TriggerAddAction(SD_damageTrigger, function SD_Damaged)
    set SD_spellTrigger = CreateTrigger()
    call TriggerRegisterUnitEvent(SD_spellTrigger, SD_caster, EVENT_UNIT_SPELL_EFFECT)
    call TriggerAddAction(SD_spellTrigger, function SD_SpellEffect)

    call SD_Log("SD_SETUP sourceIds=" + I2S(SD_treatedId) + "/" + I2S(SD_controlId) + " dummyIds=" + I2S(SD_treatedDummyId) + "/" + I2S(SD_controlDummyId) + " attackRange=100 authoredCooldown=1.35 abilityLevel=" + I2S(GetUnitAbilityLevel(SD_caster, 'ACss')))

    call SD_Log("SD_ATTACK_ORDERS accepted=" + I2S(SD_B2I(IssueTargetOrder(SD_treated, "attack", SD_treatedDummy))) + "/" + I2S(SD_B2I(IssueTargetOrder(SD_control, "attack", SD_controlDummy))))
    call SD_Log("SD_MOTION_CONTROL positionLock=0.05s speed=" + R2S(GetUnitMoveSpeed(SD_treated)) + "/" + R2S(GetUnitMoveSpeed(SD_control)))
    set SD_timer = CreateTimer()
    call TimerStart(SD_timer, 0.05, true, function SD_Tick)
endfunction

function SD_Reload takes nothing returns nothing
    call ExecuteFunc("JHCR_Init_parse")
    call SD_Log("SD_JHCR_STATUS=" + I2S(JHCR_API_GetLastStatus()))
endfunction

function SD_Init takes nothing returns nothing
    if SD_runTrigger == null then
        set SD_runTrigger = CreateTrigger()
        call TriggerRegisterPlayerChatEvent(SD_runTrigger, Player(0), "-sd", true)
        call TriggerAddAction(SD_runTrigger, function SD_Start)
    endif
    if SD_reloadTrigger == null then
        set SD_reloadTrigger = CreateTrigger()
        call TriggerRegisterPlayerChatEvent(SD_reloadTrigger, Player(0), "-jhcr", true)
        call TriggerAddAction(SD_reloadTrigger, function SD_Reload)
    endif
    call SD_Start()
endfunction

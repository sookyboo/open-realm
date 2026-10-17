function AX_Log takes string value returns nothing
    call BJDebugMsg(value)
    call Preload(value)
endfunction

function AX_B2I takes boolean value returns integer
    if value then
        return 1
    endif
    return 0
endfunction

function AX_Damaged takes nothing returns nothing
    local unit target = GetTriggerUnit()
    local unit source = GetEventDamageSource()
    local integer sourceId = GetHandleId(source)
    local integer targetId = GetHandleId(target)
    local integer interval = 0
    local integer baseline = 0
    local integer startAge = -1
    local real damage = GetEventDamage()

    if targetId == AX_treatedId and sourceId == AX_casterId then
        if damage == 10.0 then
            set AX_poisonCount = AX_poisonCount + 1
            call AX_Log("AX_POISON tick=" + I2S(AX_tick) + " age=" + I2S(AX_tick - AX_castTick) + " damage=" + R2S(damage) + " count=" + I2S(AX_poisonCount))
        else
            call AX_Log("AX_CAST_DAMAGE tick=" + I2S(AX_tick) + " age=" + I2S(AX_tick - AX_castTick) + " damage=" + R2S(damage))
        endif
    elseif targetId == AX_treatedDummyId and sourceId == AX_treatedId then
        set AX_treatedHitCount = AX_treatedHitCount + 1
        if AX_lastTreatedHit >= 0 then
            set interval = AX_tick - AX_lastTreatedHit
        endif
        if AX_castTick < 0 then
            if interval > 0 then
                set AX_baseSum = AX_baseSum + interval
                set AX_baseCount = AX_baseCount + 1
            endif
            call AX_Log("AX_HIT lane=treated phase=baseline tick=" + I2S(AX_tick) + " interval=" + I2S(interval) + " count=" + I2S(AX_treatedHitCount))
        else
            set baseline = AX_baseSum / IMaxBJ(1, AX_baseCount)
            set startAge = AX_lastTreatedHit - AX_castTick
            if interval <= baseline + 1 then
                set AX_recoveryIntervals = AX_recoveryIntervals + 1
            else
                set AX_recoveryIntervals = 0
            endif
            call AX_Log("AX_HIT lane=treated phase=post tick=" + I2S(AX_tick) + " startAge=" + I2S(startAge) + " endAge=" + I2S(AX_tick - AX_castTick) + " interval=" + I2S(interval) + " baseline=" + I2S(baseline) + " baselineStreak=" + I2S(AX_recoveryIntervals) + " count=" + I2S(AX_treatedHitCount))
        endif
        set AX_lastTreatedHit = AX_tick
    elseif targetId == AX_controlDummyId and sourceId == AX_controlId then
        set AX_controlHitCount = AX_controlHitCount + 1
        if AX_lastControlHit >= 0 then
            set interval = AX_tick - AX_lastControlHit
        endif
        call AX_Log("AX_HIT lane=control tick=" + I2S(AX_tick) + " interval=" + I2S(interval) + " count=" + I2S(AX_controlHitCount))
        set AX_lastControlHit = AX_tick
    endif

    set target = null
    set source = null
endfunction

function AX_SpellEffect takes nothing returns nothing
    if GetTriggerUnit() == AX_caster and GetSpellAbilityId() == 'ACss' and GetSpellTargetUnit() == AX_treated then
        set AX_castSeen = true
        set AX_castTick = AX_tick
        call AX_Log("AX_CAST_EFFECT tick=" + I2S(AX_tick) + " targetId=" + I2S(AX_treatedId))
    endif
endfunction

function AX_Tick takes nothing returns nothing
    local real treatedSpeed
    local real controlSpeed
    set AX_tick = AX_tick + 1

    call SetUnitX(AX_treated, AX_x)
    call SetUnitY(AX_treated, AX_y)
    call SetUnitX(AX_control, AX_x)
    call SetUnitY(AX_control, AX_y + 300.0)
    call SetUnitX(AX_treatedDummy, AX_x + 400.0)
    call SetUnitY(AX_treatedDummy, AX_y)
    call SetUnitX(AX_controlDummy, AX_x + 400.0)
    call SetUnitY(AX_controlDummy, AX_y + 300.0)

    if ModuloInteger(AX_tick, 5) == 0 then
        set treatedSpeed = GetUnitMoveSpeed(AX_treated)
        set controlSpeed = GetUnitMoveSpeed(AX_control)
        if AX_castTick >= 0 and treatedSpeed < 399.999 then
            set AX_slowSampled = true
        endif
        if AX_slowSampled and treatedSpeed >= 399.999 and AX_lastSpeedSample == 0 then
            set AX_lastSpeedSample = AX_tick
        endif
        call AX_Log("AX_SPEED tick=" + I2S(AX_tick) + " treatedAge=" + I2S(AX_tick - AX_castTick) + " treated=" + R2S(treatedSpeed) + " control=" + R2S(controlSpeed))
    endif

    if AX_tick == 300 then
        if AX_baseCount < 3 or AX_treatedHitCount < 4 or AX_controlHitCount < 4 then
            call AX_Log("AX_SETUP_FAIL reason=baseline_hits treatedIntervals=" + I2S(AX_baseCount) + " treatedHits=" + I2S(AX_treatedHitCount) + " controlHits=" + I2S(AX_controlHitCount))
        endif
        call AX_Log("AX_BASELINE treatedMeanTicks=" + I2S(AX_baseSum / IMaxBJ(1, AX_baseCount)) + " treatedIntervals=" + I2S(AX_baseCount) + " controlHits=" + I2S(AX_controlHitCount))
        set AX_orderAccepted = IssueTargetOrder(AX_caster, "shadowstrike", AX_treated)
        call AX_Log("AX_CAST_ORDER accepted=" + I2S(AX_B2I(AX_orderAccepted)))
        if not AX_orderAccepted then
            call AX_Log("AX_SETUP_FAIL reason=cast_order_rejected")
        endif
    endif

    if AX_tick >= 1000 then
        if not AX_castSeen then
            call AX_Log("AX_SETUP_FAIL reason=spell_effect_missing")
        endif
        call AX_Log("AX_DONE castSeen=" + I2S(AX_B2I(AX_castSeen)) + " accepted=" + I2S(AX_B2I(AX_orderAccepted)) + " poisonCount=" + I2S(AX_poisonCount) + " treatedHits=" + I2S(AX_treatedHitCount) + " controlHits=" + I2S(AX_controlHitCount) + " baselineTicks=" + I2S(AX_baseSum / IMaxBJ(1, AX_baseCount)) + " recoveryStreak=" + I2S(AX_recoveryIntervals) + " speedRecoveryTick=" + I2S(AX_lastSpeedSample))
        call PreloadGenEnd("shadow-strike-acss-expiry.txt")
        call PauseTimer(AX_timer)
        call DestroyTimer(AX_timer)
        set AX_timer = null
    endif
endfunction

function AX_Start takes nothing returns nothing
    local real x = GetStartLocationX(0) + 1800.0
    local real y = GetStartLocationY(0) + 600.0
    set AX_tick = 0
    set AX_castTick = -1
    set AX_casterId = 0
    set AX_treatedHitCount = 0
    set AX_controlHitCount = 0
    set AX_poisonCount = 0
    set AX_lastTreatedHit = -1
    set AX_lastControlHit = -1
    set AX_baseSum = 0
    set AX_baseCount = 0
    set AX_recoveryIntervals = 0
    set AX_lastSpeedSample = 0
    set AX_orderAccepted = false
    set AX_castSeen = false
    set AX_slowSampled = false
    set AX_x = x + 200.0
    set AX_y = y

    call FogEnable(false)
    call FogMaskEnable(false)
    call PreloadGenClear()
    call PreloadGenStart()
    call AX_Log("AX_META build=1.29.2.9231 ability=ACss durationTicks=1000 tickSeconds=0.05 sampleEveryTicks=5 castTick=300 weaponUnit=hmtm targetRange=400")

    set AX_caster = CreateUnit(Player(0), 'Ewar', x + 200.0, y + 500.0, 270.0)
    set AX_treated = CreateUnit(Player(1), 'hmtm', AX_x, AX_y, 0.0)
    set AX_control = CreateUnit(Player(1), 'hmtm', AX_x, AX_y + 300.0, 0.0)
    set AX_treatedDummy = CreateUnit(Player(12), 'hfoo', AX_x + 400.0, AX_y, 180.0)
    set AX_controlDummy = CreateUnit(Player(12), 'hfoo', AX_x + 400.0, AX_y + 300.0, 180.0)
    call UnitAddAbility(AX_caster, 'ACss')
    call SetUnitAbilityLevel(AX_caster, 'ACss', 1)
    call SetUnitState(AX_caster, UNIT_STATE_MANA, 1000.0)

    call SetUnitAcquireRange(AX_caster, 0.0)
    call SetUnitMoveSpeed(AX_treated, 400.0)
    call SetUnitMoveSpeed(AX_control, 400.0)
    call BlzSetUnitMaxHP(AX_treatedDummy, 100000)
    call BlzSetUnitMaxHP(AX_controlDummy, 100000)
    call SetUnitState(AX_treatedDummy, UNIT_STATE_LIFE, 100000.0)
    call SetUnitState(AX_controlDummy, UNIT_STATE_LIFE, 100000.0)
    call PauseUnit(AX_treatedDummy, true)
    call PauseUnit(AX_controlDummy, true)

    set AX_casterId = GetHandleId(AX_caster)
    set AX_treatedId = GetHandleId(AX_treated)
    set AX_controlId = GetHandleId(AX_control)
    set AX_treatedDummyId = GetHandleId(AX_treatedDummy)
    set AX_controlDummyId = GetHandleId(AX_controlDummy)
    set AX_damageTrigger = CreateTrigger()
    call TriggerRegisterUnitEvent(AX_damageTrigger, AX_treated, EVENT_UNIT_DAMAGED)
    call TriggerRegisterUnitEvent(AX_damageTrigger, AX_treatedDummy, EVENT_UNIT_DAMAGED)
    call TriggerRegisterUnitEvent(AX_damageTrigger, AX_controlDummy, EVENT_UNIT_DAMAGED)
    call TriggerAddAction(AX_damageTrigger, function AX_Damaged)
    set AX_spellTrigger = CreateTrigger()
    call TriggerRegisterUnitEvent(AX_spellTrigger, AX_caster, EVENT_UNIT_SPELL_EFFECT)
    call TriggerAddAction(AX_spellTrigger, function AX_SpellEffect)

    call AX_Log("AX_SETUP IDs=" + I2S(AX_casterId) + "/" + I2S(AX_treatedId) + "/" + I2S(AX_controlId) + "/" + I2S(AX_treatedDummyId) + "/" + I2S(AX_controlDummyId) + " speeds=" + R2S(GetUnitMoveSpeed(AX_treated)) + "/" + R2S(GetUnitMoveSpeed(AX_control)) + " abilityLevel=" + I2S(GetUnitAbilityLevel(AX_caster, 'ACss')))
    if AX_casterId == 0 or AX_treatedId == 0 or AX_controlId == 0 or AX_treatedDummyId == 0 or AX_controlDummyId == 0 then
        call AX_Log("AX_SETUP_FAIL reason=invalid_entity")
    endif
    call AX_Log("AX_ATTACK_ORDERS treated=" + I2S(AX_B2I(IssueTargetOrder(AX_treated, "attack", AX_treatedDummy))) + " control=" + I2S(AX_B2I(IssueTargetOrder(AX_control, "attack", AX_controlDummy))))
    set AX_timer = CreateTimer()
    call TimerStart(AX_timer, 0.05, true, function AX_Tick)
    set x = 0.0
    set y = 0.0
endfunction

function AX_Reload takes nothing returns nothing
    call ExecuteFunc("JHCR_Init_parse")
    call AX_Log("AX_JHCR_STATUS=" + I2S(JHCR_API_GetLastStatus()))
endfunction

function AX_Init takes nothing returns nothing
    if AX_reloadTrigger == null then
        set AX_reloadTrigger = CreateTrigger()
        call TriggerRegisterPlayerChatEvent(AX_reloadTrigger, Player(0), "-jhcr", true)
        call TriggerAddAction(AX_reloadTrigger, function AX_Reload)
    endif
    call AX_Start()
endfunction

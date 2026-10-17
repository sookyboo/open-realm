function PG_B2I takes boolean value returns integer
    if value then
        return 1
    endif
    return 0
endfunction

function PG_Log takes string value returns nothing
    call BJDebugMsg(value)
    call Preload(value)
    if SubString(value, 0, 7) == "PG_META" then
        call Preload("PG_LOG_REV2")
    endif
endfunction

function PG_SpellEffect takes nothing returns nothing
    local unit caster = GetTriggerUnit()
    local unit target = GetSpellTargetUnit()
    if GetHandleId(caster) == PG_casterId and GetSpellAbilityId() == 'Apg2' and GetHandleId(target) == PG_targetId then
        set PG_effectSeen = 1
        set PG_effectTick = PG_tick
        call PG_Log("PG_CAST_EFFECT tick=" + I2S(PG_tick) + " target=" + I2S(PG_targetId))
    endif
    set caster = null
    set target = null
endfunction

function PG_Tick takes nothing returns nothing
    local real targetSpeed
    local real controlSpeed
    local real targetX
    local real targetY
    set PG_tick = PG_tick + 1

    // Prevent campaign orders/AI from moving the test units or changing range.
    call SetUnitX(PG_target, I2R(PG_x))
    call SetUnitY(PG_target, I2R(PG_y))
    call SetUnitX(PG_control, I2R(PG_x))
    call SetUnitY(PG_control, I2R(PG_y + 300))

    if ModuloInteger(PG_tick, PG_sampleEvery) == 0 then
        set targetSpeed = GetUnitMoveSpeed(PG_target)
        set controlSpeed = GetUnitMoveSpeed(PG_control)
        set targetX = GetUnitX(PG_target)
        set targetY = GetUnitY(PG_target)
        if PG_tick < PG_castTick then
            set PG_baseSamples = PG_baseSamples + 1
        endif
        if PG_effectTick < 0 then
            call PG_Log("PG_SAMPLE tick=" + I2S(PG_tick) + " age=-1 targetSpeed=" + R2S(targetSpeed) + " controlSpeed=" + R2S(controlSpeed) + " targetXY=" + R2S(targetX) + "," + R2S(targetY))
        else
            call PG_Log("PG_SAMPLE tick=" + I2S(PG_tick) + " age=" + I2S(PG_tick - PG_effectTick) + " targetSpeed=" + R2S(targetSpeed) + " controlSpeed=" + R2S(controlSpeed) + " targetXY=" + R2S(targetX) + "," + R2S(targetY))
        endif
    endif

    if PG_tick == PG_castTick then
        call PG_Log("PG_BASELINE samples=" + I2S(PG_baseSamples) + " targetSpeed=" + R2S(GetUnitMoveSpeed(PG_target)) + " controlSpeed=" + R2S(GetUnitMoveSpeed(PG_control)))
        set PG_accepted = PG_B2I(IssueTargetOrder(PG_caster, "purge", PG_target))
        call PG_Log("PG_CAST_ORDER accepted=" + I2S(PG_accepted) + " caster=" + I2S(PG_casterId) + " target=" + I2S(PG_targetId))
        if PG_accepted == 0 then
            call PG_Log("PG_SETUP_FAIL reason=purge_order_rejected")
        endif
    endif

    if PG_tick >= PG_endTick then
        if PG_baseSamples < 10 or PG_effectSeen != 1 or PG_accepted != 1 then
            call PG_Log("PG_SETUP_FAIL reason=missing_baseline_order_or_effect baseline=" + I2S(PG_baseSamples) + " accepted=" + I2S(PG_accepted) + " effect=" + I2S(PG_effectSeen))
        endif
        call PG_Log("PG_DONE accepted=" + I2S(PG_accepted) + " effect=" + I2S(PG_effectSeen) + " effectTick=" + I2S(PG_effectTick) + " baselineSamples=" + I2S(PG_baseSamples) + " endTick=" + I2S(PG_tick))
        call PreloadGenEnd("purge-timing-run1.txt")
        call PauseTimer(PG_timer)
        call DestroyTimer(PG_timer)
        set PG_timer = null
    endif
endfunction

function PG_Start takes nothing returns nothing
    local real x = GetStartLocationX(0) + 1800.0
    local real y = GetStartLocationY(0) + 600.0
    if PG_timer != null then
        call PauseTimer(PG_timer)
        call DestroyTimer(PG_timer)
        set PG_timer = null
    endif
    if PG_spellTrigger != null then
        call DestroyTrigger(PG_spellTrigger)
        set PG_spellTrigger = null
    endif
    if PG_caster != null then
        call RemoveUnit(PG_caster)
        set PG_caster = null
    endif
    if PG_target != null then
        call RemoveUnit(PG_target)
        set PG_target = null
    endif
    if PG_control != null then
        call RemoveUnit(PG_control)
        set PG_control = null
    endif
    set PG_runId = PG_runId + 1
    set PG_tick = 0
    set PG_effectTick = -1
    set PG_effectSeen = 0
    set PG_accepted = 0
    set PG_baseSamples = 0
    set PG_x = R2I(x + 250.0)
    set PG_y = R2I(y)
    call PreloadGenClear()
    call PreloadGenStart()
    call PG_Log("PG_META run=" + I2S(PG_runId) + " build=1.29.2.9231 ability=Apg2 intervalSeconds=0.05 sampleEveryTicks=2 baselineTicks=40 castTick=40 endTick=440 target=hfoo requestedSpeed=300")

    set PG_caster = CreateUnit(Player(0), 'Hblm', x, y, 0.0)
    set PG_target = CreateUnit(Player(12), 'hfoo', x + 250.0, y, 180.0)
    set PG_control = CreateUnit(Player(12), 'hfoo', x + 250.0, y + 300.0, 180.0)
    call UnitAddAbility(PG_caster, 'Apg2')
    call SetUnitAbilityLevel(PG_caster, 'Apg2', 1)
    call SetUnitState(PG_caster, UNIT_STATE_MANA, 1000.0)
    call SetUnitMoveSpeed(PG_target, 300.0)
    call SetUnitMoveSpeed(PG_control, 300.0)
    call BlzSetUnitMaxHP(PG_target, 100000)
    call BlzSetUnitMaxHP(PG_control, 100000)
    call SetWidgetLife(PG_target, 100000.0)
    call SetWidgetLife(PG_control, 100000.0)
    set PG_casterId = GetHandleId(PG_caster)
    set PG_targetId = GetHandleId(PG_target)
    set PG_controlId = GetHandleId(PG_control)
    set PG_spellTrigger = CreateTrigger()
    call TriggerRegisterUnitEvent(PG_spellTrigger, PG_caster, EVENT_UNIT_SPELL_EFFECT)
    call TriggerAddAction(PG_spellTrigger, function PG_SpellEffect)
    call PG_Log("PG_SETUP caster=" + I2S(PG_casterId) + " target=" + I2S(PG_targetId) + " control=" + I2S(PG_controlId) + " abilityLevel=" + I2S(GetUnitAbilityLevel(PG_caster, 'Apg2')) + " speeds=" + R2S(GetUnitMoveSpeed(PG_target)) + "/" + R2S(GetUnitMoveSpeed(PG_control)) + " targetXY=" + R2S(GetUnitX(PG_target)) + "," + R2S(GetUnitY(PG_target)))
    set PG_timer = CreateTimer()
    call TimerStart(PG_timer, 0.05, true, function PG_Tick)
    set x = 0.0
    set y = 0.0
endfunction

function PG_Reload takes nothing returns nothing
    call ExecuteFunc("JHCR_Init_parse")
    call PG_Start()
    call PG_Log("PG_JHCR_STATUS=" + I2S(JHCR_API_GetLastStatus()))
endfunction

function PG_Rerun takes nothing returns nothing
    call PG_Start()
endfunction

function PG_Init takes nothing returns nothing
    call PG_Start()
    if PG_reloadTrigger == null then
        set PG_reloadTrigger = CreateTrigger()
        call TriggerRegisterPlayerChatEvent(PG_reloadTrigger, Player(0), "-jhcr", true)
        call TriggerAddAction(PG_reloadTrigger, function PG_Reload)
    endif
    if PG_runTrigger == null then
        set PG_runTrigger = CreateTrigger()
        call TriggerRegisterPlayerChatEvent(PG_runTrigger, Player(0), "-probe", true)
        call TriggerAddAction(PG_runTrigger, function PG_Rerun)
    endif
endfunction

// General starter only: replace GP IDs, units, ability and hypothesis-specific
// phases. Copy globals.j and this file into the probe's manifest edits.

function GP_Log takes string message returns nothing
    call BJDebugMsg("GP run=" + I2S(GP_runId) + " " + message)
    call Preload("GP run=" + I2S(GP_runId) + " " + message)
endfunction

function GP_Damaged takes nothing returns nothing
    local unit eventTarget = GetTriggerUnit()
    local unit eventSource = GetEventDamageSource()
    local integer targetId = GetHandleId(eventTarget)
    local integer sourceId = GetHandleId(eventSource)
    local real elapsed = 0.0
    local string phase = "control_or_ambient"

    if GP_runClock != null then
        set elapsed = TimerGetElapsed(GP_runClock)
    endif
    if targetId == GP_targetHandleId and sourceId == GP_sourceHandleId then
        if GP_measuring then
            set GP_observedEvents = GP_observedEvents + 1
            set phase = "treatment"
        else
            set GP_controlEvents = GP_controlEvents + 1
            set phase = "control"
        endif
        call GP_Log("EVENT phase=" + phase + " seconds=" + R2S(elapsed) + " damage=" + R2S(GetEventDamage()) + " sourceId=" + I2S(sourceId) + " targetId=" + I2S(targetId) + " sourceType=" + I2S(GetUnitTypeId(eventSource)) + " targetType=" + I2S(GetUnitTypeId(eventTarget)))
    endif

    set eventTarget = null
    set eventSource = null
endfunction

function GP_Sample takes nothing returns nothing
    local real sourceX = GetUnitX(GP_source)
    local real sourceY = GetUnitY(GP_source)
    local real targetX = GP_originX + GP_targetOffsetX
    local real targetY = GP_originY + GP_targetOffsetY

    set GP_sample = GP_sample + 1

    // Re-assert coordinates because map AI/order logic can move test units.
    call SetUnitX(GP_source, GP_originX)
    call SetUnitY(GP_source, GP_originY)
    call SetUnitX(GP_target, targetX)
    call SetUnitY(GP_target, targetY)

    if ModuloInteger(GP_sample, 20) == 0 then
        call GP_Log("SAMPLE phase=" + I2S(GP_measurePhase) + " seconds=" + R2S(TimerGetElapsed(GP_runClock)) + " sourceX=" + R2S(sourceX) + " sourceY=" + R2S(sourceY) + " targetX=" + R2S(GetUnitX(GP_target)) + " targetY=" + R2S(GetUnitY(GP_target)) + " distance=" + R2S(SquareRoot((GetUnitX(GP_target) - GetUnitX(GP_source)) * (GetUnitX(GP_target) - GetUnitX(GP_source)) + (GetUnitY(GP_target) - GetUnitY(GP_source)) * (GetUnitY(GP_target) - GetUnitY(GP_source)))) + " events=" + I2S(GP_observedEvents))
    endif

    // TODO: replace with a hypothesis-specific stop condition or phase schedule.
    if GP_sample >= 600 then
        call GP_Finish()
    endif
endfunction

function GP_Cleanup takes nothing returns nothing
    if GP_sampleTimer != null then
        call PauseTimer(GP_sampleTimer)
        call DestroyTimer(GP_sampleTimer)
        set GP_sampleTimer = null
    endif
    if GP_runClock != null then
        call PauseTimer(GP_runClock)
        call DestroyTimer(GP_runClock)
        set GP_runClock = null
    endif
    if GP_damageTrigger != null then
        call DestroyTrigger(GP_damageTrigger)
        set GP_damageTrigger = null
    endif
    if GP_source != null then
        call RemoveUnit(GP_source)
        set GP_source = null
    endif
    if GP_target != null then
        call RemoveUnit(GP_target)
        set GP_target = null
    endif
endfunction

function GP_Finish takes nothing returns nothing
    if GP_sampleTimer == null or GP_sample == 0 then
        return
    endif
    call GP_Log("RESULT controlEvents=" + I2S(GP_controlEvents) + " treatmentEvents=" + I2S(GP_observedEvents))
    call GP_Log("DONE status=complete")
    call PreloadGenEnd("ability-probe-template.txt")
    call GP_Cleanup()
endfunction

function GP_Start takes nothing returns nothing
    local real lifeBefore = 0.0

    // The chat trigger persists, while per-run handles and state are replaced.
    if GP_sampleTimer != null then
        call GP_Log("CANCELLED reason=rerun_before_completion")
        call GP_Log("DONE status=cancelled")
        call PreloadGenEnd("ability-probe-template.txt")
    endif
    call GP_Cleanup()
    set GP_runId = GP_runId + 1
    set GP_sample = 0
    set GP_observedEvents = 0
    set GP_controlEvents = 0
    set GP_measuring = false
    set GP_measurePhase = 0
    set GP_originX = 13000.0
    set GP_originY = 13000.0
    set GP_targetOffsetX = 300.0
    set GP_targetOffsetY = 0.0

    call FogEnable(false)
    call FogMaskEnable(false)
    call PreloadGenClear()
    call PreloadGenStart()
    call GP_Log("META build=REPLACE ability=REPLACE rawcode=REPLACE scenario=REPLACE")
    call GP_Log("START")

    // TODO: choose suitable unit types/owners, configure the actual ability,
    // and verify all authored preconditions for the investigation.
    set GP_source = CreateUnit(Player(0), 'hfoo', GP_originX, GP_originY, 0.0)
    set GP_target = CreateUnit(Player(1), 'hfoo', GP_originX + GP_targetOffsetX, GP_originY, 180.0)
    call SetUnitX(GP_source, GP_originX)
    call SetUnitY(GP_source, GP_originY)
    call SetUnitX(GP_target, GP_originX + GP_targetOffsetX)
    call SetUnitY(GP_target, GP_originY + GP_targetOffsetY)
    call SetUnitAcquireRange(GP_source, 0.0)
    call SetUnitAcquireRange(GP_target, 0.0)
    call SetUnitMoveSpeed(GP_source, 0.0)
    call SetUnitMoveSpeed(GP_target, 0.0)
    call BlzSetUnitMaxHP(GP_target, 100000)
    call SetUnitState(GP_target, UNIT_STATE_LIFE, 100000.0)

    set GP_sourceHandleId = GetHandleId(GP_source)
    set GP_targetHandleId = GetHandleId(GP_target)
    set GP_damageTrigger = CreateTrigger()
    call TriggerRegisterUnitEvent(GP_damageTrigger, GP_target, EVENT_UNIT_DAMAGED)
    call TriggerAddAction(GP_damageTrigger, function GP_Damaged)

    call GP_Log("SETUP sourceId=" + I2S(GP_sourceHandleId) + " targetId=" + I2S(GP_targetHandleId) + " sourceType=" + I2S(GetUnitTypeId(GP_source)) + " targetType=" + I2S(GetUnitTypeId(GP_target)) + " distance=" + R2S(GP_targetOffsetX))
    if GP_sourceHandleId == 0 or GP_targetHandleId == 0 or GetUnitTypeId(GP_source) == 0 or GetUnitTypeId(GP_target) == 0 then
        call GP_Log("SETUP_FAIL reason=invalid_entity")
        call GP_Log("DONE status=setup_fail")
        call PreloadGenEnd("ability-probe-template.txt")
        call GP_Cleanup()
        return
    endif

    // Positive control: ensure the exact target/source event filter works.
    call GP_Log("CONTROL_BEGIN")
    set lifeBefore = GetWidgetLife(GP_target)
    call UnitDamageTarget(GP_source, GP_target, 1.0, true, false, ATTACK_TYPE_NORMAL, DAMAGE_TYPE_NORMAL, WEAPON_TYPE_WHOKNOWS)
    call GP_Log("CONTROL_END lifeBefore=" + R2S(lifeBefore) + " lifeAfter=" + R2S(GetWidgetLife(GP_target)) + " controlEvents=" + I2S(GP_controlEvents))
    if GP_controlEvents == 0 then
        call GP_Log("SETUP_FAIL reason=positive_control_not_observed")
        call GP_Log("DONE status=setup_fail")
        call PreloadGenEnd("ability-probe-template.txt")
        call GP_Cleanup()
        return
    endif

    // Restore the observed state after the control, then begin measurement.
    call SetUnitState(GP_target, UNIT_STATE_LIFE, 100000.0)
    set GP_controlEvents = 0
    set GP_runClock = CreateTimer()
    call TimerStart(GP_runClock, 1000.0, false, null)
    set GP_sampleTimer = CreateTimer()
    set GP_measuring = true
    set GP_measurePhase = 1
    call GP_Log("MEASURE_BEGIN")
    call TimerStart(GP_sampleTimer, 0.05, true, function GP_Sample)
endfunction

function GP_Init takes nothing returns nothing
    if GP_rerunTrigger == null then
        set GP_rerunTrigger = CreateTrigger()
        call TriggerRegisterPlayerChatEvent(GP_rerunTrigger, Player(0), "-probe", true)
        call TriggerAddAction(GP_rerunTrigger, function GP_Start)
    endif
    call GP_Start()
endfunction

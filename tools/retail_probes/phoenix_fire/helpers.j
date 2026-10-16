function PF_Log takes string value returns nothing
    call BJDebugMsg(value)
    call Preload(value)
endfunction

function PF_Damaged takes nothing returns nothing
    local unit target = GetTriggerUnit()
    local unit source = GetEventDamageSource()
    local integer sourceId = GetHandleId(source)
    local integer matched = 0
    local real elapsed = 0.0

    if PF_clock != null then
        set elapsed = TimerGetElapsed(PF_clock)
    endif

    if target == PF_target then
        if sourceId == PF_source_handle_id then
            set matched = 1
            set PF_source_hits = PF_source_hits + 1
        endif
        call PF_Log("PF_EVENT seconds=" + R2S(elapsed) + " damage=" + R2S(GetEventDamage()) + " sourceType=" + I2S(GetUnitTypeId(source)) + " sourceHandle=" + I2S(sourceId) + " phoenixHandle=" + I2S(PF_source_handle_id) + " sourceMatch=" + I2S(matched))
    endif

    set target = null
    set source = null
endfunction

function PF_Tick takes nothing returns nothing
    local real distance = 650.0
    set PF_tick = PF_tick + 1

    if PF_tick >= 200 and PF_tick < 400 then
        set distance = 550.0
    elseif PF_tick >= 400 then
        set distance = 300.0
    endif

    // Reposition frequently: the campaign AI can move an unpaused test target.
    call SetUnitX(PF_target, PF_x + distance)
    call SetUnitY(PF_target, PF_y)

    if ModuloInteger(PF_tick, 20) == 0 then
        call PF_Log("PF_SAMPLE seconds=" + R2S(TimerGetElapsed(PF_clock)) + " distance=" + R2S(GetUnitX(PF_target) - GetUnitX(PF_phoenix)) + " life=" + R2S(GetWidgetLife(PF_target)) + " sourceHits=" + I2S(PF_source_hits))
    endif

    if PF_tick == 200 then
        call PF_Log("PF_PHASE distance=550")
    elseif PF_tick == 400 then
        call PF_Log("PF_PHASE distance=300")
    elseif PF_tick >= 600 then
        call PF_Log("PF_DONE sourceHits=" + I2S(PF_source_hits) + " life=" + R2S(GetWidgetLife(PF_target)))
        call PreloadGenEnd("phoenix-fire-radius-cadence.txt")
        call PauseTimer(PF_sample_timer)
        call DestroyTimer(PF_sample_timer)
        set PF_sample_timer = null
    endif
endfunction

function PF_Start takes nothing returns nothing
    if PF_rerun_trigger == null then
        set PF_rerun_trigger = CreateTrigger()
        call TriggerRegisterPlayerChatEvent(PF_rerun_trigger, Player(0), "-pf", true)
        call TriggerAddAction(PF_rerun_trigger, function PF_Start)
    endif

    if PF_sample_timer != null then
        call PauseTimer(PF_sample_timer)
        call DestroyTimer(PF_sample_timer)
        set PF_sample_timer = null
    endif
    if PF_clock != null then
        call DestroyTimer(PF_clock)
        set PF_clock = null
    endif
    if PF_damage_trigger != null then
        call DestroyTrigger(PF_damage_trigger)
        set PF_damage_trigger = null
    endif
    if PF_phoenix != null then
        call RemoveUnit(PF_phoenix)
        call RemoveUnit(PF_target)
    endif

    set PF_tick = 0
    set PF_source_hits = 0
    set PF_x = 13000.0
    set PF_y = 13000.0

    call FogEnable(false)
    call FogMaskEnable(false)
    call SetPlayerAlliance(Player(0), Player(1), ALLIANCE_PASSIVE, false)
    call SetPlayerAlliance(Player(1), Player(0), ALLIANCE_PASSIVE, false)
    call PreloadGenClear()
    call PreloadGenStart()
    call PF_Log("PF_META build=1.29.2.9231 ability=Apxf distances=650-then-550-then-300 duration=30s sample=0.05s")

    set PF_phoenix = CreateUnit(Player(0), 'hphx', PF_x, PF_y, 0.0)
    set PF_target = CreateUnit(Player(1), 'hfoo', PF_x + 650.0, PF_y, 180.0)
    call SetUnitX(PF_phoenix, PF_x)
    call SetUnitY(PF_phoenix, PF_y)
    call SetUnitX(PF_target, PF_x + 650.0)
    call SetUnitY(PF_target, PF_y)
    call BlzSetUnitMaxHP(PF_target, 100000)
    call SetUnitState(PF_target, UNIT_STATE_LIFE, 100000.0)
    call SetUnitAcquireRange(PF_target, 0.0)
    call SetUnitMoveSpeed(PF_target, 0.0)
    call BlzSetUnitBaseDamage(PF_target, 0, 0)
    call SetUnitAcquireRange(PF_phoenix, 0.0)
    call SetUnitMoveSpeed(PF_phoenix, 0.0)
    call BlzSetUnitBaseDamage(PF_phoenix, 0, 0)

    set PF_source_handle_id = GetHandleId(PF_phoenix)
    set PF_damage_trigger = CreateTrigger()
    call TriggerRegisterUnitEvent(PF_damage_trigger, PF_target, EVENT_UNIT_DAMAGED)
    call TriggerAddAction(PF_damage_trigger, function PF_Damaged)
    call PF_Log("PF_SETUP ability=" + I2S(GetUnitAbilityLevel(PF_phoenix, 'Apxf')) + " phoenixHandle=" + I2S(PF_source_handle_id) + " targetX=" + R2S(GetUnitX(PF_target)) + " phoenixX=" + R2S(GetUnitX(PF_phoenix)))

    // Positive control: prove the damage trigger sees the exact source handle.
    call PF_Log("PF_CONTROL_BEGIN")
    call UnitDamageTarget(PF_phoenix, PF_target, 1.0, true, false, ATTACK_TYPE_NORMAL, DAMAGE_TYPE_NORMAL, WEAPON_TYPE_WHOKNOWS)
    call PF_Log("PF_CONTROL_END")
    call SetUnitState(PF_target, UNIT_STATE_LIFE, 100000.0)
    set PF_source_hits = 0

    set PF_clock = CreateTimer()
    call TimerStart(PF_clock, 1000.0, false, null)
    set PF_sample_timer = CreateTimer()
    call TimerStart(PF_sample_timer, 0.05, true, function PF_Tick)
endfunction

function PF_Log takes string value returns nothing
    call BJDebugMsg(value)
    call Preload(value)
endfunction

function PF_Damaged takes nothing returns nothing
    local unit target = GetTriggerUnit()
    local unit source = GetEventDamageSource()
    local integer interval
    if source == PF_phoenix300 and target == PF_target300 then
        set PF_hits300 = PF_hits300 + 1
        set interval = 0
        if PF_last300 >= 0 then
            set interval = PF_tick - PF_last300
        endif
        set PF_last300 = PF_tick
        call PF_Log("PF_HIT lane=300 tick=" + I2S(PF_tick) + " interval=" + I2S(interval) + " damage=" + R2S(GetEventDamage()))
    elseif source == PF_phoenix550 and target == PF_target550 then
        set PF_hits550 = PF_hits550 + 1
        set interval = 0
        if PF_last550 >= 0 then
            set interval = PF_tick - PF_last550
        endif
        set PF_last550 = PF_tick
        call PF_Log("PF_HIT lane=550 tick=" + I2S(PF_tick) + " interval=" + I2S(interval) + " damage=" + R2S(GetEventDamage()))
    elseif source == PF_phoenix650 and target == PF_target650 then
        set PF_hits650 = PF_hits650 + 1
        set interval = 0
        if PF_last650 >= 0 then
            set interval = PF_tick - PF_last650
        endif
        set PF_last650 = PF_tick
        call PF_Log("PF_HIT lane=650 tick=" + I2S(PF_tick) + " interval=" + I2S(interval) + " damage=" + R2S(GetEventDamage()))
    endif
    set target = null
    set source = null
endfunction

function PF_Tick takes nothing returns nothing
    set PF_tick = PF_tick + 1
    if PF_tick == 300 then
        call PF_Log("PF_DONE hits=" + I2S(PF_hits300) + "/" + I2S(PF_hits550) + "/" + I2S(PF_hits650) + " life=" + R2S(GetWidgetLife(PF_target300)) + "/" + R2S(GetWidgetLife(PF_target550)) + "/" + R2S(GetWidgetLife(PF_target650)))
        call PreloadGenEnd("phoenix-fire-radius-cadence.txt")
        call PauseTimer(PF_timer)
        call DestroyTimer(PF_timer)
        set PF_timer = null
    endif
endfunction

function PF_Start takes nothing returns nothing
    local integer i = 0
    set PF_x = GetStartLocationX(0) + 1800.0
    set PF_y = GetStartLocationY(0) + 700.0
    call PreloadGenClear()
    call PreloadGenStart()
    call PF_Log("PF_META build=1.29.2.9231 ability=Apxf unit=hphx lanes=300,550,650 duration=30s sample=0.1s")

    set PF_phoenix300 = CreateUnit(Player(0), 'hphx', PF_x, PF_y, 0.0)
    set PF_phoenix550 = CreateUnit(Player(0), 'hphx', PF_x, PF_y + 900.0, 0.0)
    set PF_phoenix650 = CreateUnit(Player(0), 'hphx', PF_x, PF_y + 1800.0, 0.0)
    set PF_target300 = CreateUnit(Player(12), 'hfoo', PF_x + 300.0, PF_y, 180.0)
    set PF_target550 = CreateUnit(Player(12), 'hfoo', PF_x + 550.0, PF_y + 900.0, 180.0)
    set PF_target650 = CreateUnit(Player(12), 'hfoo', PF_x + 650.0, PF_y + 1800.0, 180.0)

    set i = 0
    loop
        exitwhen i >= 3
        if i == 0 then
            call BlzSetUnitMaxHP(PF_target300, 100000)
            call SetWidgetLife(PF_target300, 100000.0)
            call PauseUnit(PF_target300, true)
        elseif i == 1 then
            call BlzSetUnitMaxHP(PF_target550, 100000)
            call SetWidgetLife(PF_target550, 100000.0)
            call PauseUnit(PF_target550, true)
        else
            call BlzSetUnitMaxHP(PF_target650, 100000)
            call SetWidgetLife(PF_target650, 100000.0)
            call PauseUnit(PF_target650, true)
        endif
        set i = i + 1
    endloop

    call SetUnitAcquireRange(PF_phoenix300, 0.0)
    call SetUnitAcquireRange(PF_phoenix550, 0.0)
    call SetUnitAcquireRange(PF_phoenix650, 0.0)
    call BlzSetUnitBaseDamage(PF_phoenix300, 0, 0)
    call BlzSetUnitBaseDamage(PF_phoenix550, 0, 0)
    call BlzSetUnitBaseDamage(PF_phoenix650, 0, 0)
    call IssueImmediateOrder(PF_phoenix300, "holdposition")
    call IssueImmediateOrder(PF_phoenix550, "holdposition")
    call IssueImmediateOrder(PF_phoenix650, "holdposition")

    set PF_damage_trigger = CreateTrigger()
    call TriggerRegisterUnitEvent(PF_damage_trigger, PF_target300, EVENT_UNIT_DAMAGED)
    call TriggerRegisterUnitEvent(PF_damage_trigger, PF_target550, EVENT_UNIT_DAMAGED)
    call TriggerRegisterUnitEvent(PF_damage_trigger, PF_target650, EVENT_UNIT_DAMAGED)
    call TriggerAddAction(PF_damage_trigger, function PF_Damaged)

    set PF_timer = CreateTimer()
    call TimerStart(PF_timer, 0.1, true, function PF_Tick)
    call PF_Log("PF_SETUP acquire=" + R2S(GetUnitAcquireRange(PF_phoenix300)) + "/" + R2S(GetUnitAcquireRange(PF_phoenix550)) + "/" + R2S(GetUnitAcquireRange(PF_phoenix650)))
endfunction

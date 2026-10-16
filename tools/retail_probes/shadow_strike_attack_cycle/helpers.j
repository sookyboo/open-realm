function SS_B2I takes boolean value returns integer
    if value then
        return 1
    endif
    return 0
endfunction

function SS_Log takes string value returns nothing
    call BJDebugMsg(value)
    call Preload(value)
endfunction

function SS_Damaged takes nothing returns nothing
    local unit damaged = GetTriggerUnit()
    local unit source = GetEventDamageSource()
    local integer tick
    set tick = SS_tick
    if source == SS_target and damaged == SS_target_dummy then
        set SS_target_hits = SS_target_hits + 1
        if SS_last_target >= 0 then
            call SS_Log("SS_HIT lane=A tick=" + I2S(tick) + " intervalTicks=" + I2S(tick - SS_last_target) + " hit=" + I2S(SS_target_hits))
        else
            call SS_Log("SS_HIT lane=A tick=" + I2S(tick) + " intervalTicks=0 hit=1")
        endif
        set SS_last_target = tick
    elseif source == SS_control and damaged == SS_control_dummy then
        set SS_control_hits = SS_control_hits + 1
        if SS_last_control >= 0 then
            call SS_Log("SS_HIT lane=B tick=" + I2S(tick) + " intervalTicks=" + I2S(tick - SS_last_control) + " hit=" + I2S(SS_control_hits))
        else
            call SS_Log("SS_HIT lane=B tick=" + I2S(tick) + " intervalTicks=0 hit=1")
        endif
        set SS_last_control = tick
    endif
    set damaged = null
    set source = null
endfunction

function SS_SpellEffect takes nothing returns nothing
    if GetSpellAbilityId() == 'ACss' and GetSpellTargetUnit() == SS_target then
        set SS_cast_effect = true
        call SS_Log("SS_CAST_EFFECT tick=" + I2S(SS_tick) + " target=A")
    endif
endfunction

function SS_Tick takes nothing returns nothing
    set SS_tick = SS_tick + 1
    if ModuloInteger(SS_tick, 50) == 0 then
        call SS_Log("SS_SAMPLE tick=" + I2S(SS_tick) + " pos=" + R2S(GetUnitX(SS_target)) + "," + R2S(GetUnitY(SS_target)) + "/" + R2S(GetUnitX(SS_control)) + "," + R2S(GetUnitY(SS_control)) + " life=" + R2S(GetWidgetLife(SS_target)) + "/" + R2S(GetWidgetLife(SS_control)) + " dummy=" + R2S(GetWidgetLife(SS_target_dummy)) + "/" + R2S(GetWidgetLife(SS_control_dummy)))
    endif
    if SS_tick == 80 then
        call SS_Log("SS_CAST_BEGIN tick=" + I2S(SS_tick) + " hits=" + I2S(SS_target_hits) + "/" + I2S(SS_control_hits))
        set SS_cast_order = IssueTargetOrder(SS_caster, "shadowstrike", SS_target)
        call SS_Log("SS_CAST_ORDER accepted=" + I2S(SS_B2I(SS_cast_order)))
    endif
    if SS_tick == 550 then
        call PauseUnit(SS_target, true)
        call PauseUnit(SS_control, true)
        call SS_Log("SS_DONE castOrder=" + I2S(SS_B2I(SS_cast_order)) + " castEffect=" + I2S(SS_B2I(SS_cast_effect)) + " hits=" + I2S(SS_target_hits) + "/" + I2S(SS_control_hits))
        call PreloadGenEnd("@RESULT_FILE@")
        call PauseTimer(SS_timer)
        call DestroyTimer(SS_timer)
        set SS_timer = null
    endif
endfunction

function SS_Start takes nothing returns nothing
    set SS_x = GetStartLocationX(0) + 1800.0
    set SS_y = GetStartLocationY(0) + 700.0
    call PreloadGenClear()
    call PreloadGenStart()
    call SS_Log("SS_META exact-build=1292 scenario=ACss-stock-player1-dual-control interval=0.1s baseline=8s total=55s")
    set SS_caster = CreateUnit(Player(0), 'Ewar', SS_x, SS_y + 500.0, 270.0)
    call UnitAddAbility(SS_caster, 'ACss')
    call SetUnitAbilityLevel(SS_caster, 'ACss', 1)
    set SS_target = CreateUnit(Player(1), 'hmtm', SS_x, SS_y, 0.0)
    set SS_control = CreateUnit(Player(1), 'hmtm', SS_x, SS_y + 300.0, 0.0)
    set SS_target_dummy = CreateUnit(Player(12), 'hfoo', SS_x + 400.0, SS_y, 180.0)
    set SS_control_dummy = CreateUnit(Player(12), 'hfoo', SS_x + 400.0, SS_y + 300.0, 180.0)
    call BlzSetUnitMaxHP(SS_target, 100000)
    call BlzSetUnitMaxHP(SS_control, 100000)
    call SetUnitState(SS_target, UNIT_STATE_LIFE, 100000.0)
    call SetUnitState(SS_control, UNIT_STATE_LIFE, 100000.0)
    call BlzSetUnitMaxHP(SS_target_dummy, 100000)
    call BlzSetUnitMaxHP(SS_control_dummy, 100000)
    call SetUnitState(SS_target_dummy, UNIT_STATE_LIFE, 100000.0)
    call SetUnitState(SS_control_dummy, UNIT_STATE_LIFE, 100000.0)
    call PauseUnit(SS_target_dummy, true)
    call PauseUnit(SS_control_dummy, true)
    call SetUnitMoveSpeed(SS_target, 0.0)
    call SetUnitMoveSpeed(SS_control, 0.0)
    set SS_damage_trigger = CreateTrigger()
    call TriggerRegisterUnitEvent(SS_damage_trigger, SS_target_dummy, EVENT_UNIT_DAMAGED)
    call TriggerRegisterUnitEvent(SS_damage_trigger, SS_control_dummy, EVENT_UNIT_DAMAGED)
    call TriggerAddAction(SS_damage_trigger, function SS_Damaged)
    set SS_spell_trigger = CreateTrigger()
    call TriggerRegisterUnitEvent(SS_spell_trigger, SS_caster, EVENT_UNIT_SPELL_EFFECT)
    call TriggerAddAction(SS_spell_trigger, function SS_SpellEffect)
    call SS_Log("SS_BASE attack-orders=" + I2S(SS_B2I(IssueTargetOrder(SS_target, "attack", SS_target_dummy))) + "/" + I2S(SS_B2I(IssueTargetOrder(SS_control, "attack", SS_control_dummy))) + " speed=" + R2S(GetUnitMoveSpeed(SS_target)) + "/" + R2S(GetUnitMoveSpeed(SS_control)))
    set SS_timer = CreateTimer()
    call TimerStart(SS_timer, 0.1, true, function SS_Tick)
endfunction

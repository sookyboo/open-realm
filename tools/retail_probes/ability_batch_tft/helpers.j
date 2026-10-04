function AB_Log takes string value returns nothing
    call BJDebugMsg(value)
    call Preload(value)
endfunction

function B2I takes boolean value returns integer
    if value then
        return 1
    endif
    return 0
endfunction

function AB_Damaged takes nothing returns nothing
    local integer i = 0
    local unit damaged = GetTriggerUnit()
    loop
        exitwhen i >= AB_count
        if damaged == AB_units[i] then
            set AB_hits[i] = AB_hits[i] + 1
            set AB_damage[i] = AB_damage[i] + GetEventDamage()
        endif
        set i = i + 1
    endloop
    set damaged = null
endfunction

function AB_Watch takes unit u returns nothing
    set AB_units[AB_count] = u
    set AB_hits[AB_count] = 0
    set AB_damage[AB_count] = 0.0
    set AB_damageTriggers[AB_count] = CreateTrigger()
    call TriggerRegisterUnitEvent(AB_damageTriggers[AB_count], u, EVENT_UNIT_DAMAGED)
    call TriggerAddAction(AB_damageTriggers[AB_count], function AB_Damaged)
    set AB_count = AB_count + 1
endfunction

function AB_ClearCase takes nothing returns nothing
    local integer i = 0
    loop
        exitwhen i >= AB_count
        if AB_damageTriggers[i] != null then
            call DestroyTrigger(AB_damageTriggers[i])
            set AB_damageTriggers[i] = null
        endif
        if AB_units[i] != null then
            call RemoveUnit(AB_units[i])
            set AB_units[i] = null
        endif
        set i = i + 1
    endloop
    set AB_count = 0
    if AB_caster != null then
        call RemoveUnit(AB_caster)
        set AB_caster = null
    endif
endfunction

function AB_StartImmolation takes nothing returns nothing
    local boolean accepted
    call AB_ClearCase()
    set AB_phase = 1
    set AB_tick = 0
    set AB_caster = CreateUnit(Player(0), 'Edem', AB_x, AB_y, 0.0)
    call UnitAddAbility(AB_caster, 'AEim')
    call SetUnitAbilityLevel(AB_caster, 'AEim', 1)
    call SetUnitState(AB_caster, UNIT_STATE_MANA, 100.0)
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 80.0, AB_y, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hgry', AB_x + 100.0, AB_y + 40.0, 0.0))
    set accepted = IssueImmediateOrder(AB_caster, "immolation")
    call AB_Log("AB_IM_SETUP order=" + I2S(B2I(accepted)) + " ability=" + I2S(GetUnitAbilityLevel(AB_caster, 'AEim')))
endfunction

function AB_StartShadowStrike takes nothing returns nothing
    local boolean accepted
    call AB_ClearCase()
    set AB_phase = 2
    set AB_tick = 0
    set AB_caster = CreateUnit(Player(0), 'Ewar', AB_x, AB_y, 0.0)
    call UnitAddAbility(AB_caster, 'AEsh')
    call SetUnitAbilityLevel(AB_caster, 'AEsh', 1)
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 200.0, AB_y, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 200.0, AB_y + 140.0, 0.0))
    call SetUnitState(AB_units[0], UNIT_STATE_LIFE, 400.0)
    call IssuePointOrder(AB_units[0], "move", AB_x + 1000.0, AB_y)
    call IssuePointOrder(AB_units[1], "move", AB_x + 1000.0, AB_y + 140.0)
    set accepted = IssueTargetOrder(AB_caster, "shadowstrike", AB_units[0])
    call AB_Log("AB_SS_SETUP order=" + I2S(B2I(accepted)) + " ability=" + I2S(GetUnitAbilityLevel(AB_caster, 'AEsh')))
endfunction

function AB_StartEarthquake takes nothing returns nothing
    local boolean accepted
    call AB_ClearCase()
    set AB_phase = 3
    set AB_tick = 0
    set AB_caster = CreateUnit(Player(0), 'Ofar', AB_x, AB_y, 0.0)
    call UnitAddAbility(AB_caster, 'AOeq')
    call SetUnitAbilityLevel(AB_caster, 'AOeq', 1)
    call AB_Watch(CreateUnit(Player(12), 'hhou', AB_x + 280.0, AB_y + 60.0, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 230.0, AB_y + 80.0, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 230.0, AB_y + 300.0, 0.0))
    call IssuePointOrder(AB_units[1], "move", AB_x + 1000.0, AB_y + 80.0)
    call IssuePointOrder(AB_units[2], "move", AB_x + 1000.0, AB_y + 300.0)
    set accepted = IssuePointOrder(AB_caster, "earthquake", AB_x + 280.0, AB_y + 80.0)
    call AB_Log("AB_EQ_SETUP order=" + I2S(B2I(accepted)) + " ability=" + I2S(GetUnitAbilityLevel(AB_caster, 'AOeq')))
endfunction

function AB_StartClusterRockets takes nothing returns nothing
    local boolean accepted
    call AB_ClearCase()
    set AB_phase = 4
    set AB_tick = 0
    set AB_caster = CreateUnit(Player(0), 'Ntin', AB_x, AB_y, 0.0)
    call UnitAddAbility(AB_caster, 'ANcs')
    call SetUnitAbilityLevel(AB_caster, 'ANcs', 1)
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 280.0, AB_y + 20.0, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 340.0, AB_y + 40.0, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hgry', AB_x + 300.0, AB_y + 100.0, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hhou', AB_x + 400.0, AB_y + 80.0, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 400.0, AB_y + 300.0, 0.0))
    call IssuePointOrder(AB_units[0], "move", AB_x + 1000.0, AB_y + 20.0)
    call IssuePointOrder(AB_units[1], "move", AB_x + 1000.0, AB_y + 40.0)
    call IssuePointOrder(AB_units[4], "move", AB_x + 1000.0, AB_y + 300.0)
    set accepted = IssuePointOrder(AB_caster, "clusterrockets", AB_x + 320.0, AB_y + 60.0)
    call AB_Log("AB_CR_SETUP order=" + I2S(B2I(accepted)) + " ability=" + I2S(GetUnitAbilityLevel(AB_caster, 'ANcs')))
endfunction

function AB_StartCarrionSwarm takes nothing returns nothing
    local boolean accepted
    call AB_ClearCase()
    set AB_phase = 5
    set AB_tick = 0
    set AB_caster = CreateUnit(Player(0), 'Udre', AB_x, AB_y, 0.0)
    call UnitAddAbility(AB_caster, 'ACca')
    call SetUnitAbilityLevel(AB_caster, 'ACca', 1)
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 140.0, AB_y, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 250.0, AB_y, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 360.0, AB_y, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 470.0, AB_y, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 580.0, AB_y, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hfoo', AB_x + 690.0, AB_y, 0.0))
    call AB_Watch(CreateUnit(Player(12), 'hgry', AB_x + 360.0, AB_y + 220.0, 0.0))
    call AB_Watch(CreateUnit(Player(0), 'hfoo', AB_x + 360.0, AB_y - 180.0, 0.0))
    set accepted = IssuePointOrder(AB_caster, "carrionswarm", AB_x + 720.0, AB_y)
    call AB_Log("AB_CSW_SETUP order=" + I2S(B2I(accepted)) + " ability=" + I2S(GetUnitAbilityLevel(AB_caster, 'ACca')))
endfunction

function AB_ReportTick takes nothing returns nothing
    local string s
    if ModuloInteger(AB_tick, 2) == 0 then
        if AB_phase == 1 then
            set s = "AB_IM t=" + I2S(AB_tick / 2) + " mana=" + R2S(GetUnitState(AB_caster, UNIT_STATE_MANA)) + " ground=" + R2S(GetWidgetLife(AB_units[0])) + " air=" + R2S(GetWidgetLife(AB_units[1])) + " hits=" + I2S(AB_hits[0]) + "/" + I2S(AB_hits[1])
        elseif AB_phase == 2 then
            set s = "AB_SS t=" + I2S(AB_tick / 2) + " targetLife=" + R2S(GetWidgetLife(AB_units[0])) + " poisonHits=" + I2S(AB_hits[0]) + " poisonDmg=" + R2S(AB_damage[0]) + " targetX=" + R2S(GetUnitX(AB_units[0])) + " controlX=" + R2S(GetUnitX(AB_units[1]))
        elseif AB_phase == 3 then
            set s = "AB_EQ t=" + I2S(AB_tick / 2) + " building=" + R2S(GetWidgetLife(AB_units[0])) + " ground=" + R2S(GetWidgetLife(AB_units[1])) + " controlLife=" + R2S(GetWidgetLife(AB_units[2])) + " hits=" + I2S(AB_hits[0]) + "/" + I2S(AB_hits[1]) + " x=" + R2S(GetUnitX(AB_units[1])) + " controlX=" + R2S(GetUnitX(AB_units[2])) + " order=" + I2S(GetUnitCurrentOrder(AB_caster))
        elseif AB_phase == 4 then
            set s = "AB_CR t=" + I2S(AB_tick / 2) + " ground=" + R2S(GetWidgetLife(AB_units[0])) + "/" + R2S(GetWidgetLife(AB_units[1])) + " air=" + R2S(GetWidgetLife(AB_units[2])) + " building=" + R2S(GetWidgetLife(AB_units[3])) + " hits=" + I2S(AB_hits[0]) + "/" + I2S(AB_hits[1]) + "/" + I2S(AB_hits[2]) + "/" + I2S(AB_hits[3]) + " controlX=" + R2S(GetUnitX(AB_units[4]))
        elseif AB_phase == 5 then
            set s = "AB_CSW t=" + I2S(AB_tick / 2) + " hits=" + I2S(AB_hits[0]) + "/" + I2S(AB_hits[1]) + "/" + I2S(AB_hits[2]) + "/" + I2S(AB_hits[3]) + "/" + I2S(AB_hits[4]) + "/" + I2S(AB_hits[5]) + "/" + I2S(AB_hits[6]) + "/" + I2S(AB_hits[7]) + " dmg=" + R2S(AB_damage[0]) + "/" + R2S(AB_damage[1]) + "/" + R2S(AB_damage[2]) + "/" + R2S(AB_damage[3]) + "/" + R2S(AB_damage[4]) + "/" + R2S(AB_damage[5]) + "/" + R2S(AB_damage[6]) + "/" + R2S(AB_damage[7])
        endif
        call AB_Log(s)
    endif
endfunction

function AB_Tick takes nothing returns nothing
    set AB_tick = AB_tick + 1
    call AB_ReportTick()
    if AB_phase == 1 and AB_tick >= 10 then
        call IssueImmediateOrder(AB_caster, "unimmolation")
        call AB_Log("AB_IM_STOP mana=" + R2S(GetUnitState(AB_caster, UNIT_STATE_MANA)))
        call AB_StartShadowStrike()
    elseif AB_phase == 2 and AB_tick >= 32 then
        call AB_StartEarthquake()
    elseif AB_phase == 3 and AB_tick >= 10 then
        call IssueImmediateOrder(AB_caster, "stop")
        call AB_Log("AB_EQ_STOP order=" + I2S(GetUnitCurrentOrder(AB_caster)))
        call AB_StartClusterRockets()
    elseif AB_phase == 4 and AB_tick >= 6 then
        call AB_StartCarrionSwarm()
    elseif AB_phase == 5 and AB_tick >= 10 then
        call AB_Log("AB_DONE")
        call PreloadGenEnd("ability-batch-tft-v1.txt")
        call PauseTimer(AB_timer)
        call DestroyTimer(AB_timer)
        call AB_ClearCase()
        set AB_timer = null
    endif
endfunction

function AB_Start takes nothing returns nothing
    set AB_x = GetStartLocationX(0) + 1800.0
    set AB_y = GetStartLocationY(0) + 700.0
    call PreloadGenClear()
    call PreloadGenStart()
    call AB_Log("AB_META mode=TFT rawcodes=AEim,AEsh,AOeq,ANcs,ACca")
    call AB_StartImmolation()
    set AB_timer = CreateTimer()
    call TimerStart(AB_timer, 0.5, true, function AB_Tick)
endfunction

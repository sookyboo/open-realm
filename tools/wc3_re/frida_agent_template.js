/* Passive, bounded x86 function-entry instrumenter for a pinned Retail build.
 * Generated configuration below contains *candidate* Ghidra function starts.
 * No game memory is modified and no argument or receiver type is inferred.
 */
'use strict';
const PLAN = __WC3_RE_TRACE_CONFIGURATION__;
const moduleName = 'Warcraft III.exe';
const moduleInfo = Process.getModuleByName(moduleName);
if (Process.pointerSize !== 4 || Process.arch !== 'ia32') {
    throw new Error('Expected a 32-bit x86 Warcraft III process');
}
const totalLimit = PLAN.limits.max_events;
const perHookLimit = PLAN.limits.per_hook_events;
let armed = true;
let startedMs = Date.now();
let emitted = 0;
let stopped = false;
let runId = PLAN.capture_id;
const counts = {};
const exhaustedHooks = {};
let nextInvocationId = 0;
function report(kind, values) {
    send(Object.assign({source: 'wc3_ability_re_frida', kind: kind,
                        rawcode: PLAN.rawcode, capture_id: PLAN.capture_id,
                        run_id: runId}, values || {}));
}
function stop(reason) {
    if (stopped) return;
    stopped = true;
    armed = false;
    report(reason === 'event_limit' ? 'overflow' : 'stop',
           {reason: reason, emitted: emitted});
    // Once the finite budget ends, detach our own hooks instead of leaving
    // silent interceptors active for the rest of the game session.
    setImmediate(() => installed.forEach(listener => listener.detach()));
}
function allowed() {
    if (!armed || stopped) return false;
    if (Date.now() - startedMs >= PLAN.limits.seconds * 1000) {
        stop('duration_limit');
        return false;
    }
    if (emitted >= totalLimit) {
        stop('event_limit');
        return false;
    }
    return true;
}
function moduleRva(address) {
    if (!address) return null;
    const value = ptr(address);
    const offset = value.sub(moduleInfo.base).toUInt32();
    // unsigned native pointer values; avoid negative and out-of-module offsets.
    if (value.compare(moduleInfo.base) < 0 ||
        value.compare(moduleInfo.base.add(moduleInfo.size)) >= 0)
        return null;
    return '0x' + offset.toString(16).padStart(8, '0');
}
function emit(kind, context, fn, returnValue, invocationId) {
    if (!allowed()) return false;
    if ((counts[fn] || 0) >= perHookLimit) {
        if (!exhaustedHooks[fn]) {
            exhaustedHooks[fn] = true;
            report('hook_limit', {function_rva: fn, event_limit: perHookLimit});
        }
        return false;
    }
    counts[fn] = (counts[fn] || 0) + 1;
    emitted += 1;
    const regs = context.context;
    const event = {function_rva: fn, invocation_id: invocationId,
                   timestamp_wall_ms: Date.now(), thread_id: context.threadId,
                   call_depth: context.depth, ecx_raw: regs.ecx.toString(),
                   edx_raw: regs.edx.toString(), esp_raw: regs.esp.toString(),
                   eip_raw: regs.eip.toString(),
                   return_address_rva: moduleRva(context.returnAddress),
                   return_address_raw: context.returnAddress ? context.returnAddress.toString() : null};
    if (returnValue !== null) event.return_value_raw = returnValue.toString();
    if (kind === 'enter' && PLAN.limits.stack_words > 0) {
        // Optional *raw* stack words, not decoded ABI parameters.
        event.stack_raw = [];
        for (let i = 0; i < PLAN.limits.stack_words; i++) {
            try { event.stack_raw.push(regs.esp.add(i * 4).readPointer().toString()); }
            catch (e) { event.stack_raw.push(null); }
        }
    }
    report(kind, event);
    if (counts[fn] >= perHookLimit && !exhaustedHooks[fn]) {
        exhaustedHooks[fn] = true;
        report('hook_limit', {function_rva: fn, event_limit: perHookLimit});
    }
    if (emitted >= totalLimit) stop('event_limit');
    return true;
}
// Validate *all* planned hook addresses before attaching any of them.
const hooks = PLAN.hooks.map(hook => {
    const rva = parseInt(hook.rva.slice(2), 16);
    if (!Number.isSafeInteger(rva) || rva < 1 || rva >= moduleInfo.size)
        throw new Error('Invalid code RVA: ' + hook.rva);
    const address = moduleInfo.base.add(rva);
    const range = Process.findRangeByAddress(address);
    if (!range || range.protection.indexOf('x') < 0)
        throw new Error('Function not in executable memory: ' + hook.rva);
    return {rva: hook.rva, address: address};
});
const installed = [];
try {
    hooks.forEach(hook => {
        const listener = Interceptor.attach(hook.address, {
            onEnter(args) {
                this.entryRva = hook.rva;
                this.traceInvocationId = ++nextInvocationId;
                this.wasEmitted = emit('enter', this, hook.rva, null, this.traceInvocationId);
            },
            onLeave(retval) {
                if (this.wasEmitted) emit('leave', this, hook.rva, retval, this.traceInvocationId);
            }
        });
        installed.push(listener);
    });
} catch (e) {
    installed.forEach(listener => listener.detach());
    report('install_error', {reason: String(e)});
    throw e;
}
report('start', {hook_count: hooks.length, max_events: totalLimit,
                 seconds: PLAN.limits.seconds, active: armed});
rpc.exports = {
    arm() {
        if (stopped) return false;
        startedMs = Date.now();
        armed = true;
        return true;
    },
    disarm() { armed = false; return {emitted: emitted, counts: counts}; },
    setrunid(value) {
        if (!/^[A-Za-z0-9_.-]{1,80}$/.test(value)) throw new Error('invalid run id');
        runId = value;
        return true;
    },
    status() { return {armed: armed && !stopped, emitted: emitted,
                       counts: counts, run_id: runId, stopped: stopped}; }
};

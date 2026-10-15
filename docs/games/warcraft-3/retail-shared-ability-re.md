# Warcraft III Retail Reverse Engineering: Finding Shared Ability Functions

This guide describes a repeatable way to identify shared native functions behind
ability behavior in the Warcraft III Retail executable. Combine static call
graph work, short Frida traces, and controlled JASS experiments. The goal is a
verified behavioral contract, not just a renamed function or a list of callers.

The current investigation's exact-build findings are in
[ability-shared-native-functions.md](ability-shared-native-functions.md); the
ability-specific evidence and probes are in
[ability-verification-review.md](ability-verification-review.md). This guide
explains how to extend that work for attack hit dispatch, status expiry/removal,
target validation, and summon cleanup.

## Investigation model

Work in both directions and meet at candidate shared functions:

- **Top down:** start at a known JASS native, ability callback, or factory and
  follow calls, including indirect and virtual dispatch.
- **Bottom up:** start from an observable consequence such as life loss, status
  removal, rejected targeting, or summon disappearance, then trace its writer
  or callback path backward.

A JASS native may only enqueue an order or change state. The ability callback
may run later during a simulation update, after the native returns. Trace the
later update/dispatch callback as needed; the native's immediate descendants
may not include the gameplay operation.

Treat these as separate until evidence joins them: attack resolution, damage
application, and health mutation. Likewise, status creation, expiry, dispel,
and attached-object removal can be distinct paths that converge only at a
lower-level unlink or destruction helper.

## Exact-build address records

Pin every result to the executable being inspected. For the currently documented
Retail build, see the executable hash and PE32 details in
[ability-shared-native-functions.md](ability-shared-native-functions.md).
Re-derive addresses for any other build.

Record at least:

| Field | Why it matters |
|---|---|
| Executable SHA-256 and version | Prevents mixing evidence from different builds. |
| Architecture, module name, and runtime module base | Establishes pointer width, ABI, and ASLR conversion. |
| Function RVA and Ghidra address | Gives a stable identifier within the pinned executable and links runtime traces to static analysis. |
| Call-site RVA and caller identity | Distinguishes multiple routes into one helper, including virtual call sites. |
| Vtable RVA, slot offset, and resolved target RVA | Captures runtime virtual dispatch. |
| Scenario and rawcode | Ties observations to a controlled ability path. |
| Confidence and unresolved questions | Separates observed facts from inferred names and signatures. |

Use `RVA = runtime address - module base`. Store the runtime base for each
capture, and use the RVA as the cross-tool identifier for that exact build.
Maintain linked records for functions, call sites, and object/vtable
relationships rather than a flat list of provisional names.

## Resolve virtual dispatch

Static cross references do not reveal every virtual caller. For a call such as
`call dword ptr [vtable + slot]`:

1. Verify the exact instruction and register use in disassembly.
2. Capture the object pointer at the call site in Frida.
3. Read its vtable pointer and the function pointer at the slot.
4. Record the call-site, object, vtable, slot, and resolved target as RVAs.
5. Repeat with another ability in the same suspected family.
6. Follow the resolved target and compare its callees and state writes.

On PE32 x86, a byte offset of `0x30` is slot index 12 when entries are four
bytes. Confirm pointer width and table layout from the executable before using
that calculation. A resolved slot can point to a thunk; follow it to the
implementation.

| Observation | What it establishes |
|---|---|
| Same slot, different targets | A shared interface position, possibly with ability-specific behavior. |
| Different callbacks call the same function RVA | A strong shared-implementation candidate. |
| Different functions call the same lower-level helper | A shared mechanism behind specialized wrappers. |

Identical vtable layouts alone do not establish shared gameplay behavior.

## Static analysis workflow

Use Ghidra for function structure, data flow, and vtable modeling. Use radare2
for bounded disassembly and cross-reference queries. Existing commands and
build-specific examples are in
[ability-shared-native-functions.md](ability-shared-native-functions.md).

For each known wrapper or callback:

1. Identify handle-to-object conversion and argument setup.
2. Find calls into unit, ability, behavior, status, or effect objects.
3. Resolve the first meaningful indirect call instead of stopping at a
   decompiler placeholder.
4. Model relevant vtables and assign provisional signatures.
5. Inspect shared callees, their arguments, return paths, and state writes.
6. Check callers and negative paths before assigning gameplay semantics.

Names such as `ApplyDamageCandidate` or `onImpact` are hypotheses until callers,
arguments, and effects support them. Preserve raw addresses and evidence next to
provisional names.

## Targeted dynamic tracing

Start with short function-entry/exit hooks on known wrappers, callbacks, and
candidate helpers. Record the caller, thread, timestamp, registers, return
value, and relevant object/vtable pointers. Raw registers are not decoded
parameters: use the disassembly and ABI to interpret them. On 32-bit MSVC
`thiscall`, `ECX` commonly carries `this`; verify each function rather than
assuming it.

Example Frida skeleton (replace all values with verified values from the pinned
build):

```javascript
const moduleName = "Warcraft III.exe";
const game = Process.getModuleByName(moduleName);
const hooks = {
  wrapper: 0x00100000,       // example RVA only
  callback: 0x00200000,      // example RVA only
  candidate: 0x00300000      // example RVA only
};

let sequence = 0;
let events = 0;
const maxEvents = 300;

function location(address) {
  const module = Process.findModuleByAddress(address);
  return module ? `${module.name}+0x${address.sub(module.base).toString(16)}`
                : address.toString();
}

for (const [name, rva] of Object.entries(hooks)) {
  Interceptor.attach(game.base.add(rva), {
    onEnter() {
      this.logged = events++ < maxEvents;
      if (!this.logged) return;
      this.id = ++sequence;
      const registers = Process.arch === "ia32"
        ? { ecx: String(this.context.ecx), edx: String(this.context.edx),
            esp: String(this.context.esp) }
        : { rcx: String(this.context.rcx), rdx: String(this.context.rdx),
            r8: String(this.context.r8), r9: String(this.context.r9) };
      console.log(JSON.stringify({ event: "enter", id: this.id, name,
        rva: `0x${rva.toString(16)}`, caller: location(this.returnAddress),
        thread: this.threadId, time: Date.now(), registers }));
    },
    onLeave(retval) {
      if (!this.logged) return;
      console.log(JSON.stringify({ event: "leave", id: this.id, name,
        resultRaw: String(retval), time: Date.now() }));
    }
  });
}
```

To resolve a known indirect call, hook the instruction itself and read the
object's vtable slot only after confirming the register and instruction form.
Keep probes bounded. Use Frida Stalker only after entry hooks narrow the
callback and a short call trace is needed; full instruction tracing can be
expensive and can interact with Interceptor instrumentation.

Prefer these stages:

1. Hook known wrappers and callbacks.
2. Narrow candidate functions during a short simulation window.
3. Compare ordered call events across controlled abilities.
4. Use call summaries for frequency, not semantic conclusions.
5. Trace selected blocks or instructions to resolve one branch question.

If behavior occurs on a later tick, trace the corresponding update path or
capture from that callback. Do not assume returning from JASS means the
operation has completed.

## Controlled JASS experiments

Use JASS to trigger repeatable inputs and record externally visible outcomes.
Keep the original map unchanged, retain a control copy, and vary one property at
a time. Existing Retail map preparation and replay steps are in
[ability-verification-review.md](ability-verification-review.md).

| System | Comparisons | Evidence to collect |
|---|---|---|
| Attack hit dispatch | Melee hit, ranged projectile hit, miss/evasion, splash, and `UnitDamageTarget`. | Caller/callee sequences, attacker and target identity, damage amount/type, hit flags, and life changes. `UnitDamageTarget` exercises a damage receiver but does not prove ordinary attacks use the same path. |
| Status expiry/removal | Natural expiry, dispel, explicit removal, refresh, and unit death. | Status identity, duration, removal reason if present, callback order, and whether each path converges at the same removal helper. |
| Target validation | Valid enemy, ally, self, invalid type, magic immune, invulnerable, and a target that dies during cast. | Validation branches/results, order state, ability callback entry, and resulting effect. An issued-order event alone does not prove acceptance or execution. |
| Summon cleanup | Natural expiry, summon death, dispel, explicit `RemoveUnit`, and caster death. | Summon identity/owner, death events, cleanup callbacks, and whether expiry follows death handling or directly removes the entity. |

Use stock ability rows first. For field hypotheses, change one authored field at
a time and keep a stock-row control. Record both the trace and JASS-visible
state. A JASS experiment validates externally visible behavior; it does not by
itself name an internal function or establish its argument meanings.

### Attack and damage are separate paths

Compare ordinary melee, ordinary ranged impact, and explicit
`UnitDamageTarget`. A possible result is that melee and projectile callbacks
converge on helper B, while `UnitDamageTarget` enters at B and then shares
health-mutation helper C. This is only a pattern to test. Separately compare
spell damage and periodic effects before labeling B as a generic attack helper.

### Delayed lifecycle paths

For status expiry, identify where the status is created, how its duration is
stored, and which callback runs at expiry. Test expiry, dispel, refresh, and
unit destruction separately. For summons, compare expiry, death, dispel, and
explicit removal; ordinary `CreateUnit` may not establish the same summoned
lifecycle as an ability-specific constructor. JASS can observe death events,
while Frida can distinguish native cleanup paths.

## Infer arguments and validate sharing

Use differential runs to map arguments. Change one variable at a time: attacker,
target, damage amount, damage type, immunity, or ability. Correlate changed
registers and memory with known objects, constructor/destructor activity,
vtable pointers, and state writes. An address can be reused after object
destruction, so track object lifetime or generation where possible.

For bit fields, a test such as `test eax, 0x04` identifies a conditional bit,
not its semantic name. Confirm the bit with multiple controlled scenarios.

Classify candidate sharing by evidence:

| Confidence | Evidence |
|---|---|
| Candidate | Static similarity, shared vtable layout, or timing correlation only. |
| Likely shared helper | Independent callers converge at one RVA, but caller identity, arguments, or state effects remain partly unresolved. |
| Confirmed shared helper | Distinct ability paths converge; arguments and effects are correlated; positive and negative controls support the same behavioral contract. |

Avoid mistaking per-frame scheduler functions for ability helpers. Caller
identity, arguments, state mutation, and negative controls matter more than raw
call counts.

## Evidence record

Keep a machine-readable or tabular record for each candidate, linked to the raw
trace, JASS script/map, and Ghidra function. For example:

```json
{
  "build_sha256": "<exact executable hash>",
  "module": "Warcraft III.exe",
  "function_rva": "0x00300000",
  "provisional_name": "DamageApplicationCandidate",
  "confidence": "likely shared helper",
  "observed_callers": [
    { "caller_rva": "0x00100000", "scenario": "melee_hit" },
    { "caller_rva": "0x00200000", "scenario": "projectile_impact" }
  ],
  "arguments": [
    { "position": 0, "hypothesis": "target_object", "verified": false }
  ],
  "negative_controls": [],
  "notes": "Validate caller arguments and state writes before naming the contract."
}
```

Record raw captures, not only summaries, and distinguish observations from
inferences. Preserve the exact executable hash and build with every result.

## Suggested investigation order

The existing queue is maintained in
[ability-verification-review.md](ability-verification-review.md#remaining-native-inspection-queue);
this ordering is a practical starting point, not a substitute for that queue.

1. **Target validation:** controlled valid/invalid cases often expose clear
   branch differences. Map the shared validation helpers already listed in
   [ability-shared-native-functions.md](ability-shared-native-functions.md).
2. **Damage and attack dispatch:** compare ordinary attack impact against
   `UnitDamageTarget` to separate attack resolution, damage handling, and health
   mutation.
3. **Status expiry/removal:** trace asynchronous expiry separately from dispel,
   refresh, explicit removal, and death.
4. **Summon cleanup:** determine whether expiry, death, dispel, and explicit
   removal share cleanup, and whether expiry invokes ordinary death handling.

For the current investigation, Phoenix Fire is the next ability-specific
static trace: map interval, radius, and DataA/DataB reads, then follow
`CBuffPhoenixFire` and `CMissilePhoenixFire` through expiry and damage. The
queue's procedure decides whether JASS or Frida follow-up is still needed after
static inspection.

## Sources and related references

- [Shared Retail native ability functions](ability-shared-native-functions.md)
- [Ability verification review and remaining native inspection queue](ability-verification-review.md)
- [Ability implementation from data, behavior, and focused evidence](ability-implementation.md)
- [Retail ability architecture](ability-retail-architecture.md)

// WC3_RETAIL_SHA256: 3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed
// Read-only Ward order/validation trace for the executable above.
// Addresses below are RVAs relative to PE image base 0x00400000, recovered
// from that exact executable. Re-resolve them before use with another build.
'use strict';
const IMAGE_BASE = 0x00400000;
const module = Process.getModuleByName('Warcraft III.exe');
if (Process.arch !== 'ia32') throw new Error('Expected 32-bit Retail process; got ' + Process.arch);
const atVa = va => module.base.add(va - IMAGE_BASE);
const wardVtable = atVa(0x00F8ABB8);
const addresses = {
  wardValidation: atVa(0x00C34110),
  simpleSpellValidation: atVa(0x00B28980),
  validationFallback: atVa(0x007F6A00),
  wardOrderGetter: atVa(0x00C340F0)
};
let sequence = 0;
let dropped = false;
const activeByThread = new Map();
const MAX_EVENTS = 256;

function emit(event, fields) {
  if (sequence >= MAX_EVENTS) {
    if (!dropped) {
      dropped = true;
      send({event: 'trace-limit', limit: MAX_EVENTS});
    }
    return;
  }
  send(Object.assign({event, sequence: ++sequence, threadId: Process.getCurrentThreadId()}, fields));
}
function asHex(value) { return ptr(value).toString(); }
function isWardThis(value) {
  try { return ptr(value).readPointer().equals(wardVtable); }
  catch (_) { return false; }
}

send({event: 'agent-ready', pid: Process.id, arch: Process.arch,
      module: module.name, modulePath: module.path, moduleBase: module.base.toString(),
      imageBase: '0x00400000', wardVtable: wardVtable.toString(),
      targets: Object.fromEntries(Object.entries(addresses).map(([k, v]) => [k, v.toString()]))});

Interceptor.attach(addresses.wardValidation, {
  onEnter(args) {
    const self = this.context.ecx;
    this.matches = isWardThis(self);
    if (!this.matches) return;
    this.callId = ++sequence;
    const tid = Process.getCurrentThreadId();
    const stack = activeByThread.get(tid) || [];
    stack.push(this.callId);
    activeByThread.set(tid, stack);
    emit('ward-validation-enter', {
      callId: this.callId, self: self.toString(), vtable: self.readPointer().toString(),
      args: [asHex(args[0]), asHex(args[1]), asHex(args[2])]
    });
  },
  onLeave(retval) {
    if (!this.matches) return;
    emit('ward-validation-leave', {callId: this.callId, result: retval.toInt32(), resultHex: retval.toString()});
    const tid = Process.getCurrentThreadId();
    const stack = activeByThread.get(tid) || [];
    stack.pop();
    if (stack.length) activeByThread.set(tid, stack); else activeByThread.delete(tid);
  }
});

Interceptor.attach(addresses.simpleSpellValidation, {
  onEnter(args) {
    const self = this.context.ecx;
    this.matches = isWardThis(self);
    if (!this.matches) return;
    const stack = activeByThread.get(Process.getCurrentThreadId()) || [];
    this.callId = stack.length ? stack[stack.length - 1] : null;
    emit('simple-spell-validation-enter', {
      callId: this.callId, self: self.toString(),
      args: [asHex(args[0]), asHex(args[1]), asHex(args[2])]
    });
  },
  onLeave(retval) {
    if (this.matches) emit('simple-spell-validation-leave', {callId: this.callId, result: retval.toInt32(), resultHex: retval.toString()});
  }
});

Interceptor.attach(addresses.validationFallback, {
  onEnter(args) {
    const stack = activeByThread.get(Process.getCurrentThreadId()) || [];
    this.callId = stack.length ? stack[stack.length - 1] : null;
    this.matches = this.callId !== null;
    if (!this.matches) return;
    emit('validation-fallback-enter', {callId: this.callId,
      args: [asHex(args[0]), asHex(args[1]), asHex(args[2]), asHex(args[3])]});
  },
  onLeave(retval) {
    if (this.matches) emit('validation-fallback-leave', {callId: this.callId, result: retval.toInt32(), resultHex: retval.toString()});
  }
});

Interceptor.attach(addresses.wardOrderGetter, {
  onEnter() {
    this.self = this.context.ecx;
    this.matches = isWardThis(this.self);
  },
  onLeave(retval) {
    if (this.matches) emit('ward-order-id', {self: this.self.toString(), orderId: retval.toUInt32(), orderHex: retval.toString()});
  }
});

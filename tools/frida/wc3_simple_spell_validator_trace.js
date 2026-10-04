// WC3_RETAIL_SHA256: 3f2ed0120d80578bf07e4423296dade1adfb959d59a2d20a7584224559570eed
// Read-only probe for the exact executable hash above. This records pointer
// values only; it never dereferences game objects or changes arguments.
'use strict';
const IMAGE_BASE = 0x00400000;
const module = Process.getModuleByName('Warcraft III.exe');
if (Process.arch !== 'ia32') throw new Error('Expected 32-bit Retail process');
const address = module.base.add(0x00B28980 - IMAGE_BASE);
let count = 0;
const MAX_EVENTS = 512;
function emit(event, fields) {
  if (count >= MAX_EVENTS) return;
  send(Object.assign({event: event, sequence: ++count,
    threadId: Process.getCurrentThreadId(), timestamp: Date.now()}, fields));
}
send({event: 'agent-ready', pid: Process.id, arch: Process.arch,
  module: module.name, modulePath: module.path, moduleBase: module.base.toString(),
  imageBase: '0x00400000', validatorVa: '0x00B28980',
  validatorRva: '0x00728980', maxEvents: MAX_EVENTS});
Interceptor.attach(address, {
  onEnter(args) {
    this.callId = ++count;
    emit('simple-spell-enter', {callId: this.callId,
      self: this.context.ecx.toString(),
      args: [args[0].toString(), args[1].toString(), args[2].toString()]});
  },
  onLeave(retval) {
    emit('simple-spell-leave', {callId: this.callId,
      result: retval.toInt32(), resultHex: retval.toString()});
  }
});

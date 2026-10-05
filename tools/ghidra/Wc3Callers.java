// List direct callers of exact-build functions and count incoming code refs.
// Run from analyzeHeadless with preferred VAs after checking the executable hash.
import java.util.HashSet;
import java.util.Set;

import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;

public class Wc3Callers extends ghidra.app.script.GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 0) {
            println("Usage: Wc3Callers.java <preferred-VA> [...]");
            return;
        }

        println("Program: " + currentProgram.getName());
        println("Image base: " + currentProgram.getImageBase());
        for (String value : args) {
            Address target = toAddr(Long.decode(value));
            Function function = getFunctionAt(target);
            println("\nTARGET " + target + " "
                    + (function == null ? "<no function>" : function.getName()));

            int calls = 0;
            int nonCalls = 0;
            int shown = 0;
            Set<Address> uniqueCallers = new HashSet<>();
            ReferenceIterator refs = currentProgram.getReferenceManager().getReferencesTo(target);
            while (refs.hasNext()) {
                Reference ref = refs.next();
                Function caller = getFunctionContaining(ref.getFromAddress());
                if (ref.getReferenceType().isCall()) {
                    calls++;
                    if (caller != null) uniqueCallers.add(caller.getEntryPoint());
                    if (shown++ < 20) {
                        println("  CALL " + ref.getFromAddress() + " " + ref.getReferenceType()
                                + " caller=" + (caller == null ? "<no function>"
                                        : caller.getName() + "@" + caller.getEntryPoint()));
                    }
                } else {
                    nonCalls++;
                }
            }
            println("  DIRECT_CALL_REFERENCES " + calls);
            println("  UNIQUE_CALLER_FUNCTIONS " + uniqueCallers.size());
            println("  NON_CALL_REFERENCES " + nonCalls);
            if (calls > 20) println("  (first 20 direct call references shown)");
        }
    }
}

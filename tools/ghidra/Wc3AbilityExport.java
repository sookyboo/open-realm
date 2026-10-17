// Export exact-build WC3 static program evidence for ability reconstruction.
// @category WarcraftIII
// Headless args: output_dir sha256 scan|detail seed_rvas_csv vtable_rvas_csv timeout_secs max_slots
// Purely read-only. A pointer sequence is a vtable CANDIDATE, not a verified class.
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.FunctionIterator;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.mem.MemoryBlock;
import ghidra.program.model.pcode.HighFunction;
import ghidra.program.model.pcode.PcodeOp;
import ghidra.program.model.pcode.PcodeOpAST;
import ghidra.program.model.pcode.Varnode;
import ghidra.program.model.symbol.Reference;
import java.io.BufferedWriter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Iterator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public class Wc3AbilityExport extends GhidraScript {
    private static final long BASE = 0x00400000L;
    private final Map<String, BufferedWriter> outputs = new LinkedHashMap<>();
    private final Map<String, Integer> counts = new LinkedHashMap<>();

    private static String hex(long number) {
        return String.format(Locale.ROOT, "0x%08x", number & 0xffffffffL);
    }

    private static long parseRva(String value) {
        long parsed = Long.parseUnsignedLong(value.trim().replaceFirst("(?i)^0x", ""), 16);
        if (parsed > (0xffffffffL - BASE)) {
            throw new IllegalArgumentException("RVA cannot map into pinned PE32 VA: " + value);
        }
        return parsed;
    }

    private static List<Long> rvaList(String csv) {
        List<Long> result = new ArrayList<>();
        if (!csv.trim().isEmpty()) {
            for (String item : csv.split(",", -1)) result.add(parseRva(item));
        }
        return result;
    }

    private static String quote(String value) {
        StringBuilder out = new StringBuilder("\"");
        for (int i = 0; i < value.length(); i++) {
            char c = value.charAt(i);
            switch (c) {
                case '"': out.append("\\\""); break;
                case '\\': out.append("\\\\"); break;
                case '\n': out.append("\\n"); break;
                case '\r': out.append("\\r"); break;
                case '\t': out.append("\\t"); break;
                default:
                    if (c < 0x20) out.append(String.format(Locale.ROOT, "\\u%04x", (int) c));
                    else out.append(c);
            }
        }
        return out.append('"').toString();
    }

    @SuppressWarnings("unchecked")
    private static String json(Object value) {
        if (value == null) return "null";
        if (value instanceof String) return quote((String) value);
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        if (value instanceof Map) {
            List<String> elements = new ArrayList<>();
            for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet())
                elements.add(quote(String.valueOf(entry.getKey())) + ":" + json(entry.getValue()));
            return "{" + String.join(",", elements) + "}";
        }
        if (value instanceof Iterable) {
            List<String> elements = new ArrayList<>();
            for (Object item : (Iterable<?>) value) elements.add(json(item));
            return "[" + String.join(",", elements) + "]";
        }
        throw new IllegalArgumentException("unsupported JSON type: " + value.getClass());
    }

    private static Map<String, Object> object(Object... keyValues) {
        Map<String, Object> item = new LinkedHashMap<>();
        for (int i = 0; i < keyValues.length; i += 2)
            item.put((String) keyValues[i], keyValues[i + 1]);
        return item;
    }

    private void emit(String kind, Map<String, Object> row) throws IOException {
        BufferedWriter writer = outputs.get(kind);
        writer.write(json(row));
        writer.newLine();
        counts.put(kind, counts.get(kind) + 1);
    }

    private Address address(long va) {
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(va);
    }

    private String relative(Address point) {
        long value = point.getOffset();
        return point.isMemoryAddress() && currentProgram.getMemory().contains(point) && value >= BASE
            ? hex(value - BASE) : null;
    }

    private boolean executable(Address point) {
        MemoryBlock block = currentProgram.getMemory().getBlock(point);
        return block != null && block.isExecute();
    }

    private void scanFunction(Function function) throws Exception {
        Address entry = function.getEntryPoint();
        Function thunk = function.isThunk() ? function.getThunkedFunction(false) : null;
        emit("functions", object(
            "entry_va", hex(entry.getOffset()), "entry_rva", relative(entry),
            "name", function.getName(), "namespace", function.getParentNamespace().getName(true),
            "signature", function.getPrototypeString(false, true),
            "calling_convention", function.getCallingConventionName(),
            "thunk", function.isThunk(),
            "thunk_target_rva", thunk == null ? null : relative(thunk.getEntryPoint()),
            "body_min_va", hex(function.getBody().getMinAddress().getOffset()),
            "body_max_va", hex(function.getBody().getMaxAddress().getOffset()),
            "source", "ghidra_static_analysis"));
        InstructionIterator instructions = currentProgram.getListing().getInstructions(function.getBody(), true);
        while (instructions.hasNext()) {
            monitor.checkCancelled();
            Instruction instruction = instructions.next();
            Address site = instruction.getAddress();
            Reference[] refs = currentProgram.getReferenceManager().getReferencesFrom(site);
            boolean call = instruction.getFlowType().isCall();
            boolean computed = instruction.getFlowType().isComputed();
            int callRefs = 0;
            for (Reference ref : refs) {
                if (ref.getReferenceType().isCall()) {
                    callRefs++;
                    Address target = ref.getToAddress();
                    Function targetFunction = getFunctionAt(target);
                    emit("callsites", object(
                        "caller_rva", relative(entry), "site_rva", relative(site),
                        "target_va", hex(target.getOffset()), "target_rva", relative(target),
                        "target_is_executable", executable(target),
                        "target_function_entry_rva", targetFunction == null ? null : relative(targetFunction.getEntryPoint()),
                        "classification", computed ? "computed_call_reference" : "static_call_reference",
                        "reference_type", ref.getReferenceType().toString(),
                        "source", "ghidra_instruction_reference"));
                } else if (!ref.getReferenceType().isFlow()) {
                    // Data references are intentionally distinct from call edges.
                    Address target = ref.getToAddress();
                    emit("datarefs", object(
                        "function_rva", relative(entry), "site_rva", relative(site),
                        "target_va", hex(target.getOffset()), "target_rva", relative(target),
                        "reference_type", ref.getReferenceType().toString(),
                        "source", "ghidra_instruction_reference"));
                }
            }
            if (call && (computed || callRefs == 0)) {
                emit("callsites", object(
                    "caller_rva", relative(entry), "site_rva", relative(site),
                    "target_va", null, "target_rva", null,
                    "target_function_entry_rva", null,
                    "classification", "unresolved_indirect_call",
                    "mnemonic", instruction.getMnemonicString(),
                    "source", "ghidra_instruction_flow"));
            }
        }
    }

    private void decompile(Function function, DecompInterface decompiler, int timeout, String requested) throws Exception {
        monitor.checkCancelled();
        DecompileResults result = decompiler.decompileFunction(function, timeout, monitor);
        if (!result.decompileCompleted() || result.getDecompiledFunction() == null) {
            emit("decompiled", object("requested_rva", requested,
                "function_rva", relative(function.getEntryPoint()), "status", "failed",
                "error", result.getErrorMessage(), "c", null));
            return;
        }
        List<Object> indirect = new ArrayList<>();
        HighFunction high = result.getHighFunction();
        if (high != null) {
            Iterator<PcodeOpAST> ops = high.getPcodeOps();
            while (ops.hasNext()) {
                PcodeOpAST operation = ops.next();
                List<String> inputs = new ArrayList<>();
                for (int index = 0; index < operation.getNumInputs(); index++) {
                    Varnode input = operation.getInput(index);
                    inputs.add(input == null ? "null" : input.toString());
                }
                Varnode output = operation.getOutput();
                emit("pcode", object("function_rva", relative(function.getEntryPoint()),
                    "site_rva", relative(operation.getSeqnum().getTarget()),
                    "opcode", operation.getMnemonic(), "inputs", inputs,
                    "output", output == null ? null : output.toString(),
                    "note", "Decompiler p-code, not a resolved object field access."));
                if (operation.getOpcode() == PcodeOp.CALLIND) {
                    indirect.add(object("site_rva", relative(operation.getSeqnum().getTarget()),
                        "operation", "CALLIND", "status", "unresolved_dynamic_target"));
                }
            }
        }
        emit("decompiled", object("requested_rva", requested,
            "function_rva", relative(function.getEntryPoint()), "status", "complete",
            "c", result.getDecompiledFunction().getC(),
            "high_pcode_indirect_calls", indirect,
            "note", "Decompiler pseudocode, not original source or verified runtime semantics."));
    }

    private long readPointer(Address point) throws Exception {
        byte[] bytes = new byte[4];
        int read = currentProgram.getMemory().getBytes(point, bytes);
        if (read != 4) throw new IOException("incomplete pointer read at " + point);
        return ((long) bytes[0] & 255L) | (((long) bytes[1] & 255L) << 8)
            | (((long) bytes[2] & 255L) << 16) | (((long) bytes[3] & 255L) << 24);
    }

    private void scanVtable(long rva, int maxSlots) throws Exception {
        Address start = address(BASE + rva);
        List<Object> slots = new ArrayList<>();
        MemoryBlock origin = currentProgram.getMemory().getBlock(start);
        String reason = null;
        if (origin == null || !origin.isInitialized()) {
            reason = "vtable_seed_not_in_initialized_memory";
        } else {
            for (int index = 0; index < maxSlots; index++) {
                monitor.checkCancelled();
                Address location = start.add((long) index * 4);
                if (currentProgram.getMemory().getBlock(location) != origin) {
                    reason = "reached_memory_block_end";
                    break;
                }
                long pointer = readPointer(location);
                Address target = address(pointer);
                if (!executable(target)) {
                    reason = "first_nonexecutable_pointer";
                    break;
                }
                Function function = getFunctionAt(target);
                slots.add(object("offset", hex((long) index * 4),
                    "target_va", hex(pointer), "target_rva", relative(target),
                    "function_entry_confirmed", function != null,
                    "function_name", function == null ? null : function.getName()));
            }
            if (reason == null) reason = "max_slots_reached_table_may_continue";
        }
        List<Object> references = new ArrayList<>();
        for (Reference ref : getReferencesTo(start)) {
            references.add(object("from_va", hex(ref.getFromAddress().getOffset()),
                "from_rva", relative(ref.getFromAddress()),
                "reference_type", ref.getReferenceType().toString()));
        }
        emit("vtables", object("seed_va", hex(start.getOffset()), "seed_rva", hex(rva),
            "status", "pointer_table_candidate_only", "slots", slots,
            "references_to_seed", references,
            "stop_reason", reason,
            "note", "Pointer sequence alone does not identify a C++ class or prove a virtual dispatch."));
    }

    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 7) throw new IllegalArgumentException(
            "expected output_dir, sha256, mode, seed_csv, vtable_csv, timeout, slots");
        String sha = args[1].toLowerCase(Locale.ROOT);
        if (!sha.matches("[0-9a-f]{64}") || !sha.equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalArgumentException("exact-build executable SHA-256 mismatch");
        if (currentProgram.getImageBase().getOffset() != BASE
                || currentProgram.getLanguage().isBigEndian()
                || currentProgram.getLanguage().getDefaultSpace().getSize() != 32
                || !"x86".equalsIgnoreCase(currentProgram.getLanguage().getProcessor().toString()))
            throw new IllegalArgumentException("requires 32-bit little-endian x86 with image base 0x00400000");
        String mode = args[2];
        if (!mode.equals("scan") && !mode.equals("detail"))
            throw new IllegalArgumentException("invalid export mode");
        int timeout = Integer.parseInt(args[5]);
        int slots = Integer.parseInt(args[6]);
        if (timeout < 1 || timeout > 3600 || slots < 1 || slots > 512)
            throw new IllegalArgumentException("invalid export bounds");
        List<Long> seeds = rvaList(args[3]);
        List<Long> tables = rvaList(args[4]);
        if (mode.equals("detail") && seeds.isEmpty() && tables.isEmpty())
            throw new IllegalArgumentException("detail mode needs seeds");
        if (mode.equals("scan") && (!seeds.isEmpty() || !tables.isEmpty()))
            throw new IllegalArgumentException("scan mode takes no explicit seeds");
        Path directory = Paths.get(args[0]);
        Files.createDirectories(directory);
        List<String> kinds = Arrays.asList("functions", "callsites", "datarefs", "vtables", "decompiled", "pcode");
        for (String kind : kinds) {
            counts.put(kind, 0);
            outputs.put(kind, Files.newBufferedWriter(directory.resolve(kind + ".jsonl"),
                StandardCharsets.UTF_8));
        }
        List<Object> missing = new ArrayList<>();
        DecompInterface decompiler = new DecompInterface();
        try {
            if (!decompiler.openProgram(currentProgram))
                throw new IOException("cannot initialize Ghidra decompiler");
            if (mode.equals("scan")) {
                FunctionIterator iterator = currentProgram.getFunctionManager().getFunctions(true);
                while (iterator.hasNext()) {
                    monitor.checkCancelled();
                    Function function = iterator.next();
                    if (!function.isExternal()) scanFunction(function);
                }
            } else {
                for (long seed : seeds) {
                    monitor.checkCancelled();
                    Address point = address(BASE + seed);
                    Function function = getFunctionAt(point);
                    if (function == null) {
                        function = getFunctionContaining(point);
                        if (function == null) {
                            missing.add(object("rva", hex(seed), "reason", "no_analyzed_function"));
                            continue;
                        }
                    }
                    scanFunction(function);
                    decompile(function, decompiler, timeout, hex(seed));
                }
                for (long table : tables) scanVtable(table, slots);
            }
        } finally {
            decompiler.dispose();
            for (BufferedWriter writer : outputs.values()) writer.close();
        }
        Map<String, Object> summary = object(
            "schema_version", 1, "status", "complete", "mode", mode,
            "executable_sha256", sha, "image_base", hex(BASE),
            "architecture", "x86:LE:32", "program_name", currentProgram.getName(),
            "counts", counts, "unresolved_seeds", missing,
            "warnings", Arrays.asList("Static evidence only; indirect call receivers are not verified.",
                "Vtable entries are pointer-table candidates; label classes only after independent verification."));
        Path staged = directory.resolve("export-summary.json.tmp");
        Files.write(staged, (json(summary) + "\n").getBytes(StandardCharsets.UTF_8));
        Files.move(staged, directory.resolve("export-summary.json"), StandardCopyOption.ATOMIC_MOVE);
        println("Wc3AbilityExport completed: " + json(counts));
    }
}

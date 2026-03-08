// ============================================================================
// EmojiASM Stack-VM Interpreter Kernel (MSL)
//
// Each GPU thread executes one independent VM instance, interpreting shared
// bytecode from device memory.  Architecture follows switch-dispatch design
// validated by GVM (OOPSLA 2019).
//
// Instruction format (uint32):
//   [31:24]  opcode   (8 bits)
//   [23:0]   operand  (24 bits) -- constant pool index, jump target, or cell ID
//
// Float literals live in a separate constant pool; PUSH encodes the pool
// index in the operand field.
// ============================================================================

#include <metal_stdlib>
using namespace metal;

// ── Opcode constants (must match bytecode.py OP_MAP exactly) ────────────

// Stack manipulation
constant uint8_t OP_PUSH    = 0x01;
constant uint8_t OP_POP     = 0x02;
constant uint8_t OP_DUP     = 0x03;
constant uint8_t OP_SWAP    = 0x04;
constant uint8_t OP_OVER    = 0x05;
constant uint8_t OP_ROT     = 0x06;

// Arithmetic
constant uint8_t OP_ADD     = 0x10;
constant uint8_t OP_SUB     = 0x11;
constant uint8_t OP_MUL     = 0x12;
constant uint8_t OP_DIV     = 0x13;
constant uint8_t OP_MOD     = 0x14;

// Comparison & Logic
constant uint8_t OP_EQ      = 0x20;
constant uint8_t OP_LT      = 0x21;
constant uint8_t OP_GT      = 0x22;
constant uint8_t OP_AND     = 0x23;
constant uint8_t OP_OR      = 0x24;
constant uint8_t OP_NOT     = 0x25;

// Control Flow
constant uint8_t OP_JMP     = 0x30;
constant uint8_t OP_JZ      = 0x31;
constant uint8_t OP_JNZ     = 0x32;
constant uint8_t OP_CALL    = 0x33;
constant uint8_t OP_RET     = 0x34;
constant uint8_t OP_HALT    = 0x35;
constant uint8_t OP_NOP     = 0x36;

// Memory
constant uint8_t OP_STORE   = 0x40;
constant uint8_t OP_LOAD    = 0x41;

// Arrays
#define MAX_ARRAYS      8
#define MAX_ARRAY_SIZE  256

constant uint8_t OP_ALLOC   = 0x42;
constant uint8_t OP_ALOAD   = 0x43;
constant uint8_t OP_ASTORE  = 0x44;
constant uint8_t OP_ALEN    = 0x45;

// I/O
constant uint8_t OP_PRINT   = 0x50;
constant uint8_t OP_PRINTLN = 0x51;

// Random
constant uint8_t OP_RANDOM  = 0x60;

// Math
constant uint8_t OP_POW     = 0x15;
constant uint8_t OP_SQRT    = 0x16;
constant uint8_t OP_SIN     = 0x17;
constant uint8_t OP_COS     = 0x18;
constant uint8_t OP_EXP     = 0x19;
constant uint8_t OP_LOG     = 0x1A;
constant uint8_t OP_ABS     = 0x1B;
constant uint8_t OP_MIN     = 0x1C;
constant uint8_t OP_MAX     = 0x1D;

// ── Status codes ────────────────────────────────────────────────────────

constant uint32_t STATUS_OK         = 0;
constant uint32_t STATUS_ERROR      = 1;
constant uint32_t STATUS_DIV_ZERO   = 2;
constant uint32_t STATUS_TIMEOUT    = 3;

// ── Fixed-size limits ───────────────────────────────────────────────────

// Call stack depth (thread-local, small enough for registers per KB #146)
constant int CALL_STACK_DEPTH = 32;

// Memory cells per thread (thread-local array)
constant int NUM_MEMORY_CELLS = 128;

// ── Output buffer entry (Tier 2 output capture) ────────────────────────

struct OutputEntry {
    uint32_t thread_id;
    uint32_t seq_num;    // per-thread ordering
    uint32_t type;       // 0=float, 1=string_index, 2=newline
    float    value;      // for type=0
    uint32_t str_idx;    // for type=1
};

// ── Philox-4x32-10 PRNG (counter-based, GPU-friendly) ──────────────────
//
// Implements the Philox-4x32-10 algorithm for high-quality random numbers.
// Each thread gets a unique stream seeded by its thread ID.

struct PhiloxState {
    uint32_t counter[4];  // 128-bit counter
    uint32_t key[2];      // 64-bit key (derived from thread ID)
};

// Philox round constants (from the original paper)
constant uint32_t PHILOX_M0 = 0xD2511F53u;
constant uint32_t PHILOX_M1 = 0xCD9E8D57u;
constant uint32_t PHILOX_W0 = 0x9E3779B9u;  // golden ratio
constant uint32_t PHILOX_W1 = 0xBB67AE85u;  // sqrt(3) - 1

// mulhi: compute high 32 bits of a * b
inline uint32_t mulhi32(uint32_t a, uint32_t b) {
    return uint32_t((uint64_t(a) * uint64_t(b)) >> 32);
}

// Single Philox round
inline void philox_round(thread uint32_t* ctr, thread uint32_t* key) {
    uint32_t hi0 = mulhi32(PHILOX_M0, ctr[0]);
    uint32_t lo0 = PHILOX_M0 * ctr[0];
    uint32_t hi1 = mulhi32(PHILOX_M1, ctr[2]);
    uint32_t lo1 = PHILOX_M1 * ctr[2];

    uint32_t t0 = hi1 ^ ctr[1] ^ key[0];
    uint32_t t1 = lo1;
    uint32_t t2 = hi0 ^ ctr[3] ^ key[1];
    uint32_t t3 = lo0;

    ctr[0] = t0;
    ctr[1] = t1;
    ctr[2] = t2;
    ctr[3] = t3;
}

// Bump the key between rounds
inline void philox_bump_key(thread uint32_t* key) {
    key[0] += PHILOX_W0;
    key[1] += PHILOX_W1;
}

// Full Philox-4x32-10: 10 rounds of mixing
inline void philox4x32_10(thread uint32_t* ctr, thread uint32_t* key) {
    philox_round(ctr, key); philox_bump_key(key);  // round 1
    philox_round(ctr, key); philox_bump_key(key);  // round 2
    philox_round(ctr, key); philox_bump_key(key);  // round 3
    philox_round(ctr, key); philox_bump_key(key);  // round 4
    philox_round(ctr, key); philox_bump_key(key);  // round 5
    philox_round(ctr, key); philox_bump_key(key);  // round 6
    philox_round(ctr, key); philox_bump_key(key);  // round 7
    philox_round(ctr, key); philox_bump_key(key);  // round 8
    philox_round(ctr, key); philox_bump_key(key);  // round 9
    philox_round(ctr, key);                         // round 10 (no bump after last)
}

// Generate a random float in [0.0, 1.0) from a Philox state.
// Increments the counter so successive calls yield different values.
inline float philox_random(thread PhiloxState& state) {
    // Copy counter and key for this generation
    uint32_t ctr[4] = {state.counter[0], state.counter[1],
                        state.counter[2], state.counter[3]};
    uint32_t key[2] = {state.key[0], state.key[1]};

    // Run Philox
    philox4x32_10(ctr, key);

    // Increment the counter for next call
    state.counter[0] += 1;
    if (state.counter[0] == 0) {
        state.counter[1] += 1;
        if (state.counter[1] == 0) {
            state.counter[2] += 1;
            if (state.counter[2] == 0) {
                state.counter[3] += 1;
            }
        }
    }

    // Convert first output word to float in [0.0, 1.0)
    // Multiply by 2^-32 to get uniform distribution
    return float(ctr[0]) * (1.0f / 4294967296.0f);
}

// ── Main VM kernel ──────────────────────────────────────────────────────

kernel void emojiasm_vm(
    device const uint32_t* bytecode    [[buffer(0)]],  // shared program
    device const float*    constants   [[buffer(1)]],  // float constant pool
    device float*          stacks      [[buffer(2)]],  // per-thread stacks (stride = stack_depth)
    device float*          results     [[buffer(3)]],  // one float per thread (TOS at HALT)
    device uint32_t*       status      [[buffer(4)]],  // 0=ok, 1=error, 2=div-by-zero, 3=timeout
    constant uint32_t&     num_insts   [[buffer(5)]],
    constant uint32_t&     stack_depth [[buffer(6)]],
    constant uint32_t&     max_steps   [[buffer(7)]],
    device OutputEntry*    output_buf  [[buffer(8)]],   // Tier 2: per-thread output slots
    device uint32_t*       output_counts [[buffer(9)]],  // Tier 2: entries written per thread
    constant uint32_t&     output_cap  [[buffer(10)]],  // Tier 2: max entries per thread (0 = disabled)
    uint                   tid         [[thread_position_in_grid]]
)
{
    // ── Per-thread state ────────────────────────────────────────────────

    // Stack pointer into device memory (per-thread region)
    int sp = 0;
    device float* stack = stacks + (tid * stack_depth);

    // Call stack in thread-local memory (small, fits in registers per KB #146)
    uint32_t call_stack[CALL_STACK_DEPTH];
    int csp = 0;  // call stack pointer

    // Memory cells in thread-local memory
    float memory[NUM_MEMORY_CELLS];
    for (int i = 0; i < NUM_MEMORY_CELLS; i++) {
        memory[i] = 0.0f;
    }

    // Per-thread array storage
    float arrays[MAX_ARRAYS][MAX_ARRAY_SIZE];
    int array_sizes[MAX_ARRAYS];
    for (int a = 0; a < MAX_ARRAYS; a++) {
        array_sizes[a] = 0;
    }

    // Instruction pointer
    uint32_t ip = 0;

    // Step counter for timeout protection
    uint32_t steps = 0;

    // Thread status (default OK)
    status[tid] = STATUS_OK;

    // Initialize Philox PRNG state seeded with thread ID
    PhiloxState rng;
    rng.counter[0] = 0;
    rng.counter[1] = 0;
    rng.counter[2] = 0;
    rng.counter[3] = 0;
    rng.key[0] = tid;
    rng.key[1] = 0x12345678u;  // fixed salt for reproducibility

    // Per-thread output sequence counter (Tier 2 output ordering)
    uint32_t my_seq = 0;

    // ── Main dispatch loop ──────────────────────────────────────────────

    bool running = true;

    while (running && ip < num_insts) {
        // Timeout check
        if (steps >= max_steps) {
            status[tid] = STATUS_TIMEOUT;
            break;
        }
        steps++;

        // Decode instruction
        uint32_t inst = bytecode[ip];
        uint8_t opcode = uint8_t((inst >> 24) & 0xFF);
        uint32_t operand = inst & 0x00FFFFFF;

        // Advance IP (jumps will override)
        ip++;

        // ── Switch dispatch (KB #87, #139) ──────────────────────────────

        switch (opcode) {

        // ── Stack operations ────────────────────────────────────────────

        case OP_PUSH: {
            if (sp >= int(stack_depth)) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp] = constants[operand];
            sp++;
            break;
        }

        case OP_POP: {
            if (sp <= 0) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            break;
        }

        case OP_DUP: {
            if (sp <= 0 || sp >= int(stack_depth)) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp] = stack[sp - 1];
            sp++;
            break;
        }

        case OP_SWAP: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            float tmp = stack[sp - 1];
            stack[sp - 1] = stack[sp - 2];
            stack[sp - 2] = tmp;
            break;
        }

        case OP_OVER: {
            if (sp < 2 || sp >= int(stack_depth)) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp] = stack[sp - 2];
            sp++;
            break;
        }

        case OP_ROT: {
            if (sp < 3) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            // ROT: ( a b c -- b c a )
            float a = stack[sp - 3];
            float b = stack[sp - 2];
            float c = stack[sp - 1];
            stack[sp - 3] = b;
            stack[sp - 2] = c;
            stack[sp - 1] = a;
            break;
        }

        // ── Arithmetic ──────────────────────────────────────────────────

        case OP_ADD: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = stack[sp - 1] + stack[sp];
            break;
        }

        case OP_SUB: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = stack[sp - 1] - stack[sp];
            break;
        }

        case OP_MUL: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = stack[sp - 1] * stack[sp];
            break;
        }

        case OP_DIV: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            if (stack[sp - 1] == 0.0f) {
                status[tid] = STATUS_DIV_ZERO;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = stack[sp - 1] / stack[sp];
            break;
        }

        case OP_MOD: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            if (stack[sp - 1] == 0.0f) {
                status[tid] = STATUS_DIV_ZERO;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = fmod(stack[sp - 1], stack[sp]);
            break;
        }

        // ── Comparison & Logic ──────────────────────────────────────────

        case OP_EQ: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = (stack[sp - 1] == stack[sp]) ? 1.0f : 0.0f;
            break;
        }

        case OP_LT: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = (stack[sp - 1] < stack[sp]) ? 1.0f : 0.0f;
            break;
        }

        case OP_GT: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = (stack[sp - 1] > stack[sp]) ? 1.0f : 0.0f;
            break;
        }

        case OP_AND: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = (stack[sp - 1] != 0.0f && stack[sp] != 0.0f) ? 1.0f : 0.0f;
            break;
        }

        case OP_OR: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = (stack[sp - 1] != 0.0f || stack[sp] != 0.0f) ? 1.0f : 0.0f;
            break;
        }

        case OP_NOT: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp - 1] = (stack[sp - 1] == 0.0f) ? 1.0f : 0.0f;
            break;
        }

        // ── Control Flow ────────────────────────────────────────────────

        case OP_JMP: {
            ip = operand;
            break;
        }

        case OP_JZ: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            if (stack[sp] == 0.0f) {
                ip = operand;
            }
            break;
        }

        case OP_JNZ: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            if (stack[sp] != 0.0f) {
                ip = operand;
            }
            break;
        }

        case OP_CALL: {
            if (csp >= CALL_STACK_DEPTH) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            call_stack[csp] = ip;  // save return address (already incremented)
            csp++;
            ip = operand;
            break;
        }

        case OP_RET: {
            if (csp <= 0) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            csp--;
            ip = call_stack[csp];
            break;
        }

        case OP_HALT: {
            // KB #135: HALT breaks from while loop
            running = false;
            break;
        }

        case OP_NOP: {
            // No operation
            break;
        }

        // ── Memory ──────────────────────────────────────────────────────

        case OP_STORE: {
            if (sp < 1 || int(operand) >= NUM_MEMORY_CELLS) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            memory[operand] = stack[sp];
            break;
        }

        case OP_LOAD: {
            if (int(operand) >= NUM_MEMORY_CELLS || sp >= int(stack_depth)) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp] = memory[operand];
            sp++;
            break;
        }

        // ── Arrays ────────────────────────────────────────────────────────

        case OP_ALLOC: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            int cell = operand;
            if (cell >= MAX_ARRAYS) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            int sz = (int)stack[--sp];
            if (sz < 0 || sz > MAX_ARRAY_SIZE) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            array_sizes[cell] = sz;
            for (int j = 0; j < sz; j++) arrays[cell][j] = 0.0f;
            break;
        }

        case OP_ALOAD: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            int cell = operand;
            if (cell >= MAX_ARRAYS) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            int idx = (int)stack[--sp];
            if (idx < 0 || idx >= array_sizes[cell]) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            if (sp >= int(stack_depth)) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp] = arrays[cell][idx];
            sp++;
            break;
        }

        case OP_ASTORE: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            int cell = operand;
            if (cell >= MAX_ARRAYS) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            float val = stack[--sp];
            int idx = (int)stack[--sp];
            if (idx < 0 || idx >= array_sizes[cell]) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            arrays[cell][idx] = val;
            break;
        }

        case OP_ALEN: {
            int cell = operand;
            if (cell >= MAX_ARRAYS) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            if (sp >= int(stack_depth)) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp] = (float)array_sizes[cell];
            sp++;
            break;
        }

        // ── I/O ─────────────────────────────────────────────────────────
        // GPU cannot do real I/O.  PRINT/PRINTLN pop the top value and
        // discard it (output is captured via the results buffer at HALT).

        case OP_PRINT: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            if (output_cap > 0 && my_seq < output_cap) {
                // Tier 2: capture value in per-thread output slot
                uint32_t pos = tid * output_cap + my_seq;
                output_buf[pos].thread_id = tid;
                output_buf[pos].seq_num = my_seq;
                output_buf[pos].type = 0;
                output_buf[pos].value = stack[sp - 1];
                output_buf[pos].str_idx = 0;
                my_seq++;
                results[tid] = stack[--sp];
            } else {
                // Tier 1 fallback or overflow: just discard (legacy behavior)
                sp--;
            }
            break;
        }

        case OP_PRINTLN: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            if (output_cap > 0 && my_seq + 1 < output_cap) {
                // Tier 2: capture value + newline in per-thread output slots
                uint32_t base_pos = tid * output_cap + my_seq;
                output_buf[base_pos].thread_id = tid;
                output_buf[base_pos].seq_num = my_seq;
                output_buf[base_pos].type = 0;
                output_buf[base_pos].value = stack[sp - 1];
                output_buf[base_pos].str_idx = 0;
                my_seq++;
                // Newline entry
                uint32_t nl_pos = tid * output_cap + my_seq;
                output_buf[nl_pos].thread_id = tid;
                output_buf[nl_pos].seq_num = my_seq;
                output_buf[nl_pos].type = 2;
                output_buf[nl_pos].value = 0.0f;
                output_buf[nl_pos].str_idx = 0;
                my_seq++;
                results[tid] = stack[--sp];
            } else {
                // Tier 1 fallback or overflow: just discard (legacy behavior)
                sp--;
            }
            break;
        }

        // ── Random ──────────────────────────────────────────────────────

        case OP_RANDOM: {
            if (sp >= int(stack_depth)) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp] = philox_random(rng);
            sp++;
            break;
        }

        // ── Math ──────────────────────────────────────────────────────────

        case OP_POW: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = pow(stack[sp - 1], stack[sp]);
            break;
        }

        case OP_SQRT: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp - 1] = sqrt(stack[sp - 1]);
            break;
        }

        case OP_SIN: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp - 1] = sin(stack[sp - 1]);
            break;
        }

        case OP_COS: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp - 1] = cos(stack[sp - 1]);
            break;
        }

        case OP_EXP: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp - 1] = exp(stack[sp - 1]);
            break;
        }

        case OP_LOG: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp - 1] = log(stack[sp - 1]);
            break;
        }

        case OP_ABS: {
            if (sp < 1) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            stack[sp - 1] = fabs(stack[sp - 1]);
            break;
        }

        case OP_MIN: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = min(stack[sp - 1], stack[sp]);
            break;
        }

        case OP_MAX: {
            if (sp < 2) {
                status[tid] = STATUS_ERROR;
                running = false;
                break;
            }
            sp--;
            stack[sp - 1] = max(stack[sp - 1], stack[sp]);
            break;
        }

        // ── Unknown opcode ──────────────────────────────────────────────

        default: {
            status[tid] = STATUS_ERROR;
            running = false;
            break;
        }

        }  // end switch
    }  // end while

    // ── Write result ────────────────────────────────────────────────────
    // Store TOS (top of stack) as the thread's result.
    // If stack is empty, result is 0.0.

    if (sp > 0) {
        results[tid] = stack[sp - 1];
    } else {
        results[tid] = 0.0f;
    }

    // Store how many output entries this thread wrote (Tier 2)
    if (output_cap > 0) {
        output_counts[tid] = my_seq;
    }
}

# EcoLang – A Practical Guide

Welcome to EcoLang, a tiny teaching language designed to make programming approachable while raising awareness about the environmental cost of computation. This guide explains what EcoLang is, how to write programs, and how to get the most out of the language in an efficient and eco‑friendly way.

This tutorial matches the current interpreter implementation in `backend/ecolang/interpreter.py` so what you learn here will run exactly as described.

## What EcoLang is about

- Purpose: Teach programming basics and green computing. Every run estimates energy usage (Joules, kWh) and CO₂ grams for your code.
- Mental model: A simple, line‑oriented language. Each line is a statement like “say …”, “let …”, “if … then … end”.
- Safety: A guarded interpreter with time, step, and output limits. Expressions are evaluated via a safe AST subset.

### Strengths

- Friendly syntax and helpful error messages with line/column context
- Deterministic and safe execution with sensible resource limits
- Built‑in eco features: estimated total operations, energy and CO₂, plus tips
- Small, composable feature set: variables, constants, expressions, conditionals, loops, functions, arrays, inputs

### Limitations (by design)

- No general file/network I/O; programs are sandboxed
- Expressions are a restricted subset (no indexing with [], no attribute access, no arbitrary Python/JS calls)
- Loops supported: `repeat N times`, `while <cond> then … end`, and `for name = start to end [step s]`
- Function recursion depth is capped; parameter count is small
- Output length, step count, and wall‑clock time are limited per run

## Quick start: your first program

```text
say "Hello Eco"
```

Output appears in the Output panel, and Eco stats show estimated energy usage and CO₂.

## Language basics

### Comments and blank lines

- Lines beginning with `#` are comments and are ignored.
- Blank lines are ignored.

Example:

```text
# This is a comment
say "EcoLang"  # Inline comments are not parsed; prefer putting comments on their own lines
```

### Data types

- Numbers: integers and floats (e.g., `42`, `3.14`)
- Booleans: `true`, `false`
- Strings: quoted text ("…" or '…')
- Arrays: created with `array()` and manipulated using helper functions (see Arrays)

### Variables and constants

- Assign with `let name = <expr>`
- Define read‑only constants with `const NAME = <expr>` (reassignment is blocked)

Examples:

```text
let x = 10
let msg = "Hi " + toString(x)
const LIMIT = 3
```

If you try to reassign a `const`, you’ll get a runtime error.

## Expressions (safe subset)

EcoLang expressions use a safe evaluator. You can combine literals, variables, and these operators/functions:

Arithmetic

- `+  -  *  /  %  //  **` (power is limited to small exponents; max exponent magnitude is 8)

Comparisons

- `==  !=  <  <=  >  >=` (no chained comparisons like `a < b < c`)

Unary and boolean

- `+x  -x  not x  x and y  x or y`

String concatenation

- `+` concatenates if either operand is a string, e.g., `"Hello " + name`

Built‑in expression functions

- `len(x)` or `length(x)` – length of string or array
- `toNumber(x)` – convert string/number to number (int or float); errors if invalid
- `toString(x)` – convert any value to string
- `array()` – create a new empty array
- `append(arr, x)` – return a new array with `x` appended (functional, does not mutate)
- `at(arr, i)` – get element at index `i` (0‑based); errors if out of range
- `ecoOps()` – current total operations counted so far (integer)

Unsupported in expressions (examples)

- Indexing like `arr[0]` (use `at(arr, 0)` instead)
- Attribute access (`obj.attr`), imports, comprehensions, function/lambda definitions
- Calling arbitrary names except the whitelisted functions above

## Statements

Each non‑blank, non‑comment line is one statement. Supported statements:

### say

Evaluate an expression and print it to the output.

```text
say "Eco " + toString(2025)
```

### let

Bind a variable to the value of an expression.

```text
let a = 1 + 2
let name = "Ada"
```

### const

Declare a read‑only value. Attempting to change it later yields an error.

```text
const PI = 3.14159
```

### warn

Evaluate an expression and record it as a warning (it shows in the Warnings panel, not in Output).

```text
warn "Beta feature"
warn toString(len(array()))
```

### ask

Read a named input value provided externally (e.g., via the UI “Inputs (JSON)” box). If the input is missing, a runtime error is produced.

```text
ask city
say "Hello " + city
```

With inputs: `{ "city": "Accra" }`

### if / elif / else / end

Conditional execution. Syntax requires `then` on the `if` (and on `elif`). Only a single `elif` is supported at top level inside the block.

```text
if len(name) > 0 then
    say "Hi " + name
elif true then
    say "No name given"
else
    say "(fallback)"
end
```

Common errors:

- Missing `then` after `if` or `elif`
- Unmatched or extra `end`

### repeat N times … end

Repeat the body block N times. If N exceeds the configured loop cap, it is truncated and a warning is added.

```text
repeat 3 times
    say "tick"
end

```

### while … then … end

Loop while a condition remains true. The condition is re‑evaluated each iteration. A `then` is required on the `while` line.

```text
let n = 3
while n > 0 then
    say toString(n)
    let n = n - 1
end
say "Done"
```

If the loop would exceed the internal iteration cap, it stops and adds a warning.

### for name = start to end [step s]

Count from start to end inclusive. `step` is optional (defaults to +1 when start ≤ end, else −1). The loop variable is available inside the body.

```text
for i = 1 to 3
    say i
end

for k = 5 to 1 step -2
    say k
end
```

### func / return / call

Define a function, then call it later. Functions may take up to 3 parameters and call depth is limited (to prevent runaway recursion).

Define:

```text
func add a b
    return a + b
end
```

Call and capture:

```text
call add with 2, 3 into result
say result
```

Call without `into` prints the return value:

```text
call add with 1, 1
```

Argument counts must match the definition exactly or you’ll get an error.

### ecoTip

Print a small tip message related to efficient coding and energy use.

```text
ecoTip
```

### savePower N

Suggests a power‑saving level (0–100). This lowers the internal operation scale for the rest of the program (minimum 0.1), helping you compare “eco” modes. A message is added to Warnings.

```text
savePower 20
```

Tip: You can query `ecoOps()` in expressions to inspect the current op count.

## Arrays by example

```text
let xs = array()
let xs2 = append(xs, 1)
let xs3 = append(xs2, 2)
say length(xs3)
say at(xs3, 1)
```

Remember: arrays are functional in helpers here—`append` returns a new array. Use `xs = append(xs, v)` if you want to keep growing the same variable.

Expected output:

```text
2
2
```

## Inputs (ask) and environment

The runtime provides an `inputs` map. `ask name` reads from it or fails if missing.

Example run inputs (JSON):
 
```json
{"answer":"yes", "age": 18}
```

Program:

```text
ask answer
ask age
if answer == "yes" and age >= 18 then
    say "Welcome"
else
    say "Access denied"
end
```

## Errors and diagnostics

When something goes wrong, you’ll get a structured error with:

- code: SYNTAX_ERROR, RUNTIME_ERROR, TIMEOUT, STEP_LIMIT, OUTPUT_LIMIT, etc.
- message: human‑readable explanation
- line/column: where the problem occurred (when applicable)
- context: the original line text (for syntax/runtime errors inside statements)

Examples of common mistakes

```text
let 1x = 2         # Invalid identifier
if x > 0           # Missing 'then'
repeat two times   # Non‑numeric count
call f with 1, 2   # Argument count mismatch (if f expects one arg)
```

## Eco metrics: how usage is estimated

The interpreter tracks an approximate “operation” count for various actions (printing, math, loops, function calls). It computes:

- total_ops: accumulated estimated operations
- energy_J: Joules for compute + runtime overhead
- energy_kWh: kWh equivalent
- co2_g: grams of CO₂ (using a configurable grid factor)
- tips: suggestions when `total_ops` is high

High operation counts insert a “High estimated energy use” warning automatically.

You can influence the cost a bit with `savePower N` and by writing simpler code (fewer iterations, simpler math, fewer prints).

## Resource limits and safety

Per run limits (approximate defaults):

- Steps: 100,000 (overall dispatch/ops)
- Loop count per `repeat`: 10,000 (higher values are truncated)
- Time: ~1.5 seconds wall‑clock
- Output length: 5,000 characters
- Functions: up to 3 parameters; call depth up to 5

When a limit is exceeded you’ll get a clear error (e.g., TIMEOUT, STEP_LIMIT, OUTPUT_LIMIT). Many cases still return partial output and warnings.

## Best practices for green code

- Keep loops tight: prefer smaller repeat counts; use simple math inside
- Avoid excessive printing (it costs ops and grows the output)
- Precompute values you reuse instead of recomputing
- Use early returns in functions to avoid unnecessary work
- Consider `savePower` to compare “eco mode” behaviour

## Cookbook: practical examples

Hello with a name

```text
ask name
say "Hello, " + name
```

FizzBuzz (eco‑style, small N)

```text
func fb n
    if n % 15 == 0 then
        return "FizzBuzz"
    elif n % 3 == 0 then
        return "Fizz"
    else
        if n % 5 == 0 then
            return "Buzz"
        else
            return toString(n)
        end
    end
end

repeat 5 times
    let i = ecoOps()
    call fb with i into out
    say out
end
```

Sum an array

```text
func sum3 a b c
    return a + b + c
end

let xs = append(append(array(), 2), 3)
let total = 0
let total = total + at(xs, 0)
let total = total + at(xs, 1)
say total
```

Greener run using savePower

```text
savePower 25
repeat 3 times
    say ecoOps()
end
```

## FAQ

Q: Can I index arrays with `xs[0]`?

- No. Use `at(xs, 0)`.

Q: Can I call custom helpers from expressions?

- Only the whitelisted ones (`len`, `length`, `toNumber`, `toString`, `array`, `append`, `at`, `ecoOps`).

Q: Are strings single or double quoted?

- Both work. Examples use double quotes.

Q: Is recursion allowed?

- Limited by call depth (≈5). Very deep recursion will fail.

Q: Are there while/for loops?

- Yes. In addition to `repeat N times`, you can use `while <cond> then … end` and `for name = start to end [step s]`.

---

You’re ready to write EcoLang code. Keep an eye on the eco metrics and try to refactor programs to do the same work with fewer operations—small optimizations, big lessons.

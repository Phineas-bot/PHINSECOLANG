from backend.ecolang.interpreter import Interpreter
src = (
    'savePower 2\n'
    'say "Hello Eco"\n'
    'let greeting = "Hello " + "World"\n'
    'say "Greet: " + greeting\n'
    'let a = 2 + 3 * 4\n'
    'say "a = " + a\n'
    'let big = a >= 10\n'
    'if big == true then\n  say "a is large enough"\nelse\n  warn "a is small"\nend\n'
    'ask answer\n'
    'say "Answer was: " + answer\n'
    'if answer == "yes" then\n  say "Affirmative."\nelse\n  warn "Consider answering yes for a greener tip."\nend\n'
    'ecoTip\n'
    'let i = 1\n'
    'repeat 3 times\n  say "Loop iteration " + i\n  if i > 1 then\n    warn "Past the first iteration; consider reducing loops to save energy."\n  else\n    say "First pass is usually the greenest."\n  end\n  let i = i + 1\nend\n'
    'say "Demo complete."\n'
)
it = Interpreter()
res = it.run(src, inputs={"answer":"yes"})
print(res["output"]) 
print("WARN:", res.get("warnings"))
print("ECO: total_ops=", res.get("eco", {}).get("total_ops"))

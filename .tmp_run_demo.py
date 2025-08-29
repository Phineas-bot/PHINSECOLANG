import json
from backend.ecolang.interpreter import Interpreter
it = Interpreter()
res = it.run(" + # EcoLang fullsyntax demo
savePower 2
say "Hello Eco"
let greeting = "Hello " + "World"
say "Greet: " + greeting
let a = 2 + 3 * 4
say "a = " + a
let big = a >= 10
if big == true then
  say "a is large enough"
else
  warn "a is small"
end
ask answer
say "Answer was: " + answer
if answer == "yes" then
  say "Affirmative."
else
  warn "Consider answering yes for a greener tip."
end
ecoTip
let i = 1
repeat 3 times
  say "Loop iteration " + i
  if i > 1 then
    warn "Past the first iteration; consider reducing loops to save energy."
  else
    say "First pass is usually the greenest."
  end
  let i = i + 1
end
say "Demo complete.".Replace(", "") + ", inputs={"answer":"yes"})
print(json.dumps(res, ensure_ascii=False, indent=2))

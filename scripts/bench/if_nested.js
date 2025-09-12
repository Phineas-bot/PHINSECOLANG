// Equivalent of EcoLang nested if/else; scaled by N iterations and prints ECO_OPS
function main() {
  const N = parseInt(process.env.ECO_BENCH_N || "1000000", 10);
  const a = 2;
  let s = 0;
  for (let i = 0; i < N; i++) {
    if (a > 0) {
      if (a === 2) {
        s += 1;
      } else {
        s -= 1;
      }
    } else {
      s -= 2;
    }
  }
  console.log(s); // optional: prevents dead code elimination
  const ops_per_iter = 3; // two comparisons + one update
  console.log(`ECO_OPS: ${N * ops_per_iter}`);
}

main();

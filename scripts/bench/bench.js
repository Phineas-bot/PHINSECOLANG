// Simple Node.js benchmark that prints ECO_OPS
const N = parseInt(process.env.ECO_BENCH_N || "5000000", 10);
let s = 0;
for (let i = 0; i < N; i++) {
  s += (i & 1);
}
console.log(s);           // optional correctness output
console.log(`ECO_OPS: ${N}`); // required for wrapper

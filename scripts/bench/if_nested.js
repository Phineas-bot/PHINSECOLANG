// Equivalent of EcoLang nested if/else; prints ECO_OPS for wrapper
function main() {
  const a = 2;
  if (a > 0) {
    if (a === 2) {
      console.log("inner-yes");
    } else {
      console.log("inner-no");
    }
  } else {
    console.log("outer-no");
  }
  // assignment + two comparisons + one print path = 4 logical ops
  console.log("ECO_OPS: 4");
}

main();

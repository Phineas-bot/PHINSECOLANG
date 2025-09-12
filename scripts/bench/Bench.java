public class Bench {
  public static void main(String[] args) {
    int N = Integer.parseInt(System.getenv().getOrDefault("ECO_BENCH_N", "5000000"));
    long s = 0;
    for (int i = 0; i < N; i++) {
      s += (i & 1);
    }
    System.out.println(s);                 // optional correctness output
    System.out.println("ECO_OPS: " + N);   // required
  }
}

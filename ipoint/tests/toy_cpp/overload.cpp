struct E {
  int est(int a);
  int est(double b);
};
int E::est(int a) {
  if (a > 1) return a;
  return 1;
}
int E::est(double b) { return static_cast<int>(b) + est(1); }

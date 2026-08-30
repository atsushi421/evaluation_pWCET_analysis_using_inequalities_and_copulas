int guarded(int x) {
  try {
    if (x > 0) throw x;
    return 0;
  } catch (int e) {
    return e;
  }
}
const int &pick(const int &a, const int &b, bool first) {
  if (first) return a;
  return b;
}

namespace {
int g_state = 0;
void set_state(int s) { g_state = s; }
}  // namespace
void update(int x) {
  if (x > 10) return set_state(2);
  if (x > 0) {
    return set_state(1);
  }
  set_state(0);
}
int state() { return g_state; }

#include <string>
#include <utility>
#include <vector>
namespace toy {
class Acc {
 public:
  explicit Acc(int n) : n_(n) {}
  int sum_to(int x);
  void fill(std::vector<int> &v);
  std::string name(int k);
  int n_;
};
int Acc::sum_to(int x) {
  if (x <= 0) return 0;
  int s = 0;
  for (int i = 0; i < x; i++) {
    if (i % 2 == 0) continue;
    s += i;
  }
  return s + n_;
}
void Acc::fill(std::vector<int> &v) {
  for (auto &e : v) {
    e = n_;
  }
  auto twice = [](int y) {
    if (y > 0) return 2 * y;
    return 0;
  };
  n_ = twice(n_);
}
std::string Acc::name(int k) {
  if (k > 0) {
    return std::to_string(k);
  }
  return std::string("neg");
}
struct P {
  int a;
  int b;
};
P make(int x) {
  if (x) return {x, x};
  return P{};
}
}  // namespace toy

namespace toy {
struct Res {
  bool ok;
  const char *why;
};
std::pair<Res, int> classify(int x) {
  if (x > 0) return {Res{true, "positive"}, x};
  if (x == 0) {
    return {Res{false, "zero"}, 0};
  }
  return std::make_pair(Res{false, "negative"}, -x);
}
}  // namespace toy

namespace toy {
using IntVec = std::vector<int>;
IntVec repeat(int n) {
  if (n <= 0) return {};
  return {n, n};
}
}  // namespace toy

int count;
void f(int x) {
  if (x > 10)
    count++;
  if (x > 20) {
    count += 2;
  } else if (x > 15) {
    count += 3;
  } else {
  }
}

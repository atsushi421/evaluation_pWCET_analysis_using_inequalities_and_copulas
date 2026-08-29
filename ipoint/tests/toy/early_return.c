int classify(int x) {
  if (x < 0)
    return -1;
  if (x == 0) {
    return 0;
  }
  return x * 2 + classify(x - 1) % 3;
}
void nothing(int x) {
  if (x)
    return;
  x++;
}

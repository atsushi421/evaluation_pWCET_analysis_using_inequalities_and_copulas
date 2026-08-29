int s;
int g(int n) {
  int i = 0;
  while (i < n) {
    i++;
    if (i % 2)
      continue;
    if (i > 6)
      break;
    s += i;
  }
  do {
    s--;
  } while (s > 0);
  return s;
}

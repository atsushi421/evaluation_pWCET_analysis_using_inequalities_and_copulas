int r;
int chain(int a, int b) {
  if (a > b)
    r = 1;
  else if (a == b)
    r = 2;
  else
    r = 3;
  return r;
}

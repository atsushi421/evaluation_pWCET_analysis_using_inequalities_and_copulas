int t;
void h(int n) {
  int i;
  for (i = 1; i <= n - 1; i++) t += i;
  if (n) for (i = 0; i < 2; i++) t--;
  else t = 0;
}

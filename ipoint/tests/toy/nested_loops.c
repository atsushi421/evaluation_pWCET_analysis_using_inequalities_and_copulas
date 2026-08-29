#define N 3
#define M 4
int acc;
void nested(int *a) {
  int i, j;
  for (i = 0; i < N; i++) {
    for (j = 0; j < M; j++)
      acc += a[i * M + j];
    acc++;
  }
}

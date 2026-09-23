#define _GNU_SOURCE
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sched.h>
#include <x86intrin.h>
#include "bench_rng.h"
#define N 100
extern int Array[];
void BubbleSort(int Array[]);
static int cmpd(const void*a,const void*b){int x=*(int*)a,y=*(int*)b;return (x<y)-(x>y);}
static int cmpa(const void*a,const void*b){int x=*(int*)a,y=*(int*)b;return (x>y)-(x<y);}
static void gen(int type, uint64_t seed){
  bench_rng_t r; rng_seed(&r, seed);
  for(int i=1;i<=N;i++) Array[i]=(int)(uint32_t)rng_next(&r);
  if(type==1) qsort(&Array[1],N,sizeof(int),cmpd);           /* descending */
  if(type==2) for(int i=1;i<=N;i++) Array[i]=N-i;              /* descending constants */
  if(type==3){ int m=1; for(int i=2;i<=N;i++) if(Array[i]<Array[m]) m=i; int t=Array[m]; memmove(&Array[m],&Array[m+1],(N-m)*sizeof(int)); Array[N]=t; } /* min last */
  if(type==4){ qsort(&Array[1],N,sizeof(int),cmpa); }          /* ascending */
  if(type==5){ /* descending with random adjacent perturbation: half pairs swapped */
    qsort(&Array[1],N,sizeof(int),cmpd); for(int i=1;i<N;i+=2) if(rng_next(&r)&1){int t=Array[i];Array[i]=Array[i+1];Array[i+1]=t;} }
}
int main(int argc,char**argv){
  int core=atoi(argv[1]); cpu_set_t s; CPU_ZERO(&s); CPU_SET(core,&s); sched_setaffinity(0,sizeof s,&s);
  const char*names[]={"random","desc(sorted rnd)","desc(consts)","random+min last","ascending","desc+half adj swaps"};
  for(int type=0;type<6;type++){
    enum{R=20000}; static uint64_t t[R];
    for(int w=0;w<1000;w++){gen(type,w+999999);BubbleSort(Array);}
    for(int r=0;r<R;r++){ gen(type,r); unsigned a; uint64_t t0=__rdtscp(&a); _mm_lfence(); BubbleSort(Array); uint64_t t1=__rdtscp(&a); _mm_lfence(); t[r]=t1-t0; }
    int c(const void*a,const void*b){uint64_t x=*(uint64_t*)a,y=*(uint64_t*)b;return (x>y)-(x<y);}
    qsort(t,R,8,c);
    printf("%-22s median %7lu  p99 %7lu  max %7lu ticks\n",names[type],t[R/2],t[R*99/100],t[R-1]);
  }
}

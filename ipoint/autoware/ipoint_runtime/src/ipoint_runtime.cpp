// The single translation unit that defines the IPoint per-thread state and the
// job-mode file output (see ipoint.h). Linked by every instrumented package.
#define IPOINT_IMPLEMENTATION
#include "ipoint.h"

extern "C" const char *ipoint_runtime_build_id(void) {
#ifdef IPOINT_BUILD_ID
  return IPOINT_BUILD_ID;
#else
  return "";
#endif
}

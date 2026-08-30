cmake_minimum_required(VERSION 3.14)
project(ipoint_runtime C CXX)

find_package(ament_cmake REQUIRED)
find_package(Threads REQUIRED)

# IPOINT_MODE is a PUBLIC definition: every package that links ipoint_runtime
# compiles its probes in the same mode (TIMING, COVERAGE or OFF).
set(IPOINT_MODE "TIMING" CACHE STRING "TIMING | COVERAGE | OFF")
set(IPOINT_BUILD_ID "" CACHE STRING "free-form identifier recorded in the library (git describe of the patch set)")

add_library(ipoint_runtime SHARED src/ipoint_runtime.cpp)
target_include_directories(ipoint_runtime PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>)
target_compile_definitions(ipoint_runtime PUBLIC IPOINT_MODE_${IPOINT_MODE})
target_compile_definitions(ipoint_runtime PRIVATE IPOINT_BUILD_ID="${IPOINT_BUILD_ID}")
target_compile_features(ipoint_runtime PUBLIC cxx_std_17)
target_link_libraries(ipoint_runtime PUBLIC Threads::Threads)

install(TARGETS ipoint_runtime EXPORT export_ipoint_runtime
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin)
install(DIRECTORY include/ DESTINATION include)

ament_export_targets(export_ipoint_runtime HAS_LIBRARY_TARGET)
ament_export_include_directories(include)
ament_export_libraries(ipoint_runtime)
ament_export_definitions(IPOINT_MODE_${IPOINT_MODE})
ament_package()

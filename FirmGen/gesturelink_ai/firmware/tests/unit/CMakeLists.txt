cmake_minimum_required(VERSION 3.16)
project(gesture_service_acceptance C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_executable(gesture_service_acceptance
    gesture_service_acceptance.c
    ../../services/gesture_service.c
)

target_include_directories(gesture_service_acceptance PRIVATE
    ../../interfaces
    ../../services
    ../../configs
    ../../bsp
)

target_compile_options(gesture_service_acceptance PRIVATE -Wall -Wextra -Wpedantic -Wconversion -Wsign-conversion -Wshadow -Wundef -Wformat=2)
enable_testing()
add_test(NAME gesture_service_acceptance COMMAND gesture_service_acceptance)

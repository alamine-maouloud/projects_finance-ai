cmake_minimum_required(VERSION 3.14)
project(montecarlo CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_executable(pricer
    src/main.cpp
    src/black_scholes.cpp
    src/greeks.cpp
    src/monte_carlo.cpp
)

target_include_directories(pricer PRIVATE src)

target_compile_options(pricer PRIVATE -O2 -Wall -Wextra)

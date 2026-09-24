CXX ?= c++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Isrc

all: pricer

pricer: src/main.cpp src/black_scholes.cpp src/greeks.cpp src/monte_carlo.cpp
	$(CXX) $(CXXFLAGS) $^ -o $@

clean:
	rm -f pricer

.PHONY: all clean

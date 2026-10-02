#include <iostream>
#include <numeric>
#include <vector>

int main() {
    const std::vector<int> values{3, 5, 8, 13, 21};
    std::cout << "LUMEN | C++17 task\n";
    std::cout << "Sum: " << std::accumulate(values.begin(), values.end(), 0) << '\n';
}

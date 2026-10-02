#include "lumen_core.h"
size_t lumen_count_newlines(const unsigned char *data, size_t size) {
    size_t count = 0;
    if (!data) return 0;
    for (size_t i = 0; i < size; ++i) count += data[i] == '\n';
    return count;
}

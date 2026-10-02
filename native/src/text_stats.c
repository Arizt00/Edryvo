#include "lumen_core.h"

/* Line count matches an editor: even an empty document has one line. */
size_t lumen_line_count(const unsigned char *data, size_t size) {
    return (data && size ? lumen_count_newlines(data, size) : 0) + 1;
}
size_t lumen_ascii_words(const unsigned char *data, size_t size) {
    size_t words = 0;
    int inside = 0;
    if (!data) return 0;
    for (size_t i = 0; i < size; ++i) {
        const unsigned char c = data[i];
        const int space = c == ' ' || c == '\t' || c == '\r' || c == '\n' || c == '\v' || c == '\f';
        if (!space && !inside) ++words;
        inside = !space;
    }
    return words;
}
const char *lumen_backend_name(void) {
#if LUMEN_HAS_ASM
    return "C + C++ + ASM x86-64";
#else
    return "C + C++ (portable C counter)";
#endif
}

#include "lumen_core.h"
#include <cctype>
#include <cstring>

/* Deterministic ASCII-insensitive subsequence ranking; -1 means no match. */
int lumen_fuzzy_score(const char *query, const char *candidate) {
    if (!query || !candidate) return -1;
    const size_t qn = std::strlen(query), cn = std::strlen(candidate);
    if (qn == 0) return 0;
    if (qn > cn || cn > 65536) return -1;
    size_t qi = 0;
    int score = 0, previous = -2;
    for (size_t ci = 0; ci < cn && qi < qn; ++ci) {
        const auto a = static_cast<unsigned char>(query[qi]);
        const auto b = static_cast<unsigned char>(candidate[ci]);
        if (std::tolower(a) != std::tolower(b)) continue;
        score += 10;
        if (static_cast<int>(ci) == previous + 1) score += 8;
        if (ci == 0 || candidate[ci - 1] == '/' || candidate[ci - 1] == '_' || candidate[ci - 1] == '-') score += 12;
        previous = static_cast<int>(ci);
        ++qi;
    }
    if (qi != qn) return -1;
    const int ranked = score - static_cast<int>(cn - qn);
    return ranked > 0 ? ranked : 0;
}

#ifndef LUMEN_CORE_H
#define LUMEN_CORE_H
#include <stddef.h>
#include <stdint.h>
#ifdef _WIN32
#define LUMEN_API __declspec(dllexport)
#else
#define LUMEN_API __attribute__((visibility("default")))
#endif
#ifdef __cplusplus
extern "C" {
#endif
LUMEN_API size_t lumen_count_newlines(const unsigned char *data, size_t size);
LUMEN_API size_t lumen_line_count(const unsigned char *data, size_t size);
LUMEN_API size_t lumen_ascii_words(const unsigned char *data, size_t size);
LUMEN_API int lumen_fuzzy_score(const char *query, const char *candidate);
LUMEN_API const char *lumen_backend_name(void);
#ifdef __cplusplus
}
#endif
#endif

/* Cooperative Lens: values are observations, expressions are evaluated once.
   Call from a single owner thread; serialize concurrent writers in your program. */
#ifndef LUMEN_LANTERN_LENS_H
#define LUMEN_LANTERN_LENS_H
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include <windows.h>
#endif
typedef struct { int line; char value[501],label[81]; } lumen_lens_item;
static lumen_lens_item lumen_lens_items[200];
static int lumen_lens_count=0;
static inline void lumen_lens_quote(FILE *f,const char *s){
    fputc('"',f);for(const unsigned char *p=(const unsigned char*)s;*p;p++){
        if(*p=='"'||*p=='\\'){fputc('\\',f);fputc(*p,f);}
        else if(*p<32)fprintf(f,"\\u%04x",*p);else fputc(*p,f);
    }fputc('"',f);
}
static inline void lantern_lens_text(int line,const char *label,const char *value){
    const char *path=getenv("LUMEN_LANTERN_LENS"),*generation=getenv("LUMEN_LANTERN_GENERATION");
    if(!path||!generation||line<1)return;
    int index=0;while(index<lumen_lens_count&&lumen_lens_items[index].line!=line)index++;
    if(index==200)return;if(index==lumen_lens_count)lumen_lens_count++;
    lumen_lens_item *item=&lumen_lens_items[index];item->line=line;
    snprintf(item->label,sizeof(item->label),"%s",label?label:"");snprintf(item->value,sizeof(item->value),"%s",value?value:"null");
    char tmp[8192];if(snprintf(tmp,sizeof(tmp),"%s.native-tmp",path)>=(int)sizeof(tmp))return;
    FILE *f=fopen(tmp,"wb");if(!f)return;
    fputs("{\"generation\":",f);lumen_lens_quote(f,generation);fputs(",\"values\":[",f);
    for(int i=0;i<lumen_lens_count;i++){if(i)fputc(',',f);fprintf(f,"{\"line\":%d,\"label\":",lumen_lens_items[i].line);lumen_lens_quote(f,lumen_lens_items[i].label);fputs(",\"value\":",f);lumen_lens_quote(f,lumen_lens_items[i].value);fputc('}',f);}
    fputs("]}",f);if(fclose(f))return;
#ifdef _WIN32
    MoveFileExA(tmp,path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
#else
    rename(tmp,path);
#endif
}
static inline double lantern_lens_number(int line,const char *label,double value){char text[64];snprintf(text,sizeof(text),"%.17g",value);lantern_lens_text(line,label,text);return value;}
#define LANTERN_LENS_NUMBER(value) lantern_lens_number(__LINE__,#value,(double)(value))
#define LANTERN_LENS_TEXT(value) lantern_lens_text(__LINE__,#value,(value))
#endif

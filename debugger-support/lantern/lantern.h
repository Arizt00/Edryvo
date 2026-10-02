/* Lantern cooperative state v1. C11 / C++17. No heap pointers or OS handles in saved structs.
   Include this file and call lantern_checkpoint at a consistent point in your program.
   Return codes: 1 restored/saved, 0 new state, -1 I/O, -2 schema/size mismatch, -3 corrupt.
   Schema must change whenever field order, type, alignment or meaning changes. */
#ifndef LUMEN_LANTERN_H
#define LUMEN_LANTERN_H
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#ifdef _WIN32
#include <windows.h>
#include <io.h>
#else
#include <unistd.h>
#endif
#define LANTERN_MAX_STATE 1048576u
typedef struct { uint64_t magic, schema, size, checksum; } lantern_header;
typedef int (*lantern_migration)(uint64_t old_schema,const void *old_data,size_t old_size,void *new_data,size_t new_size);
static inline uint64_t lantern_hash(const void *data,size_t size){const unsigned char *p=(const unsigned char*)data;uint64_t h=UINT64_C(14695981039346656037);while(size--){h^=*p++;h*=UINT64_C(1099511628211);}return h;}
static inline int lantern_path(char *path,size_t size,const char *suffix){const char *base=getenv("LUMEN_LANTERN_STATE");if(!base||!*base)return -1;int n=snprintf(path,size,"%s%s",base,suffix);return n<0||(size_t)n>=size?-1:1;}
static inline int lantern_checkpoint(const void *state,size_t size,uint64_t schema){
    char path[8192],temp[8192];if(!size||size>LANTERN_MAX_STATE||lantern_path(path,sizeof(path),".native")<0||lantern_path(temp,sizeof(temp),".native.tmp")<0)return -1;
    FILE *file=fopen(temp,"wb");if(!file)return -1;
    lantern_header h={UINT64_C(0x4c554d454e4c4e31),schema,(uint64_t)size,lantern_hash(state,size)};
    int ok=fwrite(&h,sizeof(h),1,file)==1&&fwrite(state,size,1,file)==1;
    if(fflush(file)!=0)ok=0;
#ifndef _WIN32
    if(fsync(fileno(file))!=0)ok=0;
#else
    if(_commit(_fileno(file))!=0)ok=0;
#endif
    if(fclose(file)!=0)ok=0;
    if(!ok)return -1;
#ifdef _WIN32
    int moved=0;
    for(int attempt=0;attempt<30;attempt++){
        if(MoveFileExA(temp,path,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH)){moved=1;break;}
        DWORD error=GetLastError();if(error!=ERROR_SHARING_VIOLATION&&error!=ERROR_ACCESS_DENIED)break;
        Sleep(10);
    }
    if(!moved)return -1;
#else
    if(rename(temp,path)!=0)return -1;
#endif
    return 1;
}
static inline int lantern_restore(void *state,size_t size,uint64_t schema,lantern_migration migrate){
    char path[8192];if(!size||size>LANTERN_MAX_STATE||lantern_path(path,sizeof(path),".native")<0)return -1;
    FILE *file=fopen(path,"rb");if(!file){
        if(errno!=ENOENT)return -1;
        memset(state,0,size);return 0;
    }
    lantern_header h;if(fread(&h,sizeof(h),1,file)!=1||h.magic!=UINT64_C(0x4c554d454e4c4e31)||!h.size||h.size>LANTERN_MAX_STATE){fclose(file);return -3;}
    void *old=malloc((size_t)h.size);if(!old){fclose(file);return -1;}
    int ok=fread(old,(size_t)h.size,1,file)==1&&fgetc(file)==EOF;fclose(file);
    if(!ok||h.checksum!=lantern_hash(old,(size_t)h.size)){free(old);return -3;}
    if(h.schema!=schema||h.size!=size){
        if(!migrate){free(old);return -2;}
        void *next=calloc(1,size);if(!next){free(old);return -1;}
        ok=migrate(h.schema,old,(size_t)h.size,next,size);free(old);
        if(!ok){free(next);return -2;}
        ok=lantern_checkpoint(next,size,schema);if(ok==1)memcpy(state,next,size);free(next);return ok;
    }
    memcpy(state,old,size);free(old);return 1;
}
/* Call at a safe point in a long-running loop. 1 means saved: exit the loop.
   Lantern waits for this acknowledgement before starting the next revision. */
static inline int lantern_reload_requested(void){
    char path[8192];if(lantern_path(path,sizeof(path),".reload")<0)return 0;
    FILE *file=fopen(path,"rb");if(!file)return 0;fclose(file);return 1;
}
static inline int lantern_poll(const void *state,size_t size,uint64_t schema){
    return lantern_reload_requested()?lantern_checkpoint(state,size,schema):0;
}
#endif

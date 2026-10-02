#include "lantern.h"
typedef struct { int count; double total; } State;
int main(void) {
    State state;
    int status=lantern_restore(&state,sizeof(state),1,NULL);
    if(status<0){fprintf(stderr,"Lantern restore error %d\n",status);return 1;}
    state.count++; state.total+=2.5;
    if(lantern_checkpoint(&state,sizeof(state),1)<0)return 2;
    printf("LANTERN_NATIVE %d %.1f\n",state.count,state.total);
    return 0;
}

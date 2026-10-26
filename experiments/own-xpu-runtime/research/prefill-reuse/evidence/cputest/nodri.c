#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
static int blocked(const char* p){return p&&(strncmp(p,"/dev/dri",8)==0||strncmp(p,"/sys/class/drm",14)==0||strstr(p,"renderD")!=NULL);}
static void note(const char* p){fprintf(stderr,"[nodri] blocked %s\n",p);}
#define WRAP(name) \
int name(const char* p,int f,...){static int(*real)(const char*,int,...)=0;if(!real)real=dlsym(RTLD_NEXT,#name);if(blocked(p)){note(p);errno=ENOENT;return -1;}va_list a;va_start(a,f);mode_t m=va_arg(a,int);va_end(a);return real(p,f,m);}
WRAP(open) WRAP(open64)
int openat(int d,const char* p,int f,...){static int(*real)(int,const char*,int,...)=0;if(!real)real=dlsym(RTLD_NEXT,"openat");if(blocked(p)){note(p);errno=ENOENT;return -1;}va_list a;va_start(a,f);mode_t m=va_arg(a,int);va_end(a);return real(d,p,f,m);}
int openat64(int d,const char* p,int f,...){static int(*real)(int,const char*,int,...)=0;if(!real)real=dlsym(RTLD_NEXT,"openat64");if(blocked(p)){note(p);errno=ENOENT;return -1;}va_list a;va_start(a,f);mode_t m=va_arg(a,int);va_end(a);return real(d,p,f,m);}

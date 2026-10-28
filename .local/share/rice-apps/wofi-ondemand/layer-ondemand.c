// LD_PRELOAD for swaync (notification panel): keyboard "on demand" instead of "exclusive" – same reason as in
// wofi-ondemand.c (an exclusive layer gets ALL mouse clicks from Hyprland, so a click on another waybar icon
// would only close the panel). Without GTK, and the variable is removed again so started programs do not inherit it.
// Build: gcc -shared -fPIC -O2 -o layer-ondemand.so layer-ondemand.c
#define _GNU_SOURCE
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <wayland-client-core.h>
#include <wayland-util.h>

#define SET_KEYBOARD_INTERACTIVITY 4
#define ON_DEMAND 2
#define MAX_ARGS 20

__attribute__((constructor)) static void init(void) { unsetenv("LD_PRELOAD"); }

static void collect(struct wl_proxy *proxy, uint32_t opcode, union wl_argument *args, va_list ap) {
    const struct wl_interface *pi = *(const struct wl_interface **)proxy;
    const char *sig = pi->methods[opcode].signature;
    int n = 0;
    for (const char *c = sig; *c && n < MAX_ARGS; c++) {
        switch (*c) {
        case 'i': args[n++].i = va_arg(ap, int32_t); break;
        case 'u': args[n++].u = va_arg(ap, uint32_t); break;
        case 'f': args[n++].f = va_arg(ap, wl_fixed_t); break;
        case 's': args[n++].s = va_arg(ap, const char *); break;
        case 'o': case 'n': args[n++].o = va_arg(ap, struct wl_object *); break;
        case 'a': args[n++].a = va_arg(ap, struct wl_array *); break;
        case 'h': args[n++].h = va_arg(ap, int32_t); break;
        default: break;
        }
    }
    if (opcode == SET_KEYBOARD_INTERACTIVITY && strcmp(pi->name, "zwlr_layer_surface_v1") == 0 && args[0].u != 0)
        args[0].u = ON_DEMAND;
}

struct wl_proxy *wl_proxy_marshal_flags(struct wl_proxy *proxy, uint32_t opcode, const struct wl_interface *iface,
                                        uint32_t version, uint32_t flags, ...) {
    union wl_argument args[MAX_ARGS];
    va_list ap;
    va_start(ap, flags);
    collect(proxy, opcode, args, ap);
    va_end(ap);
    return wl_proxy_marshal_array_flags(proxy, opcode, iface, version, flags, args);
}

void wl_proxy_marshal(struct wl_proxy *proxy, uint32_t opcode, ...) {
    union wl_argument args[MAX_ARGS];
    va_list ap;
    va_start(ap, opcode);
    collect(proxy, opcode, args, ap);
    va_end(ap);
    wl_proxy_marshal_array(proxy, opcode, args);
}

struct wl_proxy *wl_proxy_marshal_constructor(struct wl_proxy *proxy, uint32_t opcode, const struct wl_interface *iface, ...) {
    union wl_argument args[MAX_ARGS];
    va_list ap;
    va_start(ap, iface);
    collect(proxy, opcode, args, ap);
    va_end(ap);
    return wl_proxy_marshal_array_constructor(proxy, opcode, args, iface);
}

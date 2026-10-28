// LD_PRELOAD for wofi: keyboard "on demand" instead of "exclusive".
// Reason: as long as a layer holds the keyboard exclusively, Hyprland also sends ALL mouse clicks to
// it. A click on another waybar icon (e.g. bluetooth menu open -> wifi) therefore never reached
// the waybar and only closed the menu. With "on demand" wofi still gets the focus.
// Build: gcc -shared -fPIC -O2 -o wofi-ondemand.so wofi-ondemand.c
#define _GNU_SOURCE
#include <dlfcn.h>
#include <gtk/gtk.h>
#include <stdarg.h>
#include <stdint.h>
#include <string.h>
#include <wayland-client-core.h>
#include <wayland-util.h>

#define SET_KEYBOARD_INTERACTIVITY 4
#define ON_DEMAND 2
#define MAX_ARGS 20

// collect the arguments from the protocol signature (like libwayland does internally) and rewrite if needed
static void collect(struct wl_proxy *proxy, uint32_t opcode, union wl_argument *args, va_list ap) {
    const struct wl_interface *pi = *(const struct wl_interface **)proxy;  // proxy->object.interface
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
        default: break;  // '?' and version digits
        }
    }
    if (opcode == SET_KEYBOARD_INTERACTIVITY && strcmp(pi->name, "zwlr_layer_surface_v1") == 0
        && args[0].u != 0)
        args[0].u = ON_DEMAND;
}

struct wl_proxy *wl_proxy_marshal_flags(struct wl_proxy *proxy, uint32_t opcode,
                                        const struct wl_interface *iface, uint32_t version,
                                        uint32_t flags, ...) {
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

struct wl_proxy *wl_proxy_marshal_constructor(struct wl_proxy *proxy, uint32_t opcode,
                                              const struct wl_interface *iface, ...) {
    union wl_argument args[MAX_ARGS];
    va_list ap;
    va_start(ap, iface);
    collect(proxy, opcode, args, ap);
    va_end(ap);
    return wl_proxy_marshal_array_constructor(proxy, opcode, args, iface);
}

// Hover = Auswahl: Wer mit der Maus über einen Eintrag fährt, markiert ihn (wofi zeigt sonst nur die Tastatur-Auswahl).
// GtkFlowBoxChild hat kein eigenes Fenster und bekommt keine enter-notify-Ereignisse → Bewegung der ganzen Liste auswerten.
static gboolean on_motion(GtkWidget *box, GdkEventMotion *ev, gpointer data) {
    GtkFlowBoxChild *child = gtk_flow_box_get_child_at_pos(GTK_FLOW_BOX(box), (gint)ev->x, (gint)ev->y);
    if (child && !gtk_flow_box_child_is_selected(child))
        gtk_flow_box_select_child(GTK_FLOW_BOX(box), child);
    return FALSE;
}

void gtk_container_add(GtkContainer *container, GtkWidget *widget) {
    static void (*real)(GtkContainer *, GtkWidget *);
    if (!real)
        real = dlsym(RTLD_NEXT, "gtk_container_add");
    real(container, widget);
    if (GTK_IS_FLOW_BOX(container) && GTK_IS_FLOW_BOX_CHILD(widget) && !g_object_get_data(G_OBJECT(container), "ist-hover")) {
        g_object_set_data(G_OBJECT(container), "ist-hover", GINT_TO_POINTER(1));
        gtk_widget_add_events(GTK_WIDGET(container), GDK_POINTER_MOTION_MASK);
        g_signal_connect(container, "motion-notify-event", G_CALLBACK(on_motion), NULL);
    }
}

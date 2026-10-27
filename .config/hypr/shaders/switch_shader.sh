#!/bin/bash
if [ "$1" == "off" ]; then
    hyprctl keyword decoration:screen_shader ~/.config/hypr/shaders/off.glsl
else
    # Şifreyi girdiğin an burası çalışacak
    hyprctl keyword decoration:screen_shader ~/.config/hypr/shaders/vibrance.glsl &
fi

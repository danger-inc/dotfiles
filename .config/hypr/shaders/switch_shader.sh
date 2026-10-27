#!/bin/bash
if [ "$1" == "off" ]; then
    hyprctl keyword decoration:screen_shader ~/.config/hypr/shaders/off.glsl
else
    # runs as soon as the password is entered
    hyprctl keyword decoration:screen_shader ~/.config/hypr/shaders/vibrance.glsl &
fi

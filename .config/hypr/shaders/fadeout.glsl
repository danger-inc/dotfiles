// fadeout.glsl
// cinematic unlock fade shader

uniform float opacity = 1.0;
uniform float fade_time = 2.5; // saniye

out vec4 fragColor;
in vec2 texCoords;
uniform sampler2D tex;

void main() {
    vec4 color = texture(tex, texCoords);
    fragColor = vec4(color.rgb * opacity, color.a);
}

// Fade animasyonu için Hyprland'da animation parametreleri

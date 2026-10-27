#version 330

uniform float time; // Hyprland animasyon zamanı
in vec2 texCoords;
out vec4 fragColor;
uniform sampler2D tex;

void main() {
    vec4 color = texture(tex, texCoords);

    // --- vibrance efekti ---
    float avg = (color.r + color.g + color.b) / 3.0;
    color.rgb = mix(vec3(avg), color.rgb, 1.2); // mevcut vibrance oranı

    // --- fade efekti ---
    float opacity = 1.0 - clamp(time / 2.5, 0.0, 1.0); // 2.5 saniyelik fade
    fragColor = vec4(color.rgb * opacity, color.a);
}

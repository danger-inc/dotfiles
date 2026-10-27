#version 330

// cinematic unlock fade shader
uniform float time; // animasyon için otomatik
in vec2 texCoords;
out vec4 fragColor;
uniform sampler2D tex;

void main() {
    vec4 color = texture(tex, texCoords);

    // fade animation: opacity decreases as time goes 0 → 1
    float opacity = 1.0 - clamp(time / 2.5, 0.0, 1.0); // 2.5 saniye fade
    fragColor = vec4(color.rgb * opacity, color.a);
}

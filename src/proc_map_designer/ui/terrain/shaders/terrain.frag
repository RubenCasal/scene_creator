#version 330 core
in float v_height_norm;
in vec2 v_uv;
in vec3 v_world_pos;
uniform sampler2D u_heightfield;
uniform vec2 u_texel;
uniform float u_max_height;
uniform bool u_show_grid;
uniform float u_grid_spacing;
out vec4 frag_color;

vec3 terrain_normal() {
    float hl = texture(u_heightfield, v_uv + vec2(-u_texel.x, 0)).r * u_max_height;
    float hr = texture(u_heightfield, v_uv + vec2( u_texel.x, 0)).r * u_max_height;
    float hd = texture(u_heightfield, v_uv + vec2(0, -u_texel.y)).r * u_max_height;
    float hu = texture(u_heightfield, v_uv + vec2(0,  u_texel.y)).r * u_max_height;
    return normalize(vec3((hl-hr), 2.0/max(u_max_height, 0.001), (hd-hu)));
}

vec3 height_color(float t) {
    vec3 low  = vec3(0.28, 0.50, 0.22);
    vec3 mid  = vec3(0.52, 0.44, 0.28);
    vec3 high = vec3(0.86, 0.86, 0.86);
    return t < 0.35 ? mix(low,mid,t/0.35) : mix(mid,high,(t-0.35)/0.65);
}

void main() {
    vec3 N = terrain_normal();
    vec3 L = normalize(vec3(0.6, 1.0, 0.4));
    float diffuse = clamp(dot(N, L), 0.0, 1.0) * 0.75 + 0.25;
    vec3 color = height_color(v_height_norm) * diffuse;
    if (u_show_grid) {
        vec2 gmod = mod(v_world_pos.xz, u_grid_spacing);
        if (gmod.x < 0.06 || gmod.y < 0.06)
            color = mix(color, vec3(0.0), 0.3);
    }
    frag_color = vec4(color, 1.0);
}

#version 330 core
layout(location = 0) in vec2 a_position;
layout(location = 1) in vec2 a_uv;
uniform sampler2D u_heightfield;
uniform float u_max_height;
uniform mat4 u_mvp;
out float v_height_norm;
out vec2 v_uv;
out vec3 v_world_pos;
void main() {
    float h = texture(u_heightfield, a_uv).r;
    v_height_norm = h;
    v_uv = a_uv;
    v_world_pos = vec3(a_position.x, h * u_max_height, a_position.y);
    gl_Position = u_mvp * vec4(v_world_pos, 1.0);
}

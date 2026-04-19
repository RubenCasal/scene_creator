#version 330 core
layout(location = 0) in vec2 a_offset;
uniform vec3 u_center;
uniform float u_radius;
uniform mat4 u_mvp;
void main() {
    vec3 pos = vec3(u_center.x + a_offset.x * u_radius, u_center.y, u_center.z + a_offset.y * u_radius);
    gl_Position = u_mvp * vec4(pos, 1.0);
}

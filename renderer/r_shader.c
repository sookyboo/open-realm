#include "r_local.h"

/*
 * Shader language selection only.
 *
 * Default:        GLSL 1.40
 * -DBZ_GLSL_120: GLSL 1.20 / gl4es
 *
 * Everything else in this file remains the pre-patch implementation.
 */
#ifdef BZ_GLSL_120
#define BZ_SHADER_VERSION "#version 120\n"
#define BZ_VS_IN "attribute"
#define BZ_VS_OUT "varying"
#define BZ_FS_IN "varying"
#define BZ_FS_OUT ""
#define BZ_FS_COMPAT "#define BZ_TEXTURE texture2D\n#define BZ_FRAGCOLOR gl_FragColor\n"
#define BZ_TEXTURE "texture2D"
#define BZ_FRAGCOLOR "gl_FragColor"
#else
#define BZ_SHADER_VERSION "#version 140\n"
#define BZ_VS_IN "in"
#define BZ_VS_OUT "out"
#define BZ_FS_IN "in"
#define BZ_FS_OUT "out vec4 o_color;\n"
#define BZ_FS_COMPAT "#define BZ_TEXTURE texture\n#define BZ_FRAGCOLOR o_color\n"
#define BZ_TEXTURE "texture"
#define BZ_FRAGCOLOR "o_color"
#endif


LPCSTR vs_default =
BZ_SHADER_VERSION
BZ_VS_IN " vec3 i_position;\n"
BZ_VS_IN " vec2 i_texcoord;\n"
BZ_VS_IN " vec3 i_normal;\n"
BZ_VS_IN " vec4 i_color;\n"
#ifdef USE_SHADOWMAPS
BZ_VS_OUT " vec4 v_shadow;\n"
#endif
BZ_VS_OUT " vec2 v_texcoord;\n"
BZ_VS_OUT " vec2 v_texcoord2;\n"
BZ_VS_OUT " vec3 v_normal;\n"
BZ_VS_OUT " vec3 v_lightDir;\n"
BZ_VS_OUT " vec4 v_color;\n"
"uniform mat4 uViewProjectionMatrix;\n"
"uniform mat4 uTextureMatrix;\n"
"uniform mat4 uModelMatrix;\n"
"uniform mat4 uLightMatrix;\n"
"uniform mat3 uNormalMatrix;\n"
"void main() {\n"
"    vec4 pos = uModelMatrix * vec4(i_position, 1.0);"
"    v_texcoord = i_texcoord;\n"
"    v_texcoord2 = (uTextureMatrix * pos).xy;\n"
"    v_normal = normalize(uNormalMatrix * i_normal);\n"
#ifdef USE_SHADOWMAPS
"    v_shadow = uLightMatrix * pos;\n"
#endif
"    v_color = i_color;\n"
"    v_lightDir = -normalize(vec3(uLightMatrix[0][2], uLightMatrix[1][2], uLightMatrix[2][2]))*1.2;\n"
"    gl_Position = uViewProjectionMatrix * uModelMatrix * vec4(i_position, 1.0);\n"
"}\n";

LPCSTR fs_default =
BZ_SHADER_VERSION
BZ_FS_COMPAT
BZ_FS_IN " vec2 v_texcoord;\n"
BZ_FS_IN " vec2 v_texcoord2;\n"
#ifdef USE_SHADOWMAPS
BZ_FS_IN " vec4 v_shadow;\n"
#endif
BZ_FS_IN " vec3 v_normal;\n"
BZ_FS_IN " vec4 v_color;\n"
BZ_FS_IN " vec3 v_lightDir;\n"
BZ_FS_OUT
"uniform sampler2D uTexture;\n"
#if defined(USE_SHADOWMAPS) || defined(DEBUG_PATHFINDING)
"uniform sampler2D uShadowmap;\n"
#endif
"uniform sampler2D uFogOfWar;\n"
"float get_light() {\n"
"    return dot(v_normal, v_lightDir);\n"
"}\n"
#ifdef USE_SHADOWMAPS
"float get_shadow() {\n"
"    float depth = BZ_TEXTURE(uShadowmap, vec2(v_shadow.x + 1.0, v_shadow.y + 1.0) * 0.5).r;\n"
"    return depth < (v_shadow.z + 0.99) * 0.5 ? 0.0 : 1.0;\n"
"}\n"
#endif
"float get_lighting() {\n"
#ifdef USE_SHADOWMAPS
"    return min(1.0, mix(0.35, 1.0, get_shadow() * get_light()) * 1.1);"
#else
"    return min(1.0, mix(0.35, 1.0, get_light()) * 1.1);"
#endif
"}\n"
"float get_fogofwar() {\n"
"    return BZ_TEXTURE(uFogOfWar, v_texcoord2).r;\n"
"}\n"
"void main() {\n"
#ifdef DEBUG_PATHFINDING
"    vec4 debug = BZ_TEXTURE(uShadowmap, v_texcoord2);\n"
"    vec4 color = BZ_TEXTURE(uTexture, v_texcoord);\n"
"    float sin_factor = sin(debug.g * 3.14159 * 2.0);\n"
"    float cos_factor = cos(debug.g * 3.14159 * 2.0);\n"
"    vec2 tc = fract(v_texcoord2 * 384.0);\n"
"    tc = (tc - 0.5) * mat2(cos_factor, sin_factor, -sin_factor, cos_factor);\n"
"    tc += 0.5;\n"
"    float stp = step(abs(0.5 - tc.y), tc.x * 0.25);"
"    /*debug.a = color.a*/;\n"
"    BZ_FRAGCOLOR = debug * 0.7;// mix(debug, color, 0.5) + vec4(stp);\n"
"    return;\n"
#endif
"    vec4 col = BZ_TEXTURE(uTexture, v_texcoord) * v_color;\n"
#ifdef WOW
"    BZ_FRAGCOLOR = col;\n"
#else
"    col.rgb *= get_fogofwar() * get_lighting();\n"
"    BZ_FRAGCOLOR = col;\n"
#endif
"}\n";

LPCSTR fs_ui =
BZ_SHADER_VERSION
BZ_FS_COMPAT
BZ_FS_IN " vec4 v_color;\n"
BZ_FS_IN " vec2 v_texcoord;\n"
BZ_FS_OUT
"uniform sampler2D uTexture;\n"
"void main() {\n"
"    BZ_FRAGCOLOR = BZ_TEXTURE(uTexture, v_texcoord) * v_color;\n"
"}\n";

LPCSTR fs_splat =
BZ_SHADER_VERSION
BZ_FS_COMPAT
BZ_FS_IN " vec4 v_color;\n"
BZ_FS_IN " vec2 v_texcoord;\n"
BZ_FS_OUT
"uniform sampler2D uTexture;\n"
"float crop_edges(vec2 tc) {\n"
"   return step(abs(tc.x - 0.5), 0.5) * step(abs(tc.y - 0.5), 0.5);\n"
"}\n"
"void main() {\n"
"    BZ_FRAGCOLOR = BZ_TEXTURE(uTexture, v_texcoord) * v_color;\n"
"    BZ_FRAGCOLOR.a *= crop_edges(v_texcoord);\n"
"}\n";

LPCSTR fs_shadow_splat =
BZ_SHADER_VERSION
BZ_FS_COMPAT
BZ_FS_IN " vec4 v_color;\n"
BZ_FS_IN " vec2 v_texcoord;\n"
BZ_FS_OUT
"uniform sampler2D uTexture;\n"
"float crop_edges(vec2 tc) {\n"
"   return step(abs(tc.x - 0.5), 0.5) * step(abs(tc.y - 0.5), 0.5);\n"
"}\n"
"void main() {\n"
"    vec4 tex = BZ_TEXTURE(uTexture, v_texcoord);\n"
"    BZ_FRAGCOLOR = vec4(0.0, 0.0, 0.0, tex.a * v_color.a * crop_edges(v_texcoord));\n"
"}\n";

LPCSTR fs_commandbutton =
BZ_SHADER_VERSION
BZ_FS_COMPAT
BZ_FS_IN " vec4 v_color;\n"
BZ_FS_IN " vec2 v_texcoord;\n"
BZ_FS_OUT
"uniform sampler2D uTexture;\n"
"uniform float uActiveGlow;\n"
"float crop_edges(vec2 tc) {\n"
"   return step(abs(tc.x - 0.5), 0.5) * step(abs(tc.y - 0.5), 0.5);\n"
"}\n"
"void main() {\n"
"    BZ_FRAGCOLOR = BZ_TEXTURE(uTexture, v_texcoord) * v_color;\n"
"    float glow = max(abs(v_texcoord.x - 0.5), abs(v_texcoord.y - 0.5));\n"
"    glow = smoothstep(0.33, 0.5, glow) * 0.75 * uActiveGlow;\n"
"    BZ_FRAGCOLOR.rgb = mix(BZ_FRAGCOLOR.rgb,vec3(0.5,1.0,0.5),glow);\n"
"    BZ_FRAGCOLOR.a *= crop_edges(v_texcoord);\n"
"}\n";

LPCSTR fs_minimap_fog =
BZ_SHADER_VERSION
BZ_FS_COMPAT
BZ_FS_IN " vec4 v_color;\n"
BZ_FS_IN " vec2 v_texcoord;\n"
BZ_FS_OUT
"uniform sampler2D uTexture;\n"
"void main() {\n"
"    float visibility = BZ_TEXTURE(uTexture, vec2(v_texcoord.x, 1.0 - v_texcoord.y)).r;\n"
"    float alpha = clamp(1.0 - visibility, 0.0, 1.0) * v_color.a;\n"
"    BZ_FRAGCOLOR = vec4(v_color.rgb, alpha);\n"
"}\n";

static LPCSTR model_vs =
BZ_SHADER_VERSION
BZ_VS_IN " vec3 i_position;\n"
BZ_VS_IN " vec4 i_color;\n"
BZ_VS_IN " vec2 i_texcoord;\n"
BZ_VS_IN " vec3 i_normal;\n"
BZ_VS_IN " vec4 i_skin1;\n"
BZ_VS_IN " vec4 i_boneWeight1;\n"
BZ_VS_OUT " vec4 v_color;\n"
#ifdef USE_SHADOWMAPS
BZ_VS_OUT " vec4 v_shadow;\n"
#endif
BZ_VS_OUT " vec2 v_texcoord;\n"
BZ_VS_OUT " vec2 v_texcoord2;\n"
BZ_VS_OUT " vec3 v_lighting;\n"
"uniform mat4 uBones[128];\n"
"uniform mat4 uViewProjectionMatrix;\n"
"uniform mat4 uModelMatrix;\n"
"uniform mat4 uLightMatrix;\n"
"uniform mat3 uNormalMatrix;\n"
"uniform mat4 uTextureMatrix;\n"
"uniform vec3 uLightDir;\n"
"uniform vec3 uLightColor;\n"
"uniform vec3 uLightAmbient;\n"
"uniform int uLightCount;\n"
"uniform float uFirstBoneLookupIndex;\n"
"uniform mat4 uLights[8];\n"
"const int MODEL_LIGHT_OMNI = 0;\n"
"const int MODEL_LIGHT_DIRECT = 1;\n"
"const int MODEL_LIGHT_AMBIENT = 2;\n"
"vec3 vertex_lighting(vec3 normal, vec3 worldPos) {\n"
"    vec3 n = normalize(normal);\n"
"    if (uLightCount == 0)\n"
"        return uLightAmbient + uLightColor * max(dot(n, normalize(uLightDir)), 0.0);\n"
"    vec3 lighting = uLightAmbient;\n"
"    for (int i = 0; i < 8; ++i) {\n"
"        if (i >= uLightCount) break;\n"
"        vec4 positionType = uLights[i][0];\n"
"        vec4 direction = uLights[i][1];\n"
"        vec4 colorIntensity = uLights[i][2];\n"
"        vec4 ambientIntensity = uLights[i][3];\n"
"        int type = int(positionType.w + 0.5);\n"
"        vec3 color = colorIntensity.rgb * colorIntensity.a;\n"
"        vec3 ambient = ambientIntensity.rgb * ambientIntensity.a;\n"
"        if (type == MODEL_LIGHT_AMBIENT) {\n"
"            lighting += color + ambient;\n"
"        } else if (type == MODEL_LIGHT_DIRECT) {\n"
"            vec3 l = normalize(-direction.xyz);\n"
"            lighting += clamp(color * max(dot(n, l), 0.0), vec3(0.0), vec3(1.0)) + ambient;\n"
"        } else {\n"
"            vec3 delta = positionType.xyz - worldPos;\n"
"            vec3 l = normalize(delta);\n"
"            float dist = length(delta) / 64.0 + 1.0;\n"
"            float atten = 1.0 / (dist * dist);\n"
"            lighting += clamp(color * atten * max(dot(n, l), 0.0), vec3(0.0), vec3(1.0));\n"
"            lighting += ambient * atten;\n"
"        }\n"
"    }\n"
"    return min(lighting, vec3(1.0));\n"
"}\n"
"void main() {\n"
"    vec4 pos4 = vec4(i_position, 1.0);\n"
"    vec4 norm4 = vec4(i_normal, 0.0);\n"
"    vec4 position = vec4(0.0);\n"
"    vec4 normal = vec4(0.0);\n"
"    for (int i = 0; i < 4; ++i) {\n"
"        int boneIdx = int(i_skin1[i]) + int(uFirstBoneLookupIndex);\n"
"        position += uBones[boneIdx] * pos4 * i_boneWeight1[i];\n"
"        normal += uBones[boneIdx] * norm4 * i_boneWeight1[i];\n"
"    }\n"
"    position.w = 1.0;\n"
"    v_color = i_color;\n"
"    v_texcoord = i_texcoord;\n"
"    v_texcoord2 = (uTextureMatrix * uModelMatrix * position).xy;\n"
"    vec3 worldNormal = normalize(uNormalMatrix * normal.xyz);\n"
"    vec3 worldPos = (uModelMatrix * position).xyz;\n"
"    v_lighting = vertex_lighting(worldNormal, worldPos);\n"
#ifdef USE_SHADOWMAPS
"    v_shadow = uLightMatrix * uModelMatrix * position;\n"
#endif
"    gl_Position = uViewProjectionMatrix * uModelMatrix * position;\n"
"}\n";

static LPCSTR model_fs =
BZ_SHADER_VERSION
BZ_FS_COMPAT
BZ_FS_IN " vec2 v_texcoord;\n"
BZ_FS_IN " vec2 v_texcoord2;\n"
#ifdef USE_SHADOWMAPS
BZ_FS_IN " vec4 v_shadow;\n"
#endif
BZ_FS_IN " vec3 v_lighting;\n"
BZ_FS_IN " vec4 v_color;\n"
BZ_FS_OUT
"uniform sampler2D uTexture;\n"
#if defined(USE_SHADOWMAPS) || defined(DEBUG_PATHFINDING)
"uniform sampler2D uShadowmap;\n"
#endif
"uniform sampler2D uFogOfWar;\n"
"uniform float uLayerAlpha;\n"
"uniform vec4 uGeosetColor;\n"
"uniform vec2 uUvTrans;\n"
"uniform vec2 uUvRot;\n"
"uniform vec2 uUvScale;\n"
"uniform bool uAlphaKey;\n"
"uniform float uAlphaCutoff;\n"
"uniform bool uUnshaded;\n"
"uniform bool uFogEnable;\n"
"uniform vec3 uFogColor;\n"
"uniform vec2 uFogParams;\n"
"vec2 quat_transform(vec2 q, vec2 v) {\n"
"    float c = q.y * q.y - q.x * q.x;\n"
"    float s = 2.0 * q.x * q.y;\n"
"    return vec2(v.x * c - v.y * s, v.x * s + v.y * c);\n"
"}\n"
"float get_fogofwar() {\n"
"    return BZ_TEXTURE(uFogOfWar, v_texcoord2).r;\n"
"}\n"
"void main() {\n"
"    vec2 uv = v_texcoord;\n"
"    uv += uUvTrans;\n"
"    uv = quat_transform(uUvRot, uv - 0.5) + 0.5;\n"
"    uv = uUvScale * (uv - 0.5) + 0.5;\n"
"    vec4 col = BZ_TEXTURE(uTexture, uv);\n"
"    col *= uGeosetColor;\n"
"    col *= uLayerAlpha;\n"
"    col *= v_color;\n"
"    if (!uUnshaded) {\n"
"        col.rgb *= get_fogofwar() * v_lighting;\n"
"        if (uFogEnable) {\n"
"            float fogFactor = clamp((uFogParams.y - gl_FragCoord.z / gl_FragCoord.w) / (uFogParams.y - uFogParams.x), 0.0, 1.0);\n"
"            col.rgb = mix(uFogColor, col.rgb, fogFactor);\n"
"        }\n"
"    }\n"
"    if (uAlphaKey) {\n"
#ifdef BZ_GLSL_120
"        if (col.a < uAlphaCutoff) discard;\n"
#else
"        float edge = max(fwidth(col.a), 1.0 / 255.0);\n"
"        col.a = smoothstep(uAlphaCutoff - edge, uAlphaCutoff + edge, col.a);\n"
#endif
"    }\n"
"    BZ_FRAGCOLOR = col;\n"
"}\n";

static LPSHADER model_shader;

/* Returns the shared model shader, compiling it on first call. All three model
   formats (MDX/M2/M3) use this single shader; per-format data is normalised at
   load time so the GPU path is identical. */
LPSHADER R_ModelShader(void) {
    if (!model_shader) {
        model_shader = R_InitShader(model_vs, model_fs);
        if (model_shader) {
            R_Call(glUseProgram, model_shader->progid);
            R_Call(glUniform1f, model_shader->uAlphaCutoff, 0.5f);
        }
    }
    return model_shader ? model_shader : tr.shader[SHADER_DEFAULT];
}

/* Instanced model shader for static meshes (ground-effect clutter). Identical
   skinning/lighting to model_vs, but the per-instance world transform is a
   vertex attribute instead of uModelMatrix so thousands of instances share one
   draw call. */
static LPCSTR instanced_vs =
BZ_SHADER_VERSION
BZ_VS_IN " vec3 i_position;\n"
BZ_VS_IN " vec4 i_color;\n"
BZ_VS_IN " vec2 i_texcoord;\n"
BZ_VS_IN " vec3 i_normal;\n"
BZ_VS_IN " vec4 i_skin1;\n"
BZ_VS_IN " vec4 i_boneWeight1;\n"
BZ_VS_IN " vec4 i_instance0;\n"
BZ_VS_IN " vec4 i_instance1;\n"
BZ_VS_IN " vec4 i_instance2;\n"
BZ_VS_IN " vec4 i_instance3;\n"
BZ_VS_OUT " vec4 v_color;\n"
#ifdef USE_SHADOWMAPS
BZ_VS_OUT " vec4 v_shadow;\n"
#endif
BZ_VS_OUT " vec2 v_texcoord;\n"
BZ_VS_OUT " vec2 v_texcoord2;\n"
BZ_VS_OUT " vec3 v_lighting;\n"
"uniform mat4 uBones[128];\n"
"uniform mat4 uViewProjectionMatrix;\n"
"uniform mat4 uLightMatrix;\n"
"uniform mat4 uTextureMatrix;\n"
"uniform vec3 uLightDir;\n"
"uniform vec3 uLightColor;\n"
"uniform vec3 uLightAmbient;\n"
"uniform int uLightCount;\n"
"uniform float uFirstBoneLookupIndex;\n"
"uniform mat4 uLights[8];\n"
"uniform vec3 uGrassCameraPos;\n"
"uniform vec2 uGrassFade;\n"
"uniform float uGrassTime;\n"
"uniform vec3 uGrassWind;\n"
"uniform vec4 uGrassPhase;\n"
"uniform vec2 uGrassHeight;\n"
"uniform int uGroundEffect;\n"
"const int MODEL_LIGHT_OMNI = 0;\n"
"const int MODEL_LIGHT_DIRECT = 1;\n"
"const int MODEL_LIGHT_AMBIENT = 2;\n"
"vec3 vertex_lighting(vec3 normal, vec3 worldPos) {\n"
"    vec3 n = normalize(normal);\n"
"    if (uLightCount == 0)\n"
"        return uLightAmbient + uLightColor * max(dot(n, normalize(uLightDir)), 0.0);\n"
"    vec3 lighting = uLightAmbient;\n"
"    for (int i = 0; i < 8; ++i) {\n"
"        if (i >= uLightCount) break;\n"
"        vec4 positionType = uLights[i][0];\n"
"        vec4 direction = uLights[i][1];\n"
"        vec4 colorIntensity = uLights[i][2];\n"
"        vec4 ambientIntensity = uLights[i][3];\n"
"        int type = int(positionType.w + 0.5);\n"
"        vec3 color = colorIntensity.rgb * colorIntensity.a;\n"
"        vec3 ambient = ambientIntensity.rgb * ambientIntensity.a;\n"
"        if (type == MODEL_LIGHT_AMBIENT) {\n"
"            lighting += color + ambient;\n"
"        } else if (type == MODEL_LIGHT_DIRECT) {\n"
"            vec3 l = normalize(-direction.xyz);\n"
"            lighting += clamp(color * max(dot(n, l), 0.0), vec3(0.0), vec3(1.0)) + ambient;\n"
"        } else {\n"
"            vec3 delta = positionType.xyz - worldPos;\n"
"            vec3 l = normalize(delta);\n"
"            float dist = length(delta) / 64.0 + 1.0;\n"
"            float atten = 1.0 / (dist * dist);\n"
"            lighting += clamp(color * atten * max(dot(n, l), 0.0), vec3(0.0), vec3(1.0));\n"
"            lighting += ambient * atten;\n"
"        }\n"
"    }\n"
"    return min(lighting, vec3(1.0));\n"
"}\n"
"void main() {\n"
"    vec4 pos4 = vec4(i_position, 1.0);\n"
"    vec4 norm4 = vec4(i_normal, 0.0);\n"
"    vec4 position = vec4(0.0);\n"
"    vec4 normal = vec4(0.0);\n"
"    for (int i = 0; i < 4; ++i) {\n"
"        int boneIdx = int(i_skin1[i]) + int(uFirstBoneLookupIndex);\n"
"        position += uBones[boneIdx] * pos4 * i_boneWeight1[i];\n"
"        normal += uBones[boneIdx] * norm4 * i_boneWeight1[i];\n"
"    }\n"
"    position.w = 1.0;\n"
"    mat4 i_instance = mat4(i_instance0, i_instance1, i_instance2, i_instance3);\n"
"    if (uGroundEffect != 0) {\n"
"        float grassHeight = max(uGrassHeight.y - uGrassHeight.x, 0.001);\n"
"        float grassTop = smoothstep(uGrassWind.z, 1.0, clamp((position.z - uGrassHeight.x) / grassHeight, 0.0, 1.0));\n"
"        float grassPhase = dot(i_instance3.xy, uGrassPhase.xy);\n"
"        float grassSway = sin(uGrassTime * uGrassWind.x + grassPhase) * uGrassWind.y * grassHeight * grassTop;\n"
"        position.xy += uGrassPhase.zw * grassSway;\n"
"    }\n"
"    vec4 worldPos = i_instance * position;\n"
"    v_color = i_color;\n"
"    if (uGroundEffect != 0) {\n"
"        float fadeDist = length(worldPos.xy - uGrassCameraPos.xy);\n"
"        v_color.a *= 1.0 - smoothstep(uGrassFade.x, uGrassFade.y, fadeDist);\n"
"    }\n"
"    v_texcoord = i_texcoord;\n"
"    v_texcoord2 = (uTextureMatrix * worldPos).xy;\n"
"    v_lighting = vertex_lighting(normalize(mat3(i_instance) * normal.xyz), worldPos.xyz);\n"
#ifdef USE_SHADOWMAPS
"    v_shadow = uLightMatrix * worldPos;\n"
#endif
"    gl_Position = uViewProjectionMatrix * worldPos;\n"
"}\n";

static LPSHADER instanced_shader;

LPSHADER R_ModelShaderInstanced(void) {
    if (!instanced_shader) {
        MATRIX4 bones[128];

        instanced_shader = R_InitShader(instanced_vs, model_fs);
        if (instanced_shader) {
            FOR_LOOP(i, 128) Matrix4_identity(&bones[i]);
            R_Call(glUseProgram, instanced_shader->progid);
            R_Call(glUniform1f, instanced_shader->uAlphaCutoff, 0.5f);
            /* Static grass has no keyed bones; install its identity palette once, not once per frame. */
            R_Call(glUniformMatrix4fv, instanced_shader->uBones, 128, GL_FALSE, bones[0].v);
        }
    }
    return instanced_shader;
}

static void R_PrintShaderCompileFailure(GLuint shader, LPCSTR stage, LPCSTR source) {
    GLint logLength = 0;

    glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &logLength);
    fprintf(stderr, "%s shader compilation failed.\n", stage);
    if (source) {
        fprintf(stderr, "---- %s shader source ----\n%s\n---- end shader source ----\n",
                stage, source);
    }
    if (logLength > 1) {
        char *log = malloc((size_t)logLength);
        if (log) {
            glGetShaderInfoLog(shader, logLength, NULL, log);
            fprintf(stderr, "%s shader log:\n%s\n", stage, log);
            free(log);
        } else {
            fprintf(stderr, "%s shader log unavailable (allocation failed).\n", stage);
        }
    } else {
        fprintf(stderr, "%s shader returned no compiler log.\n", stage);
    }
}

static void R_PrintProgramLinkFailure(GLuint program, LPCSTR vs_source, LPCSTR fs_source) {
    GLint logLength = 0;

    glGetProgramiv(program, GL_INFO_LOG_LENGTH, &logLength);
    fprintf(stderr, "Shader program link failed.\n");
    if (vs_source) {
        fprintf(stderr, "---- vertex shader source ----\n%s\n---- end vertex shader source ----\n",
                vs_source);
    }
    if (fs_source) {
        fprintf(stderr, "---- fragment shader source ----\n%s\n---- end fragment shader source ----\n",
                fs_source);
    }
    if (logLength > 1) {
        char *log = malloc((size_t)logLength);
        if (log) {
            glGetProgramInfoLog(program, logLength, NULL, log);
            fprintf(stderr, "Program link log:\n%s\n", log);
            free(log);
        } else {
            fprintf(stderr, "Program link log unavailable (allocation failed).\n");
        }
    } else {
        fprintf(stderr, "Program returned no linker log.\n");
    }
}

LPSHADER R_InitShader(LPCSTR vs_default, LPCSTR fs_default) {
    GLuint vs = R_Call(glCreateShader, GL_VERTEX_SHADER);
    GLuint fs = R_Call(glCreateShader, GL_FRAGMENT_SHADER);
    GLint status = GL_FALSE;
    int length;

    if (!vs || !fs) {
        fprintf(stderr, "Shader creation failed: vertex=%u fragment=%u\n", vs, fs);
        if (vs) glDeleteShader(vs);
        if (fs) glDeleteShader(fs);
        return NULL;
    }

    length = (int)strlen(vs_default);
    R_Call(glShaderSource, vs, 1, (const GLchar **)&vs_default, &length);
    R_Call(glCompileShader, vs);
    R_Call(glGetShaderiv, vs, GL_COMPILE_STATUS, &status);
    if (status == GL_FALSE) {
        R_PrintShaderCompileFailure(vs, "Vertex", vs_default);
        glDeleteShader(vs);
        glDeleteShader(fs);
        return NULL;
    }

    length = (int)strlen(fs_default);
    R_Call(glShaderSource, fs, 1, (const GLchar **)&fs_default, &length);
    R_Call(glCompileShader, fs);
    R_Call(glGetShaderiv, fs, GL_COMPILE_STATUS, &status);
    if (status == GL_FALSE) {
        R_PrintShaderCompileFailure(fs, "Fragment", fs_default);
        glDeleteShader(vs);
        glDeleteShader(fs);
        return NULL;
    }

    LPSHADER program = ri.MemAlloc(sizeof(struct shader_program));
    if (!program) {
        fprintf(stderr, "Shader program allocation failed.\n");
        glDeleteShader(vs);
        glDeleteShader(fs);
        return NULL;
    }
    memset(program, 0, sizeof(*program));
    program->progid = R_Call(glCreateProgram, );
    if (!program->progid) {
        fprintf(stderr, "glCreateProgram failed.\n");
        ri.MemFree(program);
        glDeleteShader(vs);
        glDeleteShader(fs);
        return NULL;
    }

    R_Call(glAttachShader, program->progid, vs);
    R_Call(glAttachShader, program->progid, fs);

    R_Call(glBindAttribLocation, program->progid, attrib_position, "i_position");
    R_Call(glBindAttribLocation, program->progid, attrib_color, "i_color");
    R_Call(glBindAttribLocation, program->progid, attrib_texcoord, "i_texcoord");
    R_Call(glBindAttribLocation, program->progid, attrib_normal, "i_normal");
    R_Call(glBindAttribLocation, program->progid, attrib_skin1, "i_skin1");
    R_Call(glBindAttribLocation, program->progid, attrib_boneWeight1, "i_boneWeight1");
    R_Call(glBindAttribLocation, program->progid, attrib_particleSize, "i_size");
    R_Call(glBindAttribLocation, program->progid, attrib_particleAxis, "i_axis");
    R_Call(glBindAttribLocation, program->progid, attrib_instance0, "i_instance0");
    R_Call(glBindAttribLocation, program->progid, attrib_instance1, "i_instance1");
    R_Call(glBindAttribLocation, program->progid, attrib_instance2, "i_instance2");
    R_Call(glBindAttribLocation, program->progid, attrib_instance3, "i_instance3");

    R_Call(glLinkProgram, program->progid);
    R_Call(glGetProgramiv, program->progid, GL_LINK_STATUS, &status);
    if (status == GL_FALSE) {
        R_PrintProgramLinkFailure(program->progid, vs_default, fs_default);
        glDeleteProgram(program->progid);
        ri.MemFree(program);
        glDeleteShader(vs);
        glDeleteShader(fs);
        return NULL;
    }

    glDeleteShader(vs);
    glDeleteShader(fs);

    R_Call(glUseProgram, program->progid);

#define R_RegisterUniform(PROGRAM, NAME) PROGRAM->NAME = glGetUniformLocation(PROGRAM->progid, #NAME);

    R_RegisterUniform(program, uViewProjectionMatrix);
    R_RegisterUniform(program, uModelMatrix);
    R_RegisterUniform(program, uLightMatrix);
    R_RegisterUniform(program, uNormalMatrix);
    R_RegisterUniform(program, uTextureMatrix);
    R_RegisterUniform(program, uTexture);
#if defined(USE_SHADOWMAPS) || defined(DEBUG_PATHFINDING)
    R_RegisterUniform(program, uShadowmap);
#endif
    R_RegisterUniform(program, uFogOfWar);
    R_RegisterUniform(program, uBones);
    R_RegisterUniform(program, uAlphaKey);
    R_RegisterUniform(program, uAlphaCutoff);
    R_RegisterUniform(program, uUnshaded);
    R_RegisterUniform(program, uLayerAlpha);
    R_RegisterUniform(program, uGeosetColor);
    R_RegisterUniform(program, uUvTrans);
    R_RegisterUniform(program, uUvRot);
    R_RegisterUniform(program, uUvScale);
    R_RegisterUniform(program, uLightDir);
    R_RegisterUniform(program, uLightColor);
    R_RegisterUniform(program, uLightAmbient);
    R_RegisterUniform(program, uLightCount);
    program->uLights = glGetUniformLocation(program->progid, "uLights[0]");
    R_RegisterUniform(program, uEyePosition);
    R_RegisterUniform(program, uActiveGlow);
    R_RegisterUniform(program, uFogEnable);
    R_RegisterUniform(program, uFogColor);
    R_RegisterUniform(program, uFogParams);
    R_RegisterUniform(program, uFirstBoneLookupIndex);

    R_Call(glUniform1i, program->uTexture, 0);
#if defined(USE_SHADOWMAPS) || defined(DEBUG_PATHFINDING)
    R_Call(glUniform1i, program->uShadowmap, 1);
#endif
    R_Call(glUniform1i, program->uFogOfWar, 2);

    return program;
}

void R_ReleaseShader(LPSHADER shader) {
    ri.MemFree(shader);
}

void R_ShutdownModelShader(void) {
    SAFE_DELETE(model_shader, R_ReleaseShader);
    SAFE_DELETE(instanced_shader, R_ReleaseShader);
}

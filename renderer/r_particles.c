#include "r_local.h"
#include "r_shader.h"

#define NUM_PARTICLE_VERTICES 6
#define MAX_PARTICLES 10000
#define UI_ATTENTION_EMITTERS 2 // emitters; opposite-phase sparkle paths around one quest button.
#define UI_ATTENTION_MAX_TAIL 32 // samples; 50/sec × 0.3 sec trail lifetime with headroom.
#define UI_ATTENTION_MAX_HEAD 64 // particles; 2 × 50/sec × 1 sec head lifetime with headroom.
#define UI_ATTENTION_RATE 50.0f // particles/sec; tail and head emission rate from quest sparkle simulation.
#define UI_ATTENTION_TAIL_LIFE 0.3f // seconds; fixed trail-sample lifetime for a short perimeter streak.
#define UI_ATTENTION_HEAD_LIFE 1.0f // seconds; head sparkle lifetime.
#define UI_ATTENTION_HEAD_SPEED 0.02f // UI units/sec; fixed downward head-particle speed.
#define UI_ATTENTION_MOTION_SPEED 0.9f // unitless; perimeter motion multiplier before the 0.18 authored scale.
#define UI_ATTENTION_MOTION_SCALE 0.18f // cycles/unit; authored path-time scale for the 6.17-second loop.
#define UI_ATTENTION_DT_MAX 0.05f // seconds; caps a stalled frame to keep the simulation frame-rate independent.

typedef struct {
    VECTOR2 pos, vel;
    FLOAT age, life, start, mid, end;
} uiAttentionParticle_t;

typedef struct {
    RECT rect;
    FLOAT time, acc[UI_ATTENTION_EMITTERS];
    BOOL valid;
    uiAttentionParticle_t tail[UI_ATTENTION_EMITTERS][UI_ATTENTION_MAX_TAIL];
    DWORD tail_count[UI_ATTENTION_EMITTERS];
    uiAttentionParticle_t head[UI_ATTENTION_EMITTERS][UI_ATTENTION_MAX_HEAD];
    DWORD head_count[UI_ATTENTION_EMITTERS];
} uiAttentionState_t;

static uiAttentionState_t ui_attention;

typedef struct particle_vertex {
    VECTOR3 position;
    COLOR32 color;
    float size;
    VECTOR3 tail;
    BYTE uv[2];
    BYTE axis[2];
} particleVertex_t;

typedef struct PARTICLESTATE {
    MATRIX4 viewProjection;
    MATRIX4 textureMatrix;
    MATRIX4 model;
    VECTOR3 eye;
    int texture;
    int fogOfWar;
    bool alphaKey;
    FLOAT alphaCutoff;
} PARTICLESTATE;
typedef struct PARTICLESTATE *LPPARTICLESTATE;
typedef const struct PARTICLESTATE *LPCPARTICLESTATE;
typedef struct PARTICLEPROG {
    SHADERPROG prog;
    PARTICLESTATE state;
} PARTICLEPROG;
typedef struct PARTICLEPROG *LPPARTICLEPROG;
typedef const struct PARTICLEPROG *LPCPARTICLEPROG;

static struct {
    PARTICLEPROG shader;
//    LPRENDERTARGET rt[FOW_RT_COUNT];
    LPBUFFER particles;
    LPTEXTURE texture;
    particleVertex_t vertices[MAX_PARTICLES * NUM_PARTICLE_VERTICES];
} particles_resources = { 0 };

cparticle_t *active_particles, *free_particles;
cparticle_t particles[MAX_PARTICLES];
int cl_numparticles = MAX_PARTICLES;

void R_ClearParticles(void) {
    free_particles = &particles[0];
    active_particles = NULL;
    FOR_LOOP(i, cl_numparticles) {
        particles[i].next = &particles[i+1];
    }
    particles[cl_numparticles-1].next = NULL;
}

cparticle_t *R_SpawnParticle(void) {
    if (!free_particles)
//        return NULL;
        return NULL;
    cparticle_t *p = free_particles;
    free_particles = p->next;
    p->next = active_particles;
    active_particles = p;
    p->blend_mode = BLEND_MODE_ADD;
    p->tail = (VECTOR3){0};
    p->size_value_scale = p->size_time_scale = 1.0f;
    return p;
}

#define SHADER_TYPE PARTICLESTATE
static const shader_desc_t sd_particle = {
    .Name = "particle",
    .Uniforms = {
        UNIFORM(viewProjection, UT_FLOAT_MAT4, PRECISION_HIGH),
        UNIFORM(textureMatrix,  UT_FLOAT_MAT4, PRECISION_HIGH),
        UNIFORM(model,          UT_FLOAT_MAT4, PRECISION_HIGH),
        UNIFORM(eye,            UT_FLOAT_VEC3, PRECISION_HIGH),
        UNIFORM(texture,        UT_SAMPLER_2D, PRECISION_LOW),
        UNIFORM(fogOfWar,       UT_SAMPLER_2D, PRECISION_LOW),
        UNIFORM(alphaKey,       UT_BOOL,       PRECISION_LOW),
        UNIFORM(alphaCutoff,    UT_FLOAT,      PRECISION_LOW),
    },
    .Attributes = {
        ATTRIB(position, attrib_position,     UT_FLOAT_VEC3),
        ATTRIB(color,    attrib_color,        UT_COLOR),
        ATTRIB(texcoord, attrib_texcoord,     UT_FLOAT_VEC2),
        ATTRIB(size,     attrib_particleSize, UT_FLOAT),
        ATTRIB(tail,     attrib_particleTail, UT_FLOAT_VEC3),
        ATTRIB(axis,     attrib_particleAxis, UT_FLOAT_VEC2),
    },
    .Shared = {
        SHARED(color,    UT_COLOR),
        SHARED(texcoord, UT_FLOAT_VEC2),
        SHARED(texcoord2, UT_FLOAT_VEC2),
    },
    .VertexBody =
        "vec4 vert() {\n"
        "  mat4 m = u_viewProjection;\n"
        "  vec3 cameraLeft = normalize(vec3(m[0][0], m[1][0], m[2][0]));\n"
        "  vec3 left = cameraLeft * a_size;\n"
        "  vec3 up = normalize(vec3(m[0][1], m[1][1], m[2][1])) * a_size;\n"
        "  vec3 pos;\n"
        "  if (dot(a_tail, a_tail) > 0.0001) {\n"
        "    vec3 point = a_position - a_tail * (1.0 - a_axis.y);\n"
        "    vec3 side = cross(normalize(a_tail), u_eye - point);\n"
        "    float sideLength = length(side);\n"
        "    if (sideLength < 0.0001) side = cameraLeft; else side /= sideLength;\n"
        "    pos = point + side * ((a_axis.x - 0.5) * a_size);\n"
        "  } else {\n"
        "    mat3 bb_mat = mat3(left, up, a_position);\n"
        "    pos = bb_mat * vec3(a_axis - vec2(0.5), 1.0);\n"
        "  }\n"
        "  v_color = a_color;\n"
        "  v_texcoord = a_texcoord;\n"
        "  v_texcoord2 = (u_textureMatrix * vec4(pos, 1.0)).xy;\n"
        "  return u_viewProjection * vec4(pos, 1.0);\n"
        "}\n",
    /* Waterfalls are PRE2-only models; the old unfogged particle pass exposed the whole effect through black FOW. */
    .FragmentBody =
        "vec4 frag() {\n"
        "  vec4 col = texture(u_texture, v_texcoord) * v_color;\n"
        "#ifdef USE_FOGOFWAR\n"
        "  col.rgb *= texture(u_fogOfWar, v_texcoord2).r;\n"
        "#endif\n"
        "  if (u_alphaKey) {\n"
        "#ifndef BZ_USE_MSAA\n"
        "    if (col.a < u_alphaCutoff) discard;\n"
        "#else\n"
        "    float edge = max(fwidth(col.a), 1.0 / 255.0);\n"
        "    col.a = smoothstep(u_alphaCutoff - edge, u_alphaCutoff + edge, col.a);\n"
        "#endif\n"
        "  }\n"
        "  return col;\n"
        "}\n",
};
#undef SHADER_TYPE

particleVertex_t *
R_AddParticle(particleVertex_t *buffer,
              LPCVECTOR3 point,
              LPCVECTOR3 tail,
              COLOR32 uvr,
              COLOR32 color,
              float size)
{
    BYTE a = 0x00, b = 0xff;
    LPBYTE uv = (LPBYTE)&uvr;
    particleVertex_t const data[NUM_PARTICLE_VERTICES] = {
        { .position = *point, .tail = tail ? *tail : (VECTOR3){0}, .uv = {uv[0],uv[1]}, .axis = {a,a}, .color = color, .size = size },
        { .position = *point, .tail = tail ? *tail : (VECTOR3){0}, .uv = {uv[2],uv[1]}, .axis = {b,a}, .color = color, .size = size },
        { .position = *point, .tail = tail ? *tail : (VECTOR3){0}, .uv = {uv[2],uv[3]}, .axis = {b,b}, .color = color, .size = size },
        { .position = *point, .tail = tail ? *tail : (VECTOR3){0}, .uv = {uv[2],uv[3]}, .axis = {b,b}, .color = color, .size = size },
        { .position = *point, .tail = tail ? *tail : (VECTOR3){0}, .uv = {uv[0],uv[3]}, .axis = {a,b}, .color = color, .size = size },
        { .position = *point, .tail = tail ? *tail : (VECTOR3){0}, .uv = {uv[0],uv[1]}, .axis = {a,a}, .color = color, .size = size },
    };
    memcpy(buffer, data, sizeof(data));
    return buffer + NUM_PARTICLE_VERTICES;
}

void R_UpdateParticles(void) {
    cparticle_t *active = NULL;
    cparticle_t *tail = NULL;
    cparticle_t *next = NULL;
    float frameTime = tr.viewDef.deltaTime / 1000.f;
    
    for (cparticle_t *p = active_particles; p; p = next) {
        next = p->next;
        p->time += frameTime;
        if (p->time > p->lifespan) {
            p->next = free_particles;
            free_particles = p;
            continue;
        }
        p->next = NULL;
        if (!tail) {
            active = tail = p;
        } else {
            tail->next = p;
            tail = p;
        }
    }
    active_particles = active;
}

COLOR32 FX_LerpColor(COLOR32 a, COLOR32 b, float t) {
    return (COLOR32) {
        .r = LerpNumber(a.r, b.r, t),
        .g = LerpNumber(a.g, b.g, t),
        .b = LerpNumber(a.b, b.b, t),
        .a = LerpNumber(a.a, b.a, t),
    };
}

float FX_BlendFloat(BYTE const *values, float k, float midtime) {
    if (k > midtime) {
        return LerpNumber(values[1], values[2], (k - midtime) / (1 - midtime));
    } else {
        return LerpNumber(values[0], values[1], k / midtime);
    }
}

COLOR32 FX_BlendColor(cparticle_t const *p) {
    float k = p->time / p->lifespan;
    float t = (float)p->midtime / (float)0xff;
    if (k > t) {
        return FX_LerpColor(p->color[1], p->color[2], (k - t) / (1 - t));
    } else {
        return FX_LerpColor(p->color[0], p->color[1], k / t);
    }
}

static void R_FlushParticles(LPCTEXTURE texture, LPCMATRIX4 matrix, particleVertex_t *pv, BLEND_MODE blend_mode) {
    R_Call(glBindVertexArray, particles_resources.particles->vao);
    R_Call(glBindBuffer, GL_ARRAY_BUFFER, particles_resources.particles->vbo);
    R_Call(glBufferData, GL_ARRAY_BUFFER, sizeof(particleVertex_t) * (pv - particles_resources.vertices), particles_resources.vertices, GL_DYNAMIC_DRAW);

    particles_resources.shader.state.model = *matrix;
    particles_resources.shader.state.viewProjection = tr.viewDef.viewProjectionMatrix;
    particles_resources.shader.state.eye = tr.viewDef.camerastate[0].eye;
    particles_resources.shader.state.textureMatrix = tr.viewDef.textureMatrix;
    R_Call(glActiveTexture, GL_TEXTURE0);
    R_Call(glBindTexture, GL_TEXTURE_2D, (texture?texture:particles_resources.texture)->texid);
    particles_resources.shader.state.alphaKey = blend_mode == BLEND_MODE_ALPHAKEY;
    particles_resources.shader.state.alphaCutoff = 0.5f;
    R_SetAlphaKeyState(blend_mode == BLEND_MODE_ALPHAKEY);
    if (blend_mode == BLEND_MODE_NONE) {
        R_Call(glDisable, GL_BLEND);
        R_Call(glDepthMask, GL_TRUE);
        R_Call(glBlendFunc, GL_ONE, GL_ZERO);
    } else if (blend_mode == BLEND_MODE_ALPHAKEY) {
        /* Alpha-key particles must not inherit additive state from an earlier batch. */
        R_Call(glDisable, GL_BLEND);
        R_Call(glDepthMask, GL_TRUE);
        R_Call(glBlendFunc, GL_ONE, GL_ZERO);
    } else {
        R_Call(glEnable, GL_BLEND);
        R_Call(glDepthMask, GL_FALSE);
        switch (blend_mode) {
        case BLEND_MODE_ADD:
            /* Shared particle legacy: ADD means alpha-weighted additive. */
            R_Call(glBlendFunc, GL_SRC_ALPHA, GL_ONE);
            break;
        case BLEND_MODE_ADDALPHA:
            /* Shared particle legacy: ADDALPHA means unweighted additive. */
            R_Call(glBlendFunc, GL_ONE, GL_ONE);
            break;
        case BLEND_MODE_MODULATE:
            R_Call(glBlendFunc, GL_ZERO, GL_SRC_COLOR);
            break;
        case BLEND_MODE_MODULATE_2X:
            R_Call(glBlendFunc, GL_DST_COLOR, GL_SRC_COLOR);
            break;
        default:
            R_Call(glBlendFunc, GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA);
            break;
        }
    }
    R_StatsDraw(GL_TRIANGLES, (DWORD)(pv - particles_resources.vertices), 1);
    R_ApplyShader(&particles_resources.shader);
    R_Call(glDrawArrays, GL_TRIANGLES, 0, (GLsizei)(pv - particles_resources.vertices));
}

static COLOR32 FX_GetFrame(const cparticle_t *p) {
    DWORD columns = p->columns ? p->columns : 1;
    DWORD rows = p->rows ? p->rows : 1;
    DWORD total = columns * rows;
    /* The sprite-sheet frame advances over the particle's own lifetime, not a
     * global clock — otherwise every particle flips frames in unison, which
     * reads as a crude strobing "old game" effect. */
    float k = (p->lifespan > 0.0f) ? (p->time / p->lifespan) : 0.0f;
    DWORD frame = (DWORD)(k * (float)total);
    if (frame >= total) frame = total - 1;
    DWORD u = frame % columns;
    DWORD v = frame / columns;
    DWORD usize = 256 / columns;
    DWORD vsize = 256 / rows;
    return (COLOR32) {
        usize * u,
        vsize * v,
        usize * (u + 1) - 1,
        vsize * (v + 1) - 1,
    };
}

/* Evaluate clockwise perimeter distance so the two UI emitters never jump at the loop seam. */
static VECTOR2 R_UIAttentionPosition(LPCRECT rect, FLOAT phase) {
    FLOAT span = 2.0f * (rect->w + rect->h);
    FLOAT dist = fmodf(phase, 1.0f) * span;

    if (dist < rect->w) return (VECTOR2){ rect->x + dist, rect->y };
    dist -= rect->w;
    if (dist < rect->h) return (VECTOR2){ rect->x + rect->w, rect->y + dist };
    dist -= rect->h;
    if (dist < rect->w) return (VECTOR2){ rect->x + rect->w - dist, rect->y + rect->h };
    dist -= rect->w;
    return (VECTOR2){ rect->x, rect->y + rect->h - dist };
}

/* Apply the shared three-point particle size curve to either head or tail age. */
static FLOAT R_UIAttentionSize(uiAttentionParticle_t const *p) {
    FLOAT u = MAX(0.0f, MIN(1.0f, p->age / p->life));
    return u < 0.5f ? p->start + (p->mid - p->start) * u * 2.0f
                    : p->mid + (p->end - p->mid) * (u - 0.5f) * 2.0f;
}

/* Remove expired UI particles in-place while retaining stable order for diagnostics. */
static void R_UIAttentionCompact(uiAttentionParticle_t *list, DWORD *count, DWORD max) {
    DWORD out = 0;
    FOR_LOOP(i, *count) if (list[i].age < list[i].life) list[out++] = list[i];
    *count = MIN(out, max);
}

/* Advance the two opposite-phase emitters and deposit frame-rate-independent head/tail samples. */
static void R_UIAttentionUpdate(LPCRECT rect, FLOAT dt) {
    FLOAT rate_dt = UI_ATTENTION_RATE * dt;

    if (!ui_attention.valid || memcmp(&ui_attention.rect, rect, sizeof(*rect))) {
        memset(&ui_attention, 0, sizeof(ui_attention));
        ui_attention.rect = *rect;
        ui_attention.valid = true;
    }
    ui_attention.time += dt;
    FOR_LOOP(e, UI_ATTENTION_EMITTERS) {
        FLOAT phase = ui_attention.time * UI_ATTENTION_MOTION_SPEED * UI_ATTENTION_MOTION_SCALE + e * 0.5f;
        VECTOR2 pos = R_UIAttentionPosition(rect, phase);
        ui_attention.acc[e] += rate_dt;
        while (ui_attention.acc[e] >= 1.0f) {
            ui_attention.acc[e] -= 1.0f;
            if (ui_attention.tail_count[e] == UI_ATTENTION_MAX_TAIL) {
                memmove(&ui_attention.tail[e][0], &ui_attention.tail[e][1],
                        sizeof(ui_attention.tail[e][0]) * (UI_ATTENTION_MAX_TAIL - 1));
                ui_attention.tail_count[e]--;
            }
            ui_attention.tail[e][ui_attention.tail_count[e]++] = (uiAttentionParticle_t){
                .pos = pos, .life = UI_ATTENTION_TAIL_LIFE,
                .start = e ? 0.006f : 0.010f, .mid = 0.004f, .end = 0.002f };
            if (ui_attention.head_count[e] < UI_ATTENTION_MAX_HEAD)
                ui_attention.head[e][ui_attention.head_count[e]++] = (uiAttentionParticle_t){
                    .pos = pos, .vel = { 0, -UI_ATTENTION_HEAD_SPEED }, .life = UI_ATTENTION_HEAD_LIFE,
                    .start = e ? 0.006f : 0.010f, .mid = 0.004f, .end = 0.002f };
        }
        FOR_LOOP(i, ui_attention.tail_count[e]) ui_attention.tail[e][i].age += dt;
        FOR_LOOP(i, ui_attention.head_count[e]) {
            uiAttentionParticle_t *p = &ui_attention.head[e][i];
            p->pos.x += p->vel.x * dt; p->pos.y += p->vel.y * dt; p->age += dt;
        }
        R_UIAttentionCompact(ui_attention.tail[e], &ui_attention.tail_count[e], UI_ATTENTION_MAX_TAIL);
        R_UIAttentionCompact(ui_attention.head[e], &ui_attention.head_count[e], UI_ATTENTION_MAX_HEAD);
    }
}

void R_DrawParticles(void) {
    MATRIX4 matrix;
    particleVertex_t *pv = particles_resources.vertices;
    LPCTEXTURE texture;
    BLEND_MODE blend_mode;

    if (!R_CvarEnabled("r_particles", "1") || !active_particles) return;
    texture = active_particles->texture; blend_mode = active_particles->blend_mode;
    
    Matrix4_identity(&matrix);
    R_UpdateParticles();
    
    FOR_EACH_LIST(cparticle_t const, p, active_particles) {
        if (p->texture != texture || p->blend_mode != blend_mode) {
            R_FlushParticles(texture, &matrix, pv, blend_mode);
            pv = particles_resources.vertices;
        }
        /* Kinematics: org = org0 + vel0*t + 1/2*accel*t^2. The original engine
         * integrates gravity per-frame (semi-implicit Euler), which over a
         * particle's life is the 1/2*a*t^2 closed form below; applying the full
         * a*t^2 made gravity-driven particles fall ~2x too fast. */
        VECTOR3 halfAccelT = Vector3_scale(&p->accel, 0.5f * p->time);
        VECTOR3 vel = Vector3_add(&p->vel, &halfAccelT);
        VECTOR3 org = Vector3_mad(&p->org, p->time, &vel);
#ifdef WC3_DEBUG_PARTICLES
        {
            VECTOR3 const ui = Matrix4_multiply_vector3(&tr.viewDef.viewProjectionMatrix, &org);
            fprintf(stderr, "WC3 particles: live world=(%.4f,%.4f,%.4f) ui=(%.4f,%.4f) age=%.3f\n",
                    org.x, org.y, org.z, ui.x, ui.y, p->time);
        }
#endif
        COLOR32 col = FX_BlendColor(p);
        float size = p->size_value_scale * FX_BlendFloat(p->size, p->time * p->size_time_scale,
                                                         BYTE2FLOAT(p->midtime));
        pv = R_AddParticle(pv, &org, &p->tail, FX_GetFrame(p), col, size);
        texture = p->texture;
        blend_mode = p->blend_mode;
    }
    
    R_FlushParticles(texture, &matrix, pv, blend_mode);
    R_SetAlphaKeyState(false);
}

/* Draw a single camera-facing (billboarded) sprite at a world position, reusing the particle
 * billboard pipeline. BLP textures are stored top-down and the particle shader maps a quad's top
 * vertex to V=1, so the UV rect is V-flipped to keep the sprite upright (top of image at top of quad). */
void R_DrawBillboardSprite(LPCTEXTURE texture, LPCVECTOR3 origin, float size, COLOR32 color) {
    MATRIX4 matrix;
    particleVertex_t *pv = particles_resources.vertices;
    COLOR32 const uv = { 0, 255, 255, 0 };

    if (!texture) texture = particles_resources.texture;
    Matrix4_identity(&matrix);
    pv = R_AddParticle(pv, origin, NULL, uv, color, size);
    R_FlushParticles(texture, &matrix, pv, BLEND_MODE_BLEND);
    R_SetAlphaKeyState(false);
}

/* Draw two immediate UI particles at the supplied corners; unlike world particles,
 * these are not inserted into the persistent world particle pool. */
void R_DrawUIAttentionParticles(LPCRECT rect) {
    viewDef_t saved;
    RECT scene;
    MATRIX4 ui;
    MATRIX4 model;
    particleVertex_t *pv = particles_resources.vertices;
    FLOAT dt;

    if (!rect) return;
    saved = tr.viewDef;
    scene = R_UISceneRect();
    dt = MIN((FLOAT)tr.viewDef.deltaTime / 1000.0f, UI_ATTENTION_DT_MAX);
    R_UIAttentionUpdate(rect, dt);
    Matrix4_ortho(&ui, scene.x, scene.x + scene.w, scene.y + scene.h, scene.y, 0.0f, 100.0f);
    tr.viewDef.viewProjectionMatrix = ui;
    Matrix4_identity(&tr.viewDef.textureMatrix);
    Matrix4_identity(&model);
    R_Call(glDisable, GL_DEPTH_TEST);
    FOR_LOOP(e, UI_ATTENTION_EMITTERS) {
        FOR_LOOP(i, ui_attention.tail_count[e]) {
            uiAttentionParticle_t const *p = &ui_attention.tail[e][i];
            FLOAT fade = 1.0f - p->age / p->life;
            COLOR32 col = { 255, 255, 255, (BYTE)(fade * 255.0f + 0.5f) };
            VECTOR3 pos = { p->pos.x, p->pos.y, 0.0f };
            FLOAT size = R_UIAttentionSize(p);
            /* Match the original MDX particle look: one shared particle sprite
             * per trail sample, rather than expanding each sample into two glows. */
            pv = R_AddParticle(pv, &pos, NULL, (COLOR32){ 0, 255, 255, 0 }, col, size);
        }
        FOR_LOOP(i, ui_attention.head_count[e]) {
            uiAttentionParticle_t const *p = &ui_attention.head[e][i];
            FLOAT fade = 1.0f - p->age / p->life;
            COLOR32 col = { 255, 255, 255, (BYTE)(fade * 166.0f + 0.5f) };
            VECTOR3 pos = { p->pos.x, p->pos.y, 0.0f };
            pv = R_AddParticle(pv, &pos, NULL, (COLOR32){ 0, 255, 255, 0 }, col, R_UIAttentionSize(p));
        }
    }
    if (pv != particles_resources.vertices)
        R_FlushParticles(NULL, &model, pv, BLEND_MODE_ADD);
    tr.viewDef = saved;
}

static LPBUFFER R_MakeParticlesVertexArrayObject(void) {
    LPBUFFER buf = ri.MemAlloc(sizeof(BUFFER));

    R_Call(glGenVertexArrays, 1, &buf->vao);
    R_Call(glGenBuffers, 1, &buf->vbo);
    R_Call(glBindVertexArray, buf->vao);
    R_Call(glBindBuffer, GL_ARRAY_BUFFER, buf->vbo);

    R_Call(glEnableVertexAttribArray, attrib_position);
    R_Call(glEnableVertexAttribArray, attrib_color);
    R_Call(glEnableVertexAttribArray, attrib_texcoord);
    R_Call(glEnableVertexAttribArray, attrib_particleSize);
    R_Call(glEnableVertexAttribArray, attrib_particleTail);
    R_Call(glEnableVertexAttribArray, attrib_particleAxis);
    
    R_Call(glVertexAttribPointer, attrib_position, 3, GL_FLOAT, GL_FALSE, sizeof(struct particle_vertex), FOFS(particle_vertex, position));
    R_Call(glVertexAttribPointer, attrib_color, 4, GL_UNSIGNED_BYTE, GL_TRUE, sizeof(struct particle_vertex), FOFS(particle_vertex, color));
    R_Call(glVertexAttribPointer, attrib_texcoord, 2, GL_UNSIGNED_BYTE, GL_TRUE, sizeof(struct particle_vertex), FOFS(particle_vertex, uv));
    R_Call(glVertexAttribPointer, attrib_particleSize, 1, GL_FLOAT, GL_FALSE, sizeof(struct particle_vertex), FOFS(particle_vertex, size));
    R_Call(glVertexAttribPointer, attrib_particleTail, 3, GL_FLOAT, GL_FALSE, sizeof(struct particle_vertex), FOFS(particle_vertex, tail));
    R_Call(glVertexAttribPointer, attrib_particleAxis, 2, GL_UNSIGNED_BYTE, GL_TRUE, sizeof(struct particle_vertex), FOFS(particle_vertex, axis));
    return buf;
}

#define DOT_TEXTURE 8

float dottexture[DOT_TEXTURE][DOT_TEXTURE] = {
    {0,0,0,0,0,0,0,0},
    {0,0,1,1,1,1,0,0},
    {0,1,2,2,2,2,1,0},
    {0,1,2,2,2,2,1,0},
    {0,1,2,2,2,2,1,0},
    {0,1,2,2,2,2,1,0},
    {0,0,1,1,1,1,0,0},
    {0,0,0,0,0,0,0,0},
};

void R_InitParticles(void) {
    COLOR32 data[DOT_TEXTURE][DOT_TEXTURE];
    FOR_LOOP(x, DOT_TEXTURE) FOR_LOOP(y, DOT_TEXTURE) {
        data[x][y].r = 0xff;
        data[x][y].g = 0xff;
        data[x][y].b = 0xff;
        data[x][y].a = dottexture[x][y] * 127;
    }
    
    particles_resources.texture = R_AllocateTexture(DOT_TEXTURE, DOT_TEXTURE);
    R_LoadTextureMipLevel(particles_resources.texture, &(TEXMIP){ data, DOT_TEXTURE, DOT_TEXTURE, 0, PIXEL_RGBA });

    static const char *particle_defines =
#ifdef USE_FOGOFWAR
        "#define USE_FOGOFWAR 1\n"
#endif
#ifdef BZ_USE_MSAA
        "#define BZ_USE_MSAA 1\n"
#endif
        "";
    memset(&particles_resources.shader, 0, sizeof(particles_resources.shader));
    R_LoadShader(&sd_particle, particle_defines, &particles_resources.shader);
    /* The scene contract reserves unit 2 for FOW; particles omit the shadow sampler that normally occupies unit 1. */
    particles_resources.shader.state.fogOfWar = 2;
    particles_resources.particles = R_MakeParticlesVertexArrayObject();
    R_ClearParticles();
}

void R_ShutdownParticles(void) {
    R_ReleaseVertexArrayObject(particles_resources.particles);
    R_DeleteShader(&particles_resources.shader.prog);
    memset(&particles_resources.shader, 0, sizeof(particles_resources.shader));
}

#include "r_mdx.h"
#include "renderer/r_emit.h"

#define GET_PARTICLE_ANIM_PARAM(MODEL, EMITTER, NAME) \
float NAME = EMITTER->NAME; \
if (EMITTER->keytracks.NAME) { \
    MDLX_GetModelKeytrackValue(MODEL, EMITTER->keytracks.NAME, frame, &NAME); \
}

/* Context for the R_EmitParticles spawn callback — carries the evaluated tracks
   and emitter metadata needed to fill a cparticle_t on each spawn. */
typedef struct {
    mdxModel_t const *model; mdxParticleEmitter_t const *emitter;
    LPCMATRIX4 matrix; DWORD team_id;
    float speed, varia, lat, grav, life, length, width;
    DWORD spawned;
} mdx_pctx_t;

static COLOR32 MDLX_GetEmitterColor(mdxParticleEmitter_t const *emitter, DWORD seg) {
    return (COLOR32) {
        emitter->SegmentColor[seg*3+0] * 0xff,
        emitter->SegmentColor[seg*3+1] * 0xff,
        emitter->SegmentColor[seg*3+2] * 0xff,
        emitter->Alpha[seg],
    };
}

static void mdx_spawn_particle(void *raw) {
    mdx_pctx_t *ctx = (mdx_pctx_t *)raw;
    cparticle_t *p = R_SpawnParticle(); if (!p) return;
    ctx->spawned++;
    float r = (float)rand() / (float)RAND_MAX;
    VECTOR3 origin = {
        (r - 0.5f) * ctx->length,
        ((float)rand() / (float)RAND_MAX - 0.5f) * ctx->width,
        0.0f,
    };
    VECTOR3 pivot = { 0, 0, 0 };
    if (ctx->emitter->node.node_id < (DWORD)ctx->model->num_pivots)
        pivot = ctx->model->pivots[ctx->emitter->node.node_id];
    VECTOR3 pivoted = Vector3_add(&origin, &pivot);
    VECTOR3 dir = FX_GenerateRandomDirection(ctx->lat * (float)M_PI / 180.0f);
    p->org = Matrix4_multiply_vector3(ctx->matrix, &pivoted);
    p->vel = Vector3_scale(&dir, ctx->speed + (r - 0.5f) * ctx->varia);
    p->accel = (VECTOR3){ 0, 0, -ctx->grav };
    p->lifespan = ctx->life; p->time = 0;
    p->midtime = ctx->emitter->Time * 0xff;
    p->texture = MDLX_GetTexture(ctx->model, ctx->team_id, ctx->emitter->TextureID, ctx->emitter->ReplaceableId, NULL);
    p->blend_mode = MDLX_ParticleBlendMode(ctx->emitter->FilterMode);
    p->columns = ctx->emitter->Columns; p->rows = ctx->emitter->Rows;
    p->color[0] = MDLX_GetEmitterColor(ctx->emitter, 0);
    p->color[1] = MDLX_GetEmitterColor(ctx->emitter, 1);
    p->color[2] = MDLX_GetEmitterColor(ctx->emitter, 2);
    R_EncodeParticleSize(p, ctx->emitter->ParticleScaling);
    if (ctx->emitter->FrameFlags == BZ_MDX_PARTICLE_BOTH) {
        cparticle_t *tail = R_SpawnParticle();
        if (tail) { cparticle_t *next = tail->next; *tail = *p; tail->next = next; p = tail; ctx->spawned++; }
        else return;
    }
    if (ctx->emitter->FrameFlags != BZ_MDX_PARTICLE_HEAD)
        p->tail = Vector3_scale(&p->vel, ctx->emitter->TailLength);
}

/* Frame-relative accumulator emission via R_EmitParticles — replaces the old
   whole-second time-anchored loop.  Uses emitter->accumulator to track fractional
   emission across frames (same pattern as WoW's M2_DrawParticles). */
static DWORD MDLX_RenderHeadEmitter(mdxModel_t const *model,
                                   mdxParticleEmitter_t *emitter,
                                   LPCMATRIX4 modelMatrix,
                                   float frame,
                                   DWORD teamID)
{
    GET_PARTICLE_ANIM_PARAM(model, emitter, EmissionRate);
    GET_PARTICLE_ANIM_PARAM(model, emitter, Speed);
    GET_PARTICLE_ANIM_PARAM(model, emitter, Variation);
    GET_PARTICLE_ANIM_PARAM(model, emitter, Latitude);
    GET_PARTICLE_ANIM_PARAM(model, emitter, Gravity);
    GET_PARTICLE_ANIM_PARAM(model, emitter, Width);
    GET_PARTICLE_ANIM_PARAM(model, emitter, Length);
    if (EmissionRate <= 0.0f) return 0;
    if (emitter->node.node_id >= MDX_MAX_NODES) return 0;
    MATRIX4 matrix;
    Matrix4_multiply(modelMatrix, &node_matrices[emitter->node.node_id], &matrix);
    mdx_pctx_t ctx = { model, emitter, &matrix, teamID,
        Speed, Variation, Latitude, Gravity, emitter->LifeSpan, Length, Width };
    R_EmitParticles(EmissionRate, &emitter->accumulator, tr.viewDef.deltaTime, mdx_spawn_particle, &ctx);
    return ctx.spawned;
}

void MDLX_RenderParticleEmitters(const renderEntity_t *entity, const mdxModel_t *model, LPCMATRIX4 model_matrix) {
    /*
     * Dead destructable remains are marked RF_NOT_SELECTABLE.  While their
     * death sequence is advancing oldframe != frame, so the destruction
     * emitters remain active.  tree_decay1() holds the final frame once the
     * death sequence finishes; after the next snapshot oldframe == frame.
     *
     * Do not keep evaluating/emitting particles indefinitely from that held
     * final death frame. Existing particles remain in the particle system and
     * expire normally.
     */
    if ((entity->flags & RF_NOT_SELECTABLE) &&
        entity->oldframe == entity->frame) {
        return;
    }
    float const frame = LerpNumber(entity->oldframe, entity->frame, tr.viewDef.lerpfrac);
    DWORD total = 0, visible = 0, active = 0, spawned = 0;
    static DWORD last_log[MAX_GAME_ENTITIES];

    FOR_EACH_LIST(mdxParticleEmitter_t, emitter, model->emitters) {
        float visibility = 1.0f, rate = emitter->EmissionRate;
        total++;

        if (emitter->keytracks.Visibility) {
            MDLX_GetModelKeytrackValue(model, emitter->keytracks.Visibility, entity->frame, &visibility);
            if (visibility < EPSILON)
                continue;
        }
        visible++;
        if (emitter->keytracks.EmissionRate)
            MDLX_GetModelKeytrackValue(model, emitter->keytracks.EmissionRate, frame, &rate);
        if (rate > 0.0f) active++;
        spawned += MDLX_RenderHeadEmitter(model, emitter, model_matrix, frame, entity->team&TEAM_MASK);
    }
    if (atoi(ri.CvarString ? ri.CvarString("wc3_attack_fx_debug", "0") : "0") >= 2 && total &&
        entity->number >= 0 && entity->number < MAX_GAME_ENTITIES &&
        (tr.viewDef.time >= last_log[entity->number] + 250 || !last_log[entity->number])) {
        mdxSequence_t const *seq = R_FindSequenceAtTime(model, entity->frame);
        fprintf(stderr,
                "[wc3fx][renderer][pre2] time=%u ent=%d seq=\"%s\" frame=%u total=%u visible=%u active=%u spawned=%u\n",
                (unsigned)tr.viewDef.time, entity->number, seq ? seq->name : "<none>",
                (unsigned)entity->frame, (unsigned)total, (unsigned)visible, (unsigned)active,
                (unsigned)spawned);
        last_log[entity->number] = tr.viewDef.time;
    }
}


static mdxMaterial_t const *MDLX_RibbonMaterial(mdxModel_t const *model, LONG material_id) {
    mdxMaterial_t const *material;
    if (!model || material_id < 0) return NULL;
    material = model->materials;
    while (material && material_id-- > 0) material = material->next;
    return material;
}

static mdxRibbonInstance_t *MDLX_RibbonInstance(mdxRibbonEmitter_t *emitter, int entity_number) {
    mdxRibbonInstance_t *state;
    DWORD const now = tr.viewDef.time;

    for (state = emitter->instances; state; state = state->next) {
        if (state->entity_number != entity_number) continue;
        /* Entity numbers are recycled. A long presentation gap means this is a
         * fresh instance, so never bridge an old ribbon trail to a new unit. */
        if (state->last_seen && now > state->last_seen + 250) {
            state->have_previous = false;
            state->accumulator = 0.0f;
        }
        state->last_seen = now;
        return state;
    }
    state = ri.MemAlloc(sizeof(*state));
    if (!state) return NULL;
    *state = (mdxRibbonInstance_t){ .entity_number = entity_number, .last_seen = now,
                                   .next = emitter->instances };
    emitter->instances = state;
    return state;
}

typedef struct {
    mdxModel_t const *mdx;
    mdxRibbonEmitter_t const *emitter;
    mdxMaterialLayer_t const *layer;
    VECTOR3 origin;
    VECTOR3 tail;
    VECTOR3 color;
    float alpha;
    float width;
    DWORD team;
    DWORD *spawned;
} mdx_ribbon_spawn_t;

static void MDLX_SpawnRibbonSegment(void *raw) {
    mdx_ribbon_spawn_t const *ctx = raw;
    cparticle_t *particle;
    DWORD texture_id;
    mdxTexture_t const *texture;
    FLOAT sizes[3];

    if (Vector3_len(&ctx->tail) < EPSILON || ctx->emitter->LifeSpan <= 0.0f ||
        ctx->width <= 0.0f || !ctx->layer) return;
    texture_id = ctx->layer->textureId;
    if (texture_id >= (DWORD)ctx->mdx->num_textures) return;
    texture = &ctx->mdx->textures[texture_id];
    particle = R_SpawnParticle();
    if (!particle) return;
    if (ctx->spawned) (*ctx->spawned)++;
    particle->org = ctx->origin;
    particle->tail = ctx->tail;
    particle->lifespan = ctx->emitter->LifeSpan;
    particle->time = 0.0f;
    particle->accel = (VECTOR3){ 0, 0, -ctx->emitter->Gravity };
    particle->texture = MDLX_GetTexture(ctx->mdx, ctx->team, texture_id,
                                        texture->replaceableID, NULL);
    particle->blend_mode = ctx->layer->blendMode;
    particle->rows = (BYTE)MAX(1u, ctx->emitter->Rows);
    particle->columns = (BYTE)MAX(1u, ctx->emitter->Columns);
    particle->midtime = 0xff;
    particle->color[0] = (COLOR32){
        (BYTE)(MIN(1.0f, MAX(0.0f, ctx->color.x)) * 255.0f),
        (BYTE)(MIN(1.0f, MAX(0.0f, ctx->color.y)) * 255.0f),
        (BYTE)(MIN(1.0f, MAX(0.0f, ctx->color.z)) * 255.0f),
        (BYTE)(MIN(1.0f, MAX(0.0f, ctx->alpha)) * 255.0f),
    };
    particle->color[1] = particle->color[0];
    particle->color[2] = particle->color[0];
    particle->color[2].a = 0;
    sizes[0] = sizes[1] = sizes[2] = ctx->width;
    R_EncodeParticleSize(particle, sizes);
}

/* Warcraft RIBB emitters are model-space trails driven by animated nodes. The
 * shared particle renderer already supports elongated world-space quads via
 * cparticle_t.tail, so each authored ribbon sample becomes one persistent
 * textured segment connecting the previous and current emitter position. This
 * keeps ribbon lifetime, gravity, colour, alpha, blend mode, and bone motion
 * data-driven without introducing a second transparent-geometry pipeline. */
void MDLX_RenderRibbonEmitters(renderEntity_t const *entity, mdxModel_t const *model,
                               LPCMATRIX4 model_matrix) {
    float const frame = LerpNumber(entity->oldframe, entity->frame, tr.viewDef.lerpfrac);
    DWORD total = 0, visible_count = 0, configured = 0, spawned = 0;
    static DWORD last_log[MAX_GAME_ENTITIES];
    (void)model_matrix; /* node_matrices already contain the model transform */

    FOR_EACH_LIST(mdxRibbonEmitter_t, emitter, model->ribbonEmitters) {
        total++;
        mdxRibbonInstance_t *state;
        mdxMaterial_t const *material;
        mdxMaterialLayer_t const *layer;
        VECTOR3 pivot = { 0, 0, 0 }, origin, color = emitter->Color;
        float height_above = emitter->HeightAbove;
        float height_below = emitter->HeightBelow;
        float alpha = emitter->Alpha;
        float visibility = 1.0f;
        float width;

        if (emitter->node.node_id >= MDX_MAX_NODES) continue;
        if (emitter->keytracks.Visibility)
            MDLX_GetModelKeytrackValue(model, emitter->keytracks.Visibility, frame, &visibility);
        if (visibility < EPSILON) {
            state = MDLX_RibbonInstance(emitter, entity->number);
            if (state) { state->have_previous = false; state->accumulator = 0.0f; }
            continue;
        }
        visible_count++;
        if (emitter->keytracks.HeightAbove)
            MDLX_GetModelKeytrackValue(model, emitter->keytracks.HeightAbove, frame, &height_above);
        if (emitter->keytracks.HeightBelow)
            MDLX_GetModelKeytrackValue(model, emitter->keytracks.HeightBelow, frame, &height_below);
        if (emitter->keytracks.Alpha)
            MDLX_GetModelKeytrackValue(model, emitter->keytracks.Alpha, frame, &alpha);
        if (emitter->keytracks.Color)
            MDLX_GetModelKeytrackValue(model, emitter->keytracks.Color, frame, &color);
        if (emitter->node.node_id < (DWORD)model->num_pivots)
            pivot = model->pivots[emitter->node.node_id];
        origin = Matrix4_multiply_vector3(&node_matrices[emitter->node.node_id], &pivot);
        width = MAX(0.0f, height_above + height_below);
        state = MDLX_RibbonInstance(emitter, entity->number);
        if (!state) continue;
        if (state->have_previous) {
            VECTOR3 tail = Vector3_sub(&origin, &state->previous_origin);
            material = MDLX_RibbonMaterial(model, emitter->MaterialID);
            layer = material && material->num_layers > 0 ? &material->layers[0] : NULL;
            if (layer && emitter->EmissionRate > 0 && emitter->LifeSpan > 0.0f) configured++;
            mdx_ribbon_spawn_t ctx = {
                .mdx = model, .emitter = emitter, .layer = layer,
                .origin = origin, .tail = tail, .color = color,
                .alpha = alpha * visibility, .width = width,
                .team = entity->team & TEAM_MASK, .spawned = &spawned,
            };
            R_EmitParticles((float)emitter->EmissionRate, &state->accumulator,
                            tr.viewDef.deltaTime, MDLX_SpawnRibbonSegment, &ctx);
        }
        state->previous_origin = origin;
        state->have_previous = true;
    }
    if (atoi(ri.CvarString ? ri.CvarString("wc3_attack_fx_debug", "0") : "0") >= 2 && total &&
        entity->number >= 0 && entity->number < MAX_GAME_ENTITIES &&
        (tr.viewDef.time >= last_log[entity->number] + 250 || !last_log[entity->number])) {
        mdxSequence_t const *seq = R_FindSequenceAtTime(model, entity->frame);
        fprintf(stderr,
                "[wc3fx][renderer][ribb] time=%u ent=%d seq=\"%s\" frame=%u total=%u visible=%u configured=%u spawned=%u\n",
                (unsigned)tr.viewDef.time, entity->number, seq ? seq->name : "<none>",
                (unsigned)entity->frame, (unsigned)total, (unsigned)visible_count,
                (unsigned)configured, (unsigned)spawned);
        last_log[entity->number] = tr.viewDef.time;
    }
}

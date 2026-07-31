import {
  matchProfileToRole,
  profileInputSchema,
  scoreCompleteness,
  type RoleRequirement,
} from '@opencareer/core'
import type { FastifyInstance } from 'fastify'
import { z } from 'zod'
import { HandleTakenError, type ProfileRepository } from '../repositories/profile-repository.js'

const handleParams = z.object({ handle: z.string().min(3) })

const listQuery = z.object({
  openToWork: z
    .enum(['true', 'false'])
    .optional()
    .transform((value) => (value === undefined ? undefined : value === 'true')),
})

const matchBody = z.object({
  requirements: z
    .array(
      z.object({
        skillId: z.string().min(1),
        minimumProficiency: z.enum(['beginner', 'intermediate', 'advanced', 'expert']),
        required: z.boolean().default(true),
      }),
    )
    .max(50),
})

export function registerProfileRoutes(app: FastifyInstance, repository: ProfileRepository): void {
  app.get('/v1/profiles', async (request, reply) => {
    const query = listQuery.safeParse(request.query)
    if (!query.success) {
      return reply.code(400).send({ error: 'invalid_query', details: query.error.flatten() })
    }

    return { data: await repository.list({ openToWork: query.data.openToWork }) }
  })

  app.post('/v1/profiles', async (request, reply) => {
    const body = profileInputSchema.safeParse(request.body)
    if (!body.success) {
      return reply.code(400).send({ error: 'invalid_profile', details: body.error.flatten() })
    }

    try {
      const profile = await repository.create(body.data)
      return reply.code(201).header('location', `/v1/profiles/${profile.handle}`).send(profile)
    } catch (error) {
      if (error instanceof HandleTakenError) {
        return reply.code(409).send({ error: 'handle_taken' })
      }
      throw error
    }
  })

  app.get('/v1/profiles/:handle', async (request, reply) => {
    const params = handleParams.parse(request.params)
    const profile = await repository.findByHandle(params.handle)
    if (!profile) return reply.code(404).send({ error: 'profile_not_found' })

    return profile
  })

  app.put('/v1/profiles/:handle', async (request, reply) => {
    const params = handleParams.parse(request.params)
    const body = profileInputSchema.safeParse(request.body)
    if (!body.success) {
      return reply.code(400).send({ error: 'invalid_profile', details: body.error.flatten() })
    }

    try {
      const profile = await repository.replace(params.handle, body.data)
      if (!profile) return reply.code(404).send({ error: 'profile_not_found' })

      return profile
    } catch (error) {
      if (error instanceof HandleTakenError) {
        return reply.code(409).send({ error: 'handle_taken' })
      }
      throw error
    }
  })

  app.delete('/v1/profiles/:handle', async (request, reply) => {
    const params = handleParams.parse(request.params)
    const deleted = await repository.delete(params.handle)

    return reply.code(deleted ? 204 : 404).send(deleted ? undefined : { error: 'profile_not_found' })
  })

  /** Portable export — the document the person owns and can take elsewhere. */
  app.get('/v1/profiles/:handle/export', async (request, reply) => {
    const params = handleParams.parse(request.params)
    const profile = await repository.findByHandle(params.handle)
    if (!profile) return reply.code(404).send({ error: 'profile_not_found' })

    return reply
      .header('content-type', 'application/json; charset=utf-8')
      .header('content-disposition', `attachment; filename="${profile.handle}.opp.json"`)
      .send(profile)
  })

  app.get('/v1/profiles/:handle/completeness', async (request, reply) => {
    const params = handleParams.parse(request.params)
    const profile = await repository.findByHandle(params.handle)
    if (!profile) return reply.code(404).send({ error: 'profile_not_found' })

    return scoreCompleteness(profile)
  })

  app.post('/v1/profiles/:handle/match', async (request, reply) => {
    const params = handleParams.parse(request.params)
    const body = matchBody.safeParse(request.body)
    if (!body.success) {
      return reply.code(400).send({ error: 'invalid_requirements', details: body.error.flatten() })
    }

    const profile = await repository.findByHandle(params.handle)
    if (!profile) return reply.code(404).send({ error: 'profile_not_found' })

    return matchProfileToRole(profile, body.data.requirements as RoleRequirement[])
  })
}

import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { FastifyInstance } from 'fastify'
import { buildServer } from './server.js'

const validProfile = {
  handle: 'ana-souza',
  fullName: 'Ana Souza',
  headline: 'Backend engineer focused on distributed systems',
  openToWork: true,
  skills: [{ id: 'go', name: 'Go', proficiency: 'expert', verifications: ['assessment:go-2025'] }],
}

describe('OpenCareer API', () => {
  let app: FastifyInstance

  beforeEach(async () => {
    app = buildServer()
    await app.ready()
  })

  afterEach(async () => {
    await app.close()
  })

  const create = (payload: unknown = validProfile) =>
    app.inject({ method: 'POST', url: '/v1/profiles', payload })

  it('reports health with the profile format version', async () => {
    const response = await app.inject({ method: 'GET', url: '/healthz' })

    expect(response.statusCode).toBe(200)
    expect(response.json()).toMatchObject({ status: 'ok', oppVersion: '0.1.0' })
  })

  it('creates a profile and returns its location', async () => {
    const response = await create()

    expect(response.statusCode).toBe(201)
    expect(response.headers['location']).toBe('/v1/profiles/ana-souza')
    expect(response.json()).toMatchObject({ handle: 'ana-souza', oppVersion: '0.1.0' })
  })

  it('rejects an invalid profile with field-level details', async () => {
    const response = await create({ ...validProfile, handle: 'NOT VALID' })

    expect(response.statusCode).toBe(400)
    expect(response.json().details.fieldErrors.handle).toBeDefined()
  })

  it('refuses a duplicate handle', async () => {
    await create()
    const response = await create()

    expect(response.statusCode).toBe(409)
    expect(response.json()).toEqual({ error: 'handle_taken' })
  })

  it('filters the listing by availability', async () => {
    await create()
    await create({ ...validProfile, handle: 'bruno-lima', openToWork: false })

    const open = await app.inject({ method: 'GET', url: '/v1/profiles?openToWork=true' })

    expect(open.statusCode).toBe(200)
    expect(open.json().data.map((p: { handle: string }) => p.handle)).toEqual(['ana-souza'])
  })

  it('returns 404 for an unknown profile', async () => {
    const response = await app.inject({ method: 'GET', url: '/v1/profiles/nobody-here' })

    expect(response.statusCode).toBe(404)
    expect(response.json()).toEqual({ error: 'profile_not_found' })
  })

  it('replaces a profile in place, keeping its id', async () => {
    const created = await create()
    const response = await app.inject({
      method: 'PUT',
      url: '/v1/profiles/ana-souza',
      payload: { ...validProfile, headline: 'Staff engineer, payments' },
    })

    expect(response.statusCode).toBe(200)
    expect(response.json()).toMatchObject({
      id: created.json().id,
      headline: 'Staff engineer, payments',
    })
  })

  it('serves a portable export as a downloadable OPP document', async () => {
    await create()
    const response = await app.inject({ method: 'GET', url: '/v1/profiles/ana-souza/export' })

    expect(response.statusCode).toBe(200)
    expect(response.headers['content-disposition']).toBe('attachment; filename="ana-souza.opp.json"')
    expect(response.json().oppVersion).toBe('0.1.0')
  })

  it('explains a match against role requirements', async () => {
    await create()
    const response = await app.inject({
      method: 'POST',
      url: '/v1/profiles/ana-souza/match',
      payload: {
        requirements: [
          { skillId: 'go', minimumProficiency: 'advanced', required: true },
          { skillId: 'kubernetes', minimumProficiency: 'intermediate', required: false },
        ],
      },
    })

    expect(response.statusCode).toBe(200)
    expect(response.json()).toMatchObject({
      eligible: true,
      explanations: [
        { skillId: 'go', status: 'met', verified: true },
        { skillId: 'kubernetes', status: 'missing' },
      ],
    })
  })

  it('scores completeness and suggests the next step', async () => {
    await create()
    const response = await app.inject({ method: 'GET', url: '/v1/profiles/ana-souza/completeness' })

    expect(response.statusCode).toBe(200)
    expect(response.json().suggestions[0].key).toBe('video-intro')
  })

  it('deletes a profile once', async () => {
    await create()

    expect((await app.inject({ method: 'DELETE', url: '/v1/profiles/ana-souza' })).statusCode).toBe(204)
    expect((await app.inject({ method: 'DELETE', url: '/v1/profiles/ana-souza' })).statusCode).toBe(404)
  })
})

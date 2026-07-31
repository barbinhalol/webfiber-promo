import { OPP_VERSION } from '@opencareer/core'
import Fastify, { type FastifyInstance } from 'fastify'
import { InMemoryProfileRepository } from './repositories/in-memory-profile-repository.js'
import type { ProfileRepository } from './repositories/profile-repository.js'
import { registerProfileRoutes } from './routes/profiles.js'

export interface ServerOptions {
  repository?: ProfileRepository
  logger?: boolean
}

export function buildServer(options: ServerOptions = {}): FastifyInstance {
  const app = Fastify({ logger: options.logger ?? false })
  const repository = options.repository ?? new InMemoryProfileRepository()

  app.get('/healthz', async () => ({ status: 'ok', oppVersion: OPP_VERSION }))

  registerProfileRoutes(app, repository)

  return app
}

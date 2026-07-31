import { buildServer } from './server.js'

const port = Number(process.env['PORT'] ?? 3000)
const host = process.env['HOST'] ?? '0.0.0.0'

const app = buildServer({ logger: true })

try {
  await app.listen({ port, host })
} catch (error) {
  app.log.error(error)
  process.exit(1)
}

for (const signal of ['SIGINT', 'SIGTERM'] as const) {
  process.once(signal, () => {
    void app.close().then(() => process.exit(0))
  })
}

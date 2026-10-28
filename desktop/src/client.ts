export type BackendMessage = {
  id?: number
  result?: unknown
  error?: string
  event?: string
  data?: unknown
}

type Send = (message: string) => Promise<void>
type Subscribe = (handler: (message: string) => void) => Promise<() => void>

export function createClient(send: Send, subscribe: Subscribe, idStart = 0) {
  let nextId = idStart
  const pending = new Map<number, { resolve: (value: unknown) => void; reject: (error: Error) => void }>()

  return {
    async connect(onEvent: (message: BackendMessage) => void) {
      return subscribe(raw => {
        let message: BackendMessage
        try { message = JSON.parse(raw) as BackendMessage } catch { return }
        if (typeof message.id === 'number') {
          const waiter = pending.get(message.id)
          if (!waiter) return
          pending.delete(message.id)
          if (message.error) waiter.reject(new Error(message.error))
          else waiter.resolve(message.result)
        } else {
          if (message.event === 'error') {
            for (const waiter of pending.values()) waiter.reject(new Error(String(message.data)))
            pending.clear()
          }
          onEvent(message)
        }
      })
    },
    command(name: string, payload: Record<string, unknown> = {}): Promise<unknown> {
      const id = ++nextId
      return new Promise((resolve, reject) => {
        pending.set(id, { resolve, reject })
        void send(JSON.stringify({ id, command: name, payload }) + '\n').catch(error => {
          pending.delete(id)
          reject(error)
        })
      })
    },
  }
}

declare global {
  interface Window {
    __TAURI__?: {
      core: { invoke: (name: string, args: Record<string, unknown>) => Promise<void> }
      event: { listen: (name: string, handler: (event: { payload: string }) => void) => Promise<() => void> }
    }
  }
}

export function tauriClient(idStart = 0) {
  const api = window.__TAURI__
  if (!api) throw new Error('Open this interface through the Tauri desktop app.')
  return createClient(
    message => api.core.invoke('send_backend', { message }),
    handler => api.event.listen('backend-message', event => handler(event.payload)),
    idStart,
  )
}

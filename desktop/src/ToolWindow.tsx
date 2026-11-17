import { useEffect, useRef, useState } from 'react'
import Diagnostics, { type Powertrain } from './Diagnostics'
import { tauriClient, type BackendMessage } from './client'
import type { State } from './App'

export default function ToolWindow({ view }: { view: 'telemetry' }) {
  const clientRef = useRef<ReturnType<typeof tauriClient> | null>(null)
  const [state, setState] = useState<State | null>(null)
  const [powertrain, setPowertrain] = useState<Powertrain | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let disposed = false
    let disconnect = () => {}
    let timer: number | undefined
    const keys = new Set<string>()
    const client = tauriClient(1_000_000_000)
    clientRef.current = client
    const report = (reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason))
    const updatePedals = () => void client.command('pedals', {
      throttle: Number(keys.has('w')), brake: Number(keys.has('s')),
    }).catch(report)
    const keydown = (event: KeyboardEvent) => {
      if (event.repeat || event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement || event.target instanceof HTMLSelectElement) return
      const key = (event.code === 'KeyW' ? 'w' : event.code === 'KeyS' ? 's' : event.key.toLowerCase())  // physical key: works in any keyboard layout
      if (key === 'w' || key === 's') { event.preventDefault(); keys.add(key); updatePedals() }
    }
    const keyup = (event: KeyboardEvent) => {
      if (keys.delete((event.code === 'KeyW' ? 'w' : event.code === 'KeyS' ? 's' : event.key.toLowerCase()))) { event.preventDefault(); updatePedals() }
    }
    const blur = () => {
      keys.clear()
      void client.command('focus', { value: false }).catch(report)
    }
    const focus = () => void client.command('focus', { value: true }).catch(report)
    window.addEventListener('keydown', keydown)
    window.addEventListener('keyup', keyup)
    window.addEventListener('blur', blur)
    window.addEventListener('focus', focus)
    const update = (message: BackendMessage) => {
      if (message.event === 'state') setState(message.data as State)
      if (message.event === 'error') setError(String(message.data))
    }
    void client.connect(update).then(stop => {
      if (disposed) { stop(); return }
      disconnect = stop
      void client.command('snapshot').then(snapshot => { if (!disposed) setState(snapshot as State) }).catch(report)
      if (document.hasFocus()) focus()
      timer = window.setInterval(() => {
        void client.command('powertrain').then(data => { if (!disposed) setPowertrain(data as Powertrain) }).catch(report)
      }, 100)
    }).catch(reason => { if (!disposed) report(reason) })
    return () => {
      disposed = true
      if (timer !== undefined) window.clearInterval(timer)
      window.removeEventListener('keydown', keydown)
      window.removeEventListener('keyup', keyup)
      window.removeEventListener('blur', blur)
      window.removeEventListener('focus', focus)
      disconnect()
      clientRef.current = null
    }
  }, [view])

  return <main className="tool-window">
    {error && <p role="alert" className="mb-4 text-red-300">{error}</p>}
    {!state ? <p className="text-neutral-400">Connecting to simulator…</p> : <Diagnostics
      powertrain={powertrain}
      rpm={state.rpm}
      maxRpm={state.maxRpm}
      running={state.running}
      sweepActive={state.soundSweepActive}
      onSweep={() => { void clientRef.current?.command('sweep') }}
    />}
  </main>
}

import React from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

// Startup timeline (printed in the terminal that runs the app).
const mark = (label: string) => { void window.__TAURI__?.core.invoke('startup_mark', { label }) }
mark('page script started')

if (import.meta.env.DEV) {
  import('react-grab')
}

const requestedWindow = new URLSearchParams(window.location.search).get('window')
if (requestedWindow === 'overlay') document.documentElement.classList.add('overlay-window')
const toolView = requestedWindow === 'telemetry' || requestedWindow === 'sound-signal' ? requestedWindow : null

// Load only the code the window needs: the startup chooser must not wait for the whole app.
async function view() {
  if (requestedWindow === 'chooser') { const { default: Chooser } = await import('./ChooserWindow'); return <Chooser /> }
  if (toolView) { const { default: Tool } = await import('./ToolWindow'); return <Tool view={toolView} /> }
  const { default: App } = await import('./App')
  return <App overlay={requestedWindow === 'overlay'} />
}

void view().then(element => {
  createRoot(document.getElementById('root')!).render(<React.StrictMode>{element}</React.StrictMode>)
  requestAnimationFrame(() => mark(`${requestedWindow ?? 'dashboard'} rendered`))
})

import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import ToolWindow from './ToolWindow'
import './style.css'

if (import.meta.env.DEV) {
  import('react-grab')
}

const requestedWindow = new URLSearchParams(window.location.search).get('window')
const toolView = requestedWindow === 'telemetry' || requestedWindow === 'sound-signal' ? requestedWindow : null

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>{toolView ? <ToolWindow view={toolView} /> : <App />}</React.StrictMode>,
)

import React, { useState, useEffect } from 'react'

// Prefer an explicit local backend port that we run in this workspace (8001).
// Allow overriding via VITE_API_BASE for other environments.
const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8001'

export default function App() {
  const [apiBase, setApiBase] = useState(DEFAULT_API_BASE)
  const [code, setCode] = useState('say 1')
  const [output, setOutput] = useState('')
  const [warnings, setWarnings] = useState([])
  const [eco, setEco] = useState(null)
  const [scripts, setScripts] = useState([])
  const [title, setTitle] = useState('My Script')

  useEffect(() => {
    fetch(`${apiBase}/scripts`).then(r => r.json()).then(setScripts).catch(() => {})
  }, [apiBase])

  async function runCode() {
    setOutput('Running...')
    setWarnings([])
    setEco(null)
    try {
      const resp = await fetch(`${apiBase}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, inputs: {} }),
      })
      if (!resp.ok) {
        const text = await resp.text().catch(() => '')
        setOutput(`HTTP ${resp.status}: ${text}`)
        return
      }
      const j = await resp.json()
      setOutput(j.output || '')
      setWarnings(j.warnings || [])
      setEco(j.eco || null)
    } catch (e) {
      // show exception details (network/CORS failures appear here)
      setOutput('Error: ' + (e && e.message ? e.message : String(e)))
    }
  }

  async function saveScript() {
    try {
      const resp = await fetch(`${apiBase}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, code }),
      })
      const j = await resp.json()
      if (j.script_id) {
        setScripts(s => [...s, { id: j.script_id, title }])
      }
    } catch (e) {
      // ignore
    }
  }

  return (
    <div className="container">
      <h1>PHINEAS EcoLang Playground</h1>
      <div className="panel">
        <label style={{ display: 'block', marginBottom: 8 }}>
          <span>API Base URL: </span>
          <input
            value={apiBase}
            onChange={e => setApiBase(e.target.value)}
            style={{ width: 320, marginLeft: 8 }}
            placeholder="http://127.0.0.1:8001"
          />
        </label>
        <textarea value={code} onChange={e => setCode(e.target.value)} />
        <div className="controls">
          <button onClick={runCode}>Run</button>
          <input value={title} onChange={e => setTitle(e.target.value)} />
          <button onClick={saveScript}>Save</button>
        </div>
      </div>

      <div className="panel">
        <h2>Output</h2>
        <pre className="output">{output}</pre>
        {warnings.length > 0 && (
          <div className="warnings">
            <h3>Warnings</h3>
            <ul>{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
          </div>
        )}

        {eco && (
          <div className="eco">
            <h3>Eco stats</h3>
            <pre>{JSON.stringify(eco, null, 2)}</pre>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Scripts</h2>
        <ul>
          {scripts.map(s => (
            <li key={s.id}>{s.title}</li>
          ))}
        </ul>
      </div>
    </div>
  )
}

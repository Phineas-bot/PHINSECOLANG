import React, { useState, useEffect } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function App() {
  const [code, setCode] = useState('say 1')
  const [output, setOutput] = useState('')
  const [warnings, setWarnings] = useState([])
  const [eco, setEco] = useState(null)
  const [scripts, setScripts] = useState([])
  const [title, setTitle] = useState('My Script')

  useEffect(() => {
    fetch(`${API_BASE}/scripts`).then(r => r.json()).then(setScripts).catch(() => {})
  }, [])

  async function runCode() {
    setOutput('Running...')
    setWarnings([])
    setEco(null)
    try {
      const resp = await fetch(`${API_BASE}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, inputs: {} }),
      })
      const j = await resp.json()
      setOutput(j.output || '')
      setWarnings(j.warnings || [])
      setEco(j.eco || null)
    } catch (e) {
      setOutput('Error: ' + e.message)
    }
  }

  async function saveScript() {
    try {
      const resp = await fetch(`${API_BASE}/save`, {
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
      <h1>EcoLang Playground</h1>
      <div className="panel">
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

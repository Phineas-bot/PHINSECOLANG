import React, { useState, useEffect, useMemo } from 'react'

// Prefer an explicit local backend port that we run in this workspace (8001).
// Allow overriding via VITE_API_BASE for other environments.
const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8001'

function EcoCard({ eco }) {
  if (!eco) return null
  const kWh = eco.energy_kWh ?? eco.energyKWh ?? eco.energy_kwh
  const co2 = eco.co2_g ?? eco.co2G
  const j = eco.energy_J ?? eco.energyJ
  const tips = eco.tips || []
  return (
    <div className="eco">
      <h3>Eco impact</h3>
      <div className="eco-grid">
        <div><span className="label">Ops</span><span>{eco.total_ops}</span></div>
        <div><span className="label">Joules</span><span>{j?.toFixed ? j.toFixed(6) : j}</span></div>
        <div><span className="label">kWh</span><span>{kWh?.toExponential ? kWh.toExponential(3) : kWh}</span></div>
        <div><span className="label">CO₂ (g)</span><span>{co2?.toFixed ? co2.toFixed(6) : co2}</span></div>
      </div>
      {tips.length > 0 && (
        <ul className="tips">
          {tips.map((t, i) => <li key={i}>💡 {t}</li>)}
        </ul>
      )}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('editor')
  const [apiBase, setApiBase] = useState(() => localStorage.getItem('apiBase') || DEFAULT_API_BASE)
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')

  const [code, setCode] = useState('say "Hello Eco"\n')
  const [inputsText, setInputsText] = useState('{"answer":"yes"}')
  const inputsObj = useMemo(() => {
    try { return JSON.parse(inputsText || '{}') } catch { return {} }
  }, [inputsText])

  const [output, setOutput] = useState('')
  const [warnings, setWarnings] = useState([])
  const [eco, setEco] = useState(null)

  const [scripts, setScripts] = useState([])
  const [title, setTitle] = useState('My Script')
  const [currentScriptId, setCurrentScriptId] = useState(null)
  const [stats, setStats] = useState([])

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    localStorage.setItem('apiBase', apiBase)
    loadScripts()
  }, [apiBase])

  useEffect(() => {
    const onKey = (e) => {
      // Ctrl+Enter: Run; Ctrl+S: Save
      if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); runCode() }
      if (e.ctrlKey && (e.key === 's' || e.key === 'S')) { e.preventDefault(); saveScript() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  async function loadScripts() {
    try {
      const r = await fetch(`${apiBase}/scripts`)
      const j = await r.json()
      setScripts(j || [])
    } catch {}
  }

  async function runCode() {
    setOutput('Running...')
    setWarnings([])
    setEco(null)
    try {
      const body = { code, inputs: inputsObj }
      if (currentScriptId) body.script_id = currentScriptId
      const resp = await fetch(`${apiBase}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const j = await resp.json().catch(() => ({}))
      if (!resp.ok) {
        setOutput(`HTTP ${resp.status}: ${JSON.stringify(j)}`)
        return
      }
      setOutput(j.output || '')
      setWarnings(j.warnings || [])
      setEco(j.eco || null)
      if (currentScriptId) fetchStats(currentScriptId)
    } catch (e) {
      setOutput('Error: ' + (e?.message || String(e)))
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
        setCurrentScriptId(j.script_id)
        await loadScripts()
      }
    } catch {}
  }

  async function openScript(id) {
    try {
      const r = await fetch(`${apiBase}/scripts/${id}`)
      const s = await r.json()
      if (!s || s.error) return
      setCode(s.code_text || '')
      setTitle(s.title || 'Untitled')
      setCurrentScriptId(s.script_id)
      setTab('editor')
      fetchStats(s.script_id)
    } catch {}
  }

  async function fetchStats(id) {
    try {
      const r = await fetch(`${apiBase}/stats?script_id=${id}`)
      const j = await r.json()
      setStats(Array.isArray(j) ? j : [])
    } catch {}
  }

  function clearOutput() {
    setOutput('')
    setWarnings([])
    setEco(null)
  }

  return (
    <div className={`container ${theme === 'dark' ? 'theme-dark' : ''}`}>
      <header className="header">
        <h1>PHINEAS EcoLang Playground</h1>
        <div className="header-controls">
          <label className="api-base">
            <span>API:</span>
            <input value={apiBase} onChange={e => setApiBase(e.target.value)} placeholder="http://127.0.0.1:8001" />
          </label>
          <button className="theme" onClick={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))}>
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </header>

      <nav className="tabs">
        <button className={tab==='editor'? 'active':''} onClick={() => setTab('editor')}>Editor</button>
        <button className={tab==='scripts'? 'active':''} onClick={() => { setTab('scripts'); loadScripts() }}>Saved Scripts</button>
        <button className={tab==='about'? 'active':''} onClick={() => setTab('about')}>About</button>
      </nav>

      {tab === 'editor' && (
        <div className="panel">
          <div className="editor-grid">
            <div>
              <label className="block-label">Title</label>
              <input value={title} onChange={e => setTitle(e.target.value)} />
              <label className="block-label">Code</label>
              <textarea value={code} onChange={e => setCode(e.target.value)} spellCheck={false} />
              <label className="block-label">Inputs (JSON)</label>
              <textarea className="inputs" value={inputsText} onChange={e => setInputsText(e.target.value)} spellCheck={false} />
              <div className="controls">
                <button onClick={runCode} title="Ctrl+Enter">▶ Run</button>
                <button onClick={saveScript} title="Ctrl+S">💾 Save</button>
                <button onClick={clearOutput}>🧹 Clear</button>
              </div>
            </div>
            <div>
              <h2>Output</h2>
              <pre className="output" aria-live="polite">{output}</pre>
              {warnings.length > 0 && (
                <div className="warnings">
                  <h3>Warnings</h3>
                  <ul>{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>
                </div>
              )}
              <EcoCard eco={eco} />
            </div>
          </div>
        </div>
      )}

      {tab === 'scripts' && (
        <div className="panel">
          <div className="scripts-grid">
            <div>
              <h2>Saved Scripts</h2>
              <ul className="list">
                {scripts.map(s => (
                  <li key={s.script_id}>
                    <div className="row">
                      <div>
                        <div className="title">{s.title}</div>
                        <div className="meta">{new Date(s.created_at).toLocaleString()}</div>
                      </div>
                      <div className="actions">
                        <button onClick={() => openScript(s.script_id)}>Open</button>
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2>Run History {currentScriptId ? `(script ${currentScriptId})` : ''}</h2>
              {currentScriptId ? (
                <table className="table">
                  <thead>
                    <tr>
                      <th>When</th><th>kWh</th><th>CO₂ (g)</th><th>Ops</th><th>Duration (ms)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.map(r => (
                      <tr key={r.run_id}>
                        <td>{new Date(r.created_at).toLocaleString()}</td>
                        <td>{(r.energy_kWh ?? r.energy_kwh)?.toExponential?.(3) ?? r.energy_kWh}</td>
                        <td>{(r.co2_g)?.toFixed?.(6) ?? r.co2_g}</td>
                        <td>{r.total_ops}</td>
                        <td>{r.duration_ms}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p>Select a script to view its history.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'about' && (
        <div className="panel">
          <h2>About EcoLang</h2>
          <p>EcoLang is a lightweight educational language that teaches programming and green computing. Write code, run it securely on the backend, and get eco impact estimates and tips.</p>
          <ul>
            <li>Core statements: say, let, warn, ask, if/then/else/end, repeat N times … end, ecoTip, savePower N</li>
            <li>New: func name [args] … end; return; call name with args [into var]</li>
            <li>Keyboard: Ctrl+Enter to Run, Ctrl+S to Save</li>
          </ul>
        </div>
      )}
    </div>
  )
}

import React, { useState, useEffect, useMemo } from 'react'
import tutoMd from './docs/tuto.md?raw'

// Prefer an explicit local backend port that we run in this workspace (8000).
// Allow overriding via VITE_API_BASE for other environments.
const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

// Minimal markdown -> JSX renderer (headings, lists, code fences, paragraphs)
function renderTutorial(md, opts = {}) {
  const { onTryCode, onTryInputs } = opts
  const lines = (md || '').split('\n')
  const out = []
  let i = 0, key = 0
  const push = (el) => out.push(React.cloneElement(el, { key: key++ }))

  while (i < lines.length) {
    const line = lines[i]

    // Fenced code block ```
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim()
      i++
      const code = []
      while (i < lines.length && !lines[i].startsWith('```')) {
        code.push(lines[i])
        i++
      }
      // skip closing ```
      if (i < lines.length && lines[i].startsWith('```')) i++
      const src = code.join('\n')
      const langLc = (lang || '').toLowerCase()
      const canTryCode = langLc !== 'json'
      const canTryInputs = langLc === 'json'
      push(
        <div className="codebox">
          <pre className={`md-code ${lang ? 'lang-' + lang : ''}`}><code>{src}</code></pre>
          <div className="code-actions">
            {canTryCode && (
              <button type="button" className="try-btn" onClick={() => onTryCode && onTryCode(src)}>Try it</button>
            )}
            {canTryInputs && (
              <button type="button" className="inputs-btn" onClick={() => onTryInputs && onTryInputs(src)}>Use as inputs</button>
            )}
          </div>
        </div>
      )
      continue
    }

    // Headings
    if (/^###\s+/.test(line)) { push(<h3>{line.replace(/^###\s+/, '')}</h3>); i++; continue }
    if (/^##\s+/.test(line))  { push(<h2>{line.replace(/^##\s+/, '')}</h2>);  i++; continue }
    if (/^#\s+/.test(line))   { push(<h1>{line.replace(/^#\s+/, '')}</h1>);   i++; continue }

    // Lists
    if (/^\-\s+/.test(line)) {
      const items = []
      while (i < lines.length && /^\-\s+/.test(lines[i])) {
        items.push(lines[i].replace(/^\-\s+/, ''))
        i++
      }
      push(<ul>{items.map((t, idx) => <li key={idx}>{t}</li>)}</ul>)
      continue
    }

    // Blank -> skip (also acts as paragraph separator)
    if (!line.trim()) { i++; continue }

    // Paragraph: accumulate until blank or block
    const para = [line]
    i++
    while (i < lines.length && lines[i].trim() && !/^\-\s+/.test(lines[i]) && !lines[i].startsWith('```') && !/^#{1,3}\s+/.test(lines[i])) {
      para.push(lines[i])
      i++
    }
    push(<p>{para.join(' ')}</p>)
  }

  return (<div className="about">{out}</div>)
}

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

function ErrorPanel({ err, codeText }) {
  if (!err) return null
  const line = err.line || 1
  const col = err.column || 1
  const lines = (codeText || '').split('\n')
  const text = (err.context?.line_text) || lines[line - 1] || ''
  const caret = ' '.repeat(Math.max(0, col - 1)) + '^'
  return (
    <div className="errors" role="alert" aria-live="assertive">
      <h3>Error</h3>
      <div className="err-summary">
        <strong>{err.code}</strong>: {err.message}
        {Number.isFinite(line) && Number.isFinite(col) ? (
          <span> (line {line}, col {col})</span>
        ) : null}
      </div>
      <pre className="codeframe">
{text}\n
{caret}
      </pre>
      {err.hint && <div className="hint">Hint: {err.hint}</div>}
    </div>
  )
}

export default function App() {
  const [tab, setTab] = useState('editor')
  const [apiBase, setApiBase] = useState(() => localStorage.getItem('apiBase') || DEFAULT_API_BASE)
  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'light')
  const [token, setToken] = useState(() => localStorage.getItem('token') || '')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authMode, setAuthMode] = useState('login')

  const [code, setCode] = useState('say "Hello Eco"\n')
  const [inputsText, setInputsText] = useState('{"answer":"yes"}')
  const [inputsMode, setInputsMode] = useState(() => localStorage.getItem('inputsMode') || 'json')
  const [formRows, setFormRows] = useState([])
  const [formNotice, setFormNotice] = useState('')
  const inputsObj = useMemo(() => {
    try { return JSON.parse(inputsText || '{}') } catch { return {} }
  }, [inputsText])

  const [output, setOutput] = useState('')
  const [warnings, setWarnings] = useState([])
  const [eco, setEco] = useState(null)
  const [error, setError] = useState(null)

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
    if (token) localStorage.setItem('token', token); else localStorage.removeItem('token')
  }, [token])

  useEffect(() => {
    const onKey = (e) => {
      // Ctrl+Enter: Run; Ctrl+S: Save
      if (e.ctrlKey && e.key === 'Enter') { e.preventDefault(); runCode() }
      if (e.ctrlKey && (e.key === 's' || e.key === 'S')) { e.preventDefault(); saveScript() }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  // Persist inputs mode
  useEffect(() => { localStorage.setItem('inputsMode', inputsMode) }, [inputsMode])

  // Helpers: JSON <-> rows
  function jsonToRows(text) {
    try {
      const obj = JSON.parse(text || '{}')
      if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return []
      return Object.entries(obj).map(([k, v]) => {
        if (v === null) return { key: k, type: 'null', value: '' }
        if (Array.isArray(v)) return { key: k, type: 'array', value: JSON.stringify(v) }
        switch (typeof v) {
          case 'boolean': return { key: k, type: 'boolean', value: String(v) }
          case 'number': return { key: k, type: 'number', value: String(v) }
          case 'object': return { key: k, type: 'object', value: JSON.stringify(v) }
          default: return { key: k, type: 'string', value: String(v) }
        }
      })
    } catch {
      return []
    }
  }

  function rowsToJson(rows) {
    const obj = {}
    for (const r of rows) {
      const k = (r.key || '').trim()
      if (!k) continue
      const t = r.type || 'string'
      const v = r.value
      try {
        if (t === 'string') obj[k] = String(v ?? '')
        else if (t === 'number') {
          const n = Number(v)
          if (!Number.isFinite(n)) throw new Error('Invalid number')
          obj[k] = n
        } else if (t === 'boolean') {
          const b = String(v).toLowerCase()
          obj[k] = b === 'true'
        } else if (t === 'null') {
          obj[k] = null
        } else if (t === 'array' || t === 'object') {
          const parsed = JSON.parse(v || (t === 'array' ? '[]' : '{}'))
          obj[k] = parsed
        } else {
          obj[k] = v
        }
      } catch (e) {
        // Skip invalid entries; caller can show a notice
      }
    }
    return JSON.stringify(obj)
  }

  // When switching to form mode, hydrate rows from JSON
  useEffect(() => {
    if (inputsMode === 'form') {
      const rows = jsonToRows(inputsText)
      setFormRows(rows)
      // Show a notice if JSON was invalid and produced empty rows while non-empty text
      try {
        JSON.parse(inputsText || '{}')
        setFormNotice('')
      } catch {
        setFormNotice('Current JSON is invalid. Starting form with empty/default values.')
      }
    } else {
      setFormNotice('')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [inputsMode])

  async function loadScripts() {
    try {
  const r = await fetch(`${apiBase}/scripts`, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} })
      const j = await r.json()
      setScripts(j || [])
    } catch {}
  }

  async function runCode() {
    setOutput('Running...')
    setWarnings([])
    setEco(null)
    setError(null)
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
      setError(j.errors || null)
      if (currentScriptId) fetchStats(currentScriptId)
    } catch (e) {
      setOutput('Error: ' + (e?.message || String(e)))
    }
  }

  async function saveScript() {
    try {
      const resp = await fetch(`${apiBase}/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { 'Authorization': `Bearer ${token}` } : {}) },
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
  const r = await fetch(`${apiBase}/scripts/${id}`, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} })
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
  const r = await fetch(`${apiBase}/stats?script_id=${id}`, { headers: token ? { 'Authorization': `Bearer ${token}` } : {} })
      const j = await r.json()
      setStats(Array.isArray(j) ? j : [])
    } catch {}
  }

  function clearOutput() {
    setOutput('')
    setWarnings([])
    setEco(null)
  setError(null)
  }

  async function doAuth(mode) {
    try {
      const path = mode === 'register' ? '/auth/register' : '/auth/login'
      const resp = await fetch(`${apiBase}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
      })
      const j = await resp.json()
      if (!resp.ok) return
      setToken(j.access_token || '')
      setPassword('')
      setTab('editor')
      loadScripts()
    } catch {}
  }

  function logout() {
    setToken('')
    setUsername('')
    setPassword('')
    setScripts([])
    setCurrentScriptId(null)
    setStats([])
    setTab('landing')
  }

  const isAuthed = !!token
  const showEditor = isAuthed && tab !== 'about' && tab !== 'scripts' ? 'editor' : tab

  return (
    <div className={`container ${theme === 'dark' ? 'theme-dark' : ''}`}>
      <header className="header">
        <h1>PHINEAS EcoLang Playground</h1>
        <div className="header-controls">
          <label className="api-base">
            <span>API:</span>
            <input value={apiBase} onChange={e => setApiBase(e.target.value)} placeholder="http://127.0.0.1:8001" />
          </label>
          {isAuthed ? (
            <button onClick={logout}>Logout</button>
          ) : (
            <button onClick={() => setTab('landing')}>Login / Sign up</button>
          )}
          <button className="theme" onClick={() => setTheme(t => (t === 'dark' ? 'light' : 'dark'))}>
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </header>

      <nav className="tabs">
        <button className={showEditor==='editor'? 'active':''} onClick={() => setTab('editor')} disabled={!isAuthed}>Editor</button>
        <button className={tab==='scripts'? 'active':''} onClick={() => { setTab('scripts'); loadScripts() }}>Saved Scripts</button>
        <button className={tab==='about'? 'active':''} onClick={() => setTab('about')}>About</button>
      </nav>

      {!isAuthed && (
        <div className="panel landing">
          <h2>Welcome to EcoLang</h2>
          <p>Learn programming and green computing with a fun, minimal language. Create an account or log in to start coding.</p>
          <div className="landing-grid">
            <form className="auth" onSubmit={(e)=>{e.preventDefault(); doAuth(authMode)}}>
              <div className="field">
                <label>Username</label>
                <input value={username} onChange={e=>setUsername(e.target.value)} required />
              </div>
              <div className="field">
                <label>Password</label>
                <input type="password" value={password} onChange={e=>setPassword(e.target.value)} required />
              </div>
              <div className="field inline">
                <label><input type="radio" checked={authMode==='login'} onChange={()=>setAuthMode('login')} /> Login</label>
                <label><input type="radio" checked={authMode==='register'} onChange={()=>setAuthMode('register')} /> Sign up</label>
              </div>
              <div className="actions"><button type="submit">{authMode==='login' ? 'Login' : 'Create account'}</button></div>
            </form>
          </div>
        </div>
      )}

      {isAuthed && showEditor === 'editor' && (
        <div className="panel">
          <div className="editor-grid">
            <div>
              <label className="block-label">Title</label>
              <input value={title} onChange={e => setTitle(e.target.value)} />
              <label className="block-label">Code</label>
              <textarea value={code} onChange={e => setCode(e.target.value)} spellCheck={false} />
              <div className="inputs-header">
                <span className="block-label">Inputs</span>
                <div className="inputs-tabs" role="tablist">
                  <button role="tab" aria-selected={inputsMode==='json'} className={inputsMode==='json'?'active':''} onClick={()=>setInputsMode('json')}>JSON</button>
                  <button role="tab" aria-selected={inputsMode==='form'} className={inputsMode==='form'?'active':''} onClick={()=>setInputsMode('form')}>Form</button>
                </div>
              </div>
              {inputsMode === 'json' ? (
                <textarea className="inputs" value={inputsText} onChange={e => setInputsText(e.target.value)} spellCheck={false} />
              ) : (
                <div className="inputs-form">
                  {formNotice && <div className="notice">{formNotice}</div>}
                  <div className="form-rows">
                    {formRows.map((r, idx) => (
                      <div className="form-row" key={idx}>
                        <input className="k" placeholder="name" value={r.key} onChange={e=>{
                          const rows=[...formRows]; rows[idx] = { ...rows[idx], key: e.target.value }; setFormRows(rows); setInputsText(rowsToJson(rows))
                        }} />
                        <select className="t" value={r.type} onChange={e=>{
                          const rows=[...formRows]; rows[idx] = { ...rows[idx], type: e.target.value };
                          // default value for type
                          if (e.target.value==='boolean') rows[idx].value = 'false'
                          if (e.target.value==='number') rows[idx].value = '0'
                          if (e.target.value==='null') rows[idx].value = ''
                          if (e.target.value==='array') rows[idx].value = '[]'
                          if (e.target.value==='object') rows[idx].value = '{}'
                          setFormRows(rows); setInputsText(rowsToJson(rows))
                        }}>
                          <option value="string">string</option>
                          <option value="number">number</option>
                          <option value="boolean">boolean</option>
                          <option value="null">null</option>
                          <option value="array">array</option>
                          <option value="object">object</option>
                        </select>
                        <input className="v" placeholder="value" value={r.value} onChange={e=>{
                          const rows=[...formRows]; rows[idx] = { ...rows[idx], value: e.target.value }; setFormRows(rows); setInputsText(rowsToJson(rows))
                        }} />
                        <button type="button" className="del" title="Remove" onClick={()=>{
                          const rows=[...formRows]; rows.splice(idx,1); setFormRows(rows); setInputsText(rowsToJson(rows))
                        }}>✕</button>
                      </div>
                    ))}
                  </div>
                  <div className="form-actions">
                    <button type="button" onClick={()=>{
                      const rows=[...formRows, { key:'', type:'string', value:'' }]; setFormRows(rows); setInputsText(rowsToJson(rows))
                    }}>+ Add row</button>
                    <button type="button" onClick={()=>{ setFormRows(jsonToRows(inputsText)); setFormNotice('Form reloaded from JSON') }}>Reload from JSON</button>
                  </div>
                </div>
              )}
              <div className="controls">
                <button onClick={runCode} title="Ctrl+Enter">▶ Run</button>
                <button onClick={saveScript} title="Ctrl+S">💾 Save</button>
                <button onClick={clearOutput}>🧹 Clear</button>
              </div>
            </div>
            <div>
              <h2>Output</h2>
              <pre className="output" aria-live="polite">{output}</pre>
              <ErrorPanel err={error} codeText={code} />
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
          {renderTutorial(tutoMd, {
            onTryCode: (src) => { setCode(src); setTab('editor') },
            onTryInputs: (json) => { setInputsText(json); setInputsMode('json'); setTab('editor') },
          })}
        </div>
      )}
    </div>
  )
}

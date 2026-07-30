import { useEffect, useState } from 'react'

import { baselineProgress, patternProgress, phonemeProgress, sessionReport } from '../api'
import BaselineChart from '../components/BaselineChart'
import SessionReport from '../components/SessionReport'

/**
 * Progreso: solo métricas honestas.
 *
 * Sin rachas, sin medallas, sin niveles. Lo que se muestra es lo que se midió:
 * precisión por fonema sobre tus propias lecturas, y qué patrones de la
 * taxonomía se repiten. Un número inventado para motivar es un número que te
 * enseña a desconfiar del resto.
 */
export default function Progress() {
  const [phonemes, setPhonemes] = useState(null)
  const [patterns, setPatterns] = useState(null)
  const [baseline, setBaseline] = useState(null)
  const [session, setSession] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    phonemeProgress(30).then((d) => setPhonemes(d.phonemes)).catch((e) => setError(e.message))
    patternProgress(30).then((d) => setPatterns(d.patterns)).catch(() => {})
    baselineProgress(90).then(setBaseline).catch(() => {})
    sessionReport().then(setSession).catch(() => {})
  }, [])

  const loading = !phonemes && !error

  return (
    <div className="page dashboard">
      <header className="page-head">
        <h1>Progreso</h1>
        <p className="lede">Solo lecturas evaluables. Cada panel dice su ventana.</p>
      </header>

      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Cargando…</p>}

      {phonemes && phonemes.length === 0 && (
        <p className="muted">
          Todavía no hay suficientes lecturas. Cada sonido necesita al menos tres
          muestras antes de aparecer aquí.
        </p>
      )}

      <SessionReport report={session} />

      <div className="dash-main">
      {baseline && baseline.phonemes.length > 0 && <BaselineChart data={baseline} />}

      {phonemes && phonemes.length > 0 && (
        <section className="panel">
          <h2>Precisión reciente · 30 días</h2>
          <p className="hint">
            La medida en crudo, sin contrastar. Sirve para ver movimiento a corto
            plazo; para saber qué practicar, el panel de arriba.
          </p>
          <ul className="phoneme-bars">
            {phonemes.map((p) => (
              <li key={p.ipa}>
                <code className="ipa">/{p.ipa}/</code>
                <span className="bar">
                  <span
                    className="fill"
                    style={{
                      width: `${p.mean_score}%`,
                      background:
                        p.mean_score >= 85
                          ? 'var(--ok)'
                          : p.mean_score >= 70
                            ? 'var(--near)'
                            : 'var(--error)',
                    }}
                  />
                </span>
                <span className="score">{p.mean_score}</span>
                <span className="samples">{p.samples} muestras</span>
              </li>
            ))}
          </ul>
        </section>
      )}
      </div>

      {/* A la columna de apoyo: es una lista corta de consulta, no algo que se
          estudie renglón a renglón como el resto. */}
      {patterns && patterns.length > 0 && (
        <section className="panel aside">
          <h2>Patrones recurrentes</h2>
          <ul className="pattern-list">
            {patterns.map((p) => (
              <li key={p.code}>
                <span className="count">{p.hits}</span>
                <span className="label">{p.label}</span>
                <code className="code">{p.code}</code>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

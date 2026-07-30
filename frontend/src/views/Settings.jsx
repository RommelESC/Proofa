/**
 * Ajustes: aquí vive la línea técnica que antes estaba apretada en el encabezado.
 *
 * En el riel es un punto de color; el detalle completo está aquí, que es donde
 * lo buscas cuando algo falla.
 */
function Row({ label, value, state }) {
  return (
    <div className="setting-row">
      <span className="k">{label}</span>
      <span className={`v ${state ?? ''}`}>{value}</span>
    </div>
  )
}

/** Índice lateral. Con dos secciones parece de más, pero esta pantalla solo
 *  crece — y anclarla ahora evita que mañana sea un muro de filas. */
const SECCIONES = [
  { id: 'estado', label: 'Estado' },
  { id: 'motores', label: 'Motores disponibles' },
]

export default function Settings({ health }) {
  if (!health) {
    return (
      <div className="page">
        <header className="page-head">
          <h1>Ajustes</h1>
        </header>
        <p className="muted">Sin respuesta del servidor.</p>
      </div>
    )
  }

  const engine = health.engines?.[health.active_engine]

  return (
    <div className="page settings-page">
      <header className="page-head">
        <h1>Ajustes</h1>
        <p className="lede">
          Todo se configura en <code>.env</code>. Esta pantalla refleja lo que el
          servidor está usando ahora mismo.
        </p>
      </header>

      <nav className="settings-nav" aria-label="Secciones de ajustes">
        <ul>
          {SECCIONES.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`}>{s.label}</a>
            </li>
          ))}
        </ul>
      </nav>

      <div className="settings-body">
      <section className="panel" id="estado">
        <h2>Estado</h2>
        <Row
          label="Base de datos"
          value={health.database.ok ? 'conectada' : health.database.detail}
          state={health.database.ok ? 'ok' : 'error'}
        />
        <Row
          label="Motor de pronunciación"
          value={`${health.active_engine} — ${engine?.detail ?? ''}`}
          state={engine?.ready ? 'ok' : 'error'}
        />
        <Row
          label="Modelo de lenguaje"
          value={`${health.llm?.name ?? '—'} — ${health.llm?.detail ?? ''}`}
          state={health.llm?.ready ? 'ok' : 'near'}
        />
        <Row label="Grafema → fonema" value={health.g2p} state="ok" />
        <Row label="Patrones en catálogo" value={health.error_patterns} />
      </section>

      <section className="panel" id="motores">
        <h2>Motores disponibles</h2>
        {Object.entries(health.engines ?? {}).map(([name, e]) => (
          <Row
            key={name}
            label={name}
            value={e.detail || (e.ready ? 'listo' : 'no disponible')}
            state={e.ready ? 'ok' : 'muted'}
          />
        ))}
      </section>
      </div>
    </div>
  )
}

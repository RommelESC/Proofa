import { Coach, Listen, Resume } from './icons'

/**
 * Lo que ves al entrar.
 *
 * Antes la Biblioteca era una lista de libros: para volver a donde ibas había
 * que abrir el libro, esperar los capítulos y buscar el botón de reanudar.
 * Tres pasos para la única acción que haces siempre.
 *
 * Las cifras de la semana son deliberadamente tres. Este no es el sitio donde
 * se analiza nada — para eso está Progreso — es donde decides si hoy practicas.
 */

const fmtHace = (iso) => {
  const dias = Math.floor((Date.now() - new Date(iso)) / 86400000)
  if (dias <= 0) return 'hoy'
  if (dias === 1) return 'ayer'
  return `hace ${dias} días`
}

function Resumen({ resume, onOpen }) {
  if (!resume) return null
  const donde = resume.chapter_title || `Capítulo ${resume.chapter_idx + 1}`

  return (
    <div className="where-block">
      <h2>Continuar donde te quedaste</h2>
      <p className="where">
        <strong>{resume.book_title}</strong> · {donde}
        {resume.sentences > 0 && (
          <> · oración {resume.sentence_idx + 1} de {resume.sentences}</>
        )}
      </p>
      <p className="hint">Última vez: {fmtHace(resume.updated_at)}</p>

      <div className="start-actions">
        <button className="solid" onClick={() => onOpen('read')}>
          <Resume size={15} /> Reanudar leyendo
        </button>
        <button onClick={() => onOpen('listen')}>
          <Listen size={15} /> Escuchar
        </button>
        <button onClick={() => onOpen('coach')}>
          <Coach size={15} /> Coach
        </button>
      </div>
    </div>
  )
}

function Semana({ week }) {
  if (!week) return null
  const pico = Math.max(...week.days.map((d) => d.minutes), 1)

  return (
    <div className="week-block">
      <h2>Esta semana</h2>

      <div className="week-stats">
        <div className="stat">
          <span className="value mono">{week.minutes}</span>
          <span className="label">{week.minutes === 1 ? 'minuto leyendo' : 'minutos leyendo'}</span>
        </div>
        <div className="stat">
          <span className="value mono">{week.wpm ?? '—'}</span>
          <span className="label">velocidad media</span>
        </div>
        <div className="stat">
          <span className="value mono">{week.accuracy != null ? `${week.accuracy}%` : '—'}</span>
          <span className="label">precisión al leer</span>
        </div>
      </div>

      <div className="week-strip">
        {week.days.map((d) => (
          <div key={d.date} className={`day ${d.is_today ? 'today' : ''} ${d.minutes ? 'active' : ''}`}>
            {/* Cada día tiene su carril, siempre visible. Sin él, una semana
                con un solo día de práctica dibujaba un cuadro suelto en medio
                de la nada: parecía un error de maquetación en vez de seis días
                sin practicar, que es justo lo que hay que ver. */}
            <span className="track" title={`${d.minutes} min · ${d.attempts} grabaciones`}>
              <span
                className="fill"
                style={{ height: `${d.minutes ? Math.max((d.minutes / pico) * 100, 6) : 0}%` }}
              />
            </span>
            <span className="initial">{d.initial}</span>
          </div>
        ))}
      </div>

      {week.attempts === 0 && (
        <p className="hint">
          Sin lecturas evaluables esta semana. Casi todo lo que mide la app mejora
          solo con grabar más.
        </p>
      )}
    </div>
  )
}

function Sonidos({ baseline, onPractice }) {
  // Los confirmados primero y el resto se rellena con los más bajos que tengan
  // muestra. Enseñar solo el único confirmado dejaría el panel casi vacío y
  // daría a entender que no hay nada más que mirar; enseñarlos todos por igual
  // borraría la distinción entre lo medido y lo que aún no se sabe. Van los dos,
  // marcados distinto.
  const weak = baseline?.weak ?? []
  const codigos = new Set(weak.map((p) => p.ipa))
  const relleno = (baseline?.phonemes ?? []).filter(
    (p) => p.stdev != null && !codigos.has(p.ipa),
  )
  const lista = [...weak, ...relleno].slice(0, 4)
  if (!lista.length) return null

  const confirmados = weak.length

  return (
    <section className="panel start-sounds aside">
      <h2>
        Sonidos que te cuestan
        <button className="ghost" onClick={onPractice}>
          Practicar
        </button>
      </h2>

      <ul className="sound-list">
        {lista.map((p) => (
          <li key={p.ipa}>
            <code className="ipa">/{p.ipa}/</code>
            <span className="track">
              <span
                className="fill"
                style={{
                  width: `${p.mean}%`,
                  background: p.verdict === 'weak' ? 'var(--error)' : 'var(--near)',
                }}
              />
            </span>
            <span className="pct mono">{Math.round(p.mean)}%</span>
          </li>
        ))}
      </ul>

      <p className="hint">
        {confirmados
          ? `En rojo, ${confirmados === 1 ? 'el confirmado' : 'los confirmados'} contra tu propia media. En ámbar, los más bajos que todavía caben en el margen de error.`
          : 'Ninguno confirmado todavía: son los más bajos, pero la diferencia aún cabe en el margen de error.'}
      </p>
    </section>
  )
}

export default function StartPanel({ resume, week, baseline, onOpen, onPractice }) {
  return (
    <>
      {/* Una sola banda a lo ancho: dónde te quedaste y cómo va la semana son
          la misma pregunta — «¿sigo por aquí?» — y apiladas ocupaban dos
          pantallazos de alto en un monitor donde sobraba anchura. */}
      {(resume || week) && (
        <section className="panel start-resume band">
          <Resumen resume={resume} onOpen={onOpen} />
          <Semana week={week} />
        </section>
      )}
      <Sonidos baseline={baseline} onPractice={onPractice} />
    </>
  )
}

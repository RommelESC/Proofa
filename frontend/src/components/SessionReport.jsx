/**
 * Informe de la última sesión de práctica.
 *
 * Las sesiones se derivan del ritmo de grabación, no hay botón de empezar ni
 * terminar. Así que esto aparece solo cuando de verdad practicaste.
 *
 * Lo que se muestra arriba y en grande son las grabaciones descartadas, no la
 * media. Si seis de diez no se pudieron evaluar, eso es lo que hay que
 * arreglar hoy — y una media calculada sobre las cuatro que quedan es un dato
 * frágil que no conviene leer como si fueran diez.
 */

const fmtDate = (iso) =>
  new Date(iso).toLocaleString('es', {
    day: 'numeric',
    month: 'long',
    hour: '2-digit',
    minute: '2-digit',
  })

export default function SessionReport({ report }) {
  if (!report?.enough) return null

  const {
    started_at: started,
    minutes,
    attempts,
    discarded,
    mean_overall: mean,
    best,
    trend,
    weak_points: weak,
    patterns,
    open,
  } = report

  const evaluated = attempts - discarded

  return (
    /* `start-resume` la coloca en la banda superior del tablero: es el
       resumen de cabecera, igual que en Biblioteca. */
    <section className="panel session start-resume">
      <h2>
        {open ? 'Sesión en curso' : 'Última sesión'}
        <span className="when">{fmtDate(started)} · {minutes} min</span>
      </h2>

      {discarded > 0 && (
        <p className="discarded">
          <strong>
            {discarded} de {attempts} grabaciones no se pudieron evaluar.
          </strong>{' '}
          Salen cuando el audio se corta antes de acabar la frase o no se oye
          nada. No cuentan como mala pronunciación y no entran en la media — pero
          si pasa seguido, lo que hay que revisar es la grabación.
        </p>
      )}

      <div className="session-stats">
        <div className="stat">
          <span className="value mono">{evaluated}</span>
          <span className="label">evaluadas</span>
        </div>
        <div className="stat">
          <span className="value mono">{mean}</span>
          <span className="label">media</span>
        </div>
        <div className="stat">
          <span className="value mono">{best}</span>
          <span className="label">mejor</span>
        </div>
      </div>

      {trend ? (
        <p className="hint trend">
          Primera mitad {trend.first_half} · segunda {trend.second_half} (
          {trend.delta >= 0 ? '+' : ''}
          {trend.delta}). En veinte minutos no se aprende un sonido: esto es
          calentamiento o cansancio. Si sueles empezar flojo, las primeras
          grabaciones no valen como diagnóstico.
        </p>
      ) : (
        <p className="hint">
          Pocas grabaciones evaluables para hablar de tendencia dentro de la
          sesión.
        </p>
      )}

      {weak.length > 0 && (
        <div className="session-weak">
          <h4>Tus puntos débiles en esta sesión</h4>
          {weak.map((w) => (
            <div key={w.ipa} className={`personal-row ${w.delta >= 0 ? 'better' : 'worse'}`}>
              <code className="ipa">/{w.ipa}/</code>
              <span className="now mono">{w.session}</span>
              <span className="delta mono">
                {w.delta >= 0 ? '+' : ''}
                {w.delta}
              </span>
              <span className="vs">
                {w.delta >= 0 ? 'sobre' : 'bajo'} tu media de {w.baseline}, sobre{' '}
                {w.samples} {w.samples === 1 ? 'muestra' : 'muestras'}
              </span>
            </div>
          ))}
        </div>
      )}

      {patterns.length > 0 && (
        <ul className="pattern-list session-patterns">
          {patterns.map((p) => (
            <li key={p.code}>
              <span className="count">{p.hits}</span>
              <span className="label">{p.label}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

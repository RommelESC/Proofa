/**
 * Puntos débiles medidos contra ti mismo.
 *
 * Cada fila dibuja el intervalo de confianza del sonido y una línea con tu
 * propia media. Que se vea el intervalo es el punto: un sonido en 72 con la
 * barra cruzando la línea no es una debilidad, es una muestra pequeña, y
 * decirlo con palabras no convence tanto como enseñarlo.
 *
 * El margen lo calcula el backend con el mismo error típico que usa para
 * decidir el veredicto, así que la barra nunca puede contradecir al texto.
 */

const MIN = 40
const MAX = 100

const pct = (v) => Math.min(100, Math.max(0, ((v - MIN) / (MAX - MIN)) * 100))

function Row({ p }) {
  const low = p.margin != null ? p.mean - p.margin : p.mean
  const high = p.margin != null ? p.mean + p.margin : p.mean
  const left = pct(low)
  const width = Math.max(pct(high) - left, 1.2)

  return (
    <li className={`baseline-row ${p.verdict}`}>
      <code className="ipa">/{p.ipa}/</code>

      <span className="track" title={`${p.samples} muestras`}>
        <span className="ref" style={{ left: `${pct(p.reference)}%` }} />
        {p.margin != null && (
          <span className="range" style={{ left: `${left}%`, width: `${width}%` }} />
        )}
        <span className="dot" style={{ left: `${pct(p.mean)}%` }} />
      </span>

      <span className="mean mono">{p.mean}</span>

      <span className="verdict">
        {p.verdict === 'weak' && 'debilidad'}
        {p.verdict === 'ok' && 'sobre tu media'}
        {p.verdict === 'unclear' &&
          (p.attempts_needed
            ? `${p.attempts_needed} lecturas más`
            : p.samples < 5
              ? 'sin muestra'
              : 'diferencia mínima')}
      </span>
    </li>
  )
}

export default function BaselineChart({ data }) {
  const { weak = [], phonemes = [], reference, attempts, days, next_answer: next } = data

  return (
    <section className="panel">
      <h2>Tus puntos débiles · {days} días</h2>
      <p className="hint">
        Comparado contigo mismo, no con un umbral fijo. La línea vertical es tu
        media ({reference}) y la barra es el margen de error de cada sonido. Un
        sonido solo cuenta como debilidad cuando su barra entera queda por
        debajo de la línea — si la cruza, todavía puede ser casualidad.
      </p>

      {weak.length > 0 ? (
        <ul className="weak-list">
          {weak.map((w) => (
            <li key={w.ipa}>
              <code className="ipa">/{w.ipa}/</code>
              <span>
                <strong>{Math.abs(w.gap)} puntos</strong> por debajo de tu media, sobre{' '}
                {w.samples} muestras.
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">
          Ninguna debilidad confirmada todavía. Con {attempts} lecturas grabadas, las
          diferencias que se ven abajo aún caben dentro del margen de error.
        </p>
      )}

      <ul className="baseline-rows">
        {phonemes.map((p) => (
          <Row key={p.ipa} p={p} />
        ))}
      </ul>

      {next && (
        <p className="next-answer">
          El siguiente en resolverse es <code className="ipa">/{next.ipa}/</code>: unas{' '}
          <strong>{next.attempts_needed} lecturas</strong> más y se sabrá.
        </p>
      )}
    </section>
  )
}

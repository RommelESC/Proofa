/**
 * Mapa de tus sonidos.
 *
 * Antes esta pantalla solo sabía enseñar el drill del peor: si querías
 * practicar otro, no había manera de pedirlo. La lista lo vuelve navegable —
 * y de paso enseña dónde estás en cada sonido, que es lo que decide cuál
 * merece el rato de hoy.
 *
 * El orden es de peor a mejor, y la marca de «confirmado» se conserva: no es
 * lo mismo un sonido que está bajo de verdad que uno que aún cabe en el
 * margen de error.
 */
export default function SoundMap({ phonemes, current, onPick }) {
  if (!phonemes?.length) return null

  return (
    <nav className="panel sound-map" aria-label="Tus sonidos">
      <h2>Tus sonidos</h2>
      <p className="hint">De peor a mejor, medido contra tu propia media.</p>

      <ul>
        {phonemes.map((p) => {
          const activo = p.ipa === current
          return (
            <li key={p.ipa}>
              <button
                className={`${activo ? 'current' : ''} ${p.verdict}`}
                onClick={() => onPick(p.ipa)}
                aria-current={activo ? 'true' : undefined}
                title={`${p.samples} muestras${p.stdev != null ? ` · desviación ${p.stdev}` : ''}`}
              >
                <code className="ipa">/{p.ipa}/</code>
                <span className="track">
                  <span className="fill" style={{ width: `${p.mean}%` }} />
                </span>
                <span className="mean mono">{Math.round(p.mean)}</span>
                {p.verdict === 'weak' && <span className="flag" title="Debilidad confirmada">●</span>}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

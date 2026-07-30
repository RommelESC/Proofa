const RATES = [0.6, 0.75, 1, 1.25]

/**
 * Controles de la narración. La velocidad va al frente, no escondida en un
 * menú: en lectura pasiva es el ajuste que de verdad usas, porque marca la
 * diferencia entre seguir el texto y perderte.
 */
export default function NarrationBar({ narration, total, onExit }) {
  const { index, playing, rate, error, setRate, toggle, skip } = narration
  const position = index != null ? index + 1 : 0

  return (
    <aside className="narration-bar" role="region" aria-label="Narración">
      <div className="bar-inner">
        <div className="narration-main">
          <div className="transport">
            <button onClick={() => skip(-1)} disabled={!index} title="Oración anterior">
              ‹
            </button>
            <button className="primary" onClick={toggle}>
              {playing ? 'Pausa' : index != null ? 'Continuar' : 'Escuchar capítulo'}
            </button>
            <button onClick={() => skip(1)} title="Siguiente oración">
              ›
            </button>
          </div>

          <span className="counter mono">
            {position}/{total}
          </span>

          <div className="rates" role="group" aria-label="Velocidad">
            {RATES.map((r) => (
              <button
                key={r}
                className={rate === r ? 'active' : ''}
                onClick={() => setRate(r)}
              >
                {r}×
              </button>
            ))}
          </div>

          <button className="dismiss" onClick={onExit} aria-label="Salir de Escuchar">
            &times;
          </button>
        </div>

        {error && <p className="error inline">{error}</p>}
      </div>
    </aside>
  )
}

/**
 * Tu ritmo contra el del modelo.
 *
 * Las dos líneas están normalizadas a su propia duración total: comparan la
 * FORMA, no la velocidad. Si vas al 90% de su tempo todas tus palabras salen
 * más cortas, y eso no es un error de ritmo — por eso el tempo va aparte.
 *
 * Lo que se busca es el aplanamiento. El inglés alarga las tónicas y comprime
 * las átonas; el español reparte parejo. Cuando tus bloques salen todos del
 * mismo ancho y los del modelo no, eso es el acento aunque cada fonema esté
 * bien puntuado.
 */

function Timeline({ words, side, label }) {
  return (
    <div className="rhythm-row">
      <span className="rhythm-label">{label}</span>
      <span className="rhythm-track">
        {words.map((w, i) => (
          <span
            key={i}
            className={`rhythm-block ${side === 'yours' ? w.verdict.replace(' ', '-') : ''}`}
            style={{ width: `${w[side === 'yours' ? 'yours_share' : 'model_share'] * 100}%` }}
            title={`${w.surface}: ${w[side === 'yours' ? 'yours_ms' : 'model_ms']} ms`}
          >
            <span className="rhythm-word">{w.surface}</span>
          </span>
        ))}
      </span>
    </div>
  )
}

export default function RhythmCompare({ rhythm }) {
  if (!rhythm) return null

  if (!rhythm.enough) {
    return (
      <p className="muted">
        Solo se emparejaron {rhythm.matched} de {rhythm.expected} palabras: hacen falta
        más para que la comparación de ritmo signifique algo. Vuelve a intentarlo
        leyendo la frase entera.
      </p>
    )
  }

  const { tempo, contrast_ratio: contrast, words, notable } = rhythm
  const aplana = contrast != null && contrast < 0.9

  return (
    <div className="rhythm">
      <div className="rhythm-stats">
        <div className="stat">
          <span className="value mono">{tempo}×</span>
          <span className="label">tu tempo</span>
        </div>
        <div className={`stat ${aplana ? 'warn' : ''}`}>
          <span className="value mono">{contrast}×</span>
          <span className="label">contraste</span>
        </div>
      </div>

      <p className="hint">
        {aplana ? (
          <>
            Repartes el tiempo <strong>más parejo que el modelo</strong>. El inglés
            alarga las sílabas tónicas y comprime las átonas; el español las hace
            durar casi lo mismo. Es lo que suena a acento aunque los sonidos estén
            bien.
          </>
        ) : (
          <>Tu reparto de duraciones sigue al del modelo. El ritmo va bien.</>
        )}
      </p>

      <Timeline words={words} side="model" label="modelo" />
      <Timeline words={words} side="yours" label="tú" />

      {notable.length > 0 && (
        <ul className="rhythm-notable">
          {notable.map((w) => (
            <li key={w.surface}>
              <strong>{w.surface}</strong>{' '}
              {w.verdict === 'estirada'
                ? `la alargas de más (${w.model_ms} ms en el modelo, ${w.yours_ms} en la tuya)`
                : `la comes (${w.model_ms} ms en el modelo, ${w.yours_ms} en la tuya)`}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

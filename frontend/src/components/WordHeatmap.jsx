/**
 * Mapa de calor por palabra. Al pasar el cursor muestra el detalle fonema a
 * fonema: que se esperaba y que produjiste.
 *
 * Los cortes son deliberadamente indulgentes. Un falso positivo (marcar mal
 * algo bien dicho) destruye la confianza mucho mas rapido de lo que un falso
 * negativo retrasa el avance.
 */

function band(score) {
  if (score >= 85) return 'ok'
  if (score >= 70) return 'fair'
  if (score >= 50) return 'weak'
  return 'bad'
}

export default function WordHeatmap({ words }) {
  if (!words?.length) return null

  return (
    <div className="heatmap">
      {words.map((w) => (
        <span key={w.index} className={`word ${band(w.score)}`}>
          {w.surface}
          <span className="tooltip">
            <strong>
              {w.surface} · {Math.round(w.score)}
            </strong>
            {w.stress_ok === false && <em className="stress">acento desplazado</em>}
            <span className="phonemes">
              {w.phonemes.map((p) => (
                <span key={p.index} className={`ph ${band(p.score)}`}>
                  /{p.expected_ipa}/
                  {p.produced_ipa && p.produced_ipa !== p.expected_ipa && (
                    <b> → /{p.produced_ipa}/</b>
                  )}
                  {!p.produced_ipa && <b> → omitido</b>}
                </span>
              ))}
            </span>
          </span>
        </span>
      ))}
    </div>
  )
}

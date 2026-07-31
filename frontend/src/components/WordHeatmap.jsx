/**
 * Mapa de calor por palabra. Al pasar el cursor muestra el detalle fonema a
 * fonema: que se esperaba y que produjiste.
 *
 * Los cortes son deliberadamente indulgentes. Un falso positivo (marcar mal
 * algo bien dicho) destruye la confianza mucho mas rapido de lo que un falso
 * negativo retrasa el avance.
 */

import { Fragment } from 'react'

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
        // El espacio entre palabras es un nodo de texto de verdad, no relleno
        // CSS. El navegador solo puede partir una línea donde hay un espacio
        // en blanco: sin él, los `span` van pegados, no hay dónde cortar y la
        // oración evaluada se dibuja en una sola línea que se sale del marco
        // y pasa por detrás del panel. Medido: 1373px dentro de una caja de 700.
        <Fragment key={w.index}>
        <span className={`word ${band(w.score)}`}>
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
        </span>{' '}
        </Fragment>
      ))}
    </div>
  )
}

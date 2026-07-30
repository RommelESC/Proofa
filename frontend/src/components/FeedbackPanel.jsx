import { useAudioCue } from '../hooks/useAudioCue'
import SpeakButton from './SpeakButton'

/**
 * Feedback pedagogico. Muestra como maximo 2 focos por intento: corregir
 * todos los errores a la vez es tecnicamente correcto y pedagogicamente
 * pesimo. El backend ya limita esto en coaching_payload().
 */

/** «think / sink» -> ['think', 'sink'].  «speak (no 'espeak')» -> ['speak'] */
function splitPair(raw) {
  return raw
    .split('/')
    .map((part) => part.replace(/\([^)]*\)/g, '').trim())
    .filter(Boolean)
}

export default function FeedbackPanel({ coaching, personal = [] }) {
  const cue = useAudioCue()
  if (!coaching) return null

  const { overall, focus, worst_words: worstWords, synthetic, usable, warning } = coaching

  // Una lectura truncada produce un score bajo que se lee como «pronunciaste
  // mal». Mostrarlo desinforma: el problema fue la grabación, no la boca.
  if (usable === false) {
    return (
      <section className="feedback">
        <p className="unusable">{warning}</p>
      </section>
    )
  }

  return (
    <section className="feedback">
      {synthetic && (
        <p className="synthetic-warning">
          Motor <code>mock</code>: estos scores son <strong>generados, no medidos</strong>.
          Sirven para validar el circuito completo. Cambia <code>PRONUNCIATION_ENGINE</code>{' '}
          en <code>.env</code> para evaluar de verdad.
        </p>
      )}

      <div className="overall">
        <span className="value">{Math.round(overall)}</span>
        <span className="label">global</span>
      </div>

      {/* Lo tuyo, medido contra tu historial. Un sonido en 68 no dispara
          ninguna alarma general, pero si tu media en ese sonido es 70,
          acabas de repetir el error que arrastras. */}
      {personal.length > 0 && (
        <div className="personal">
          <h4>Tus puntos débiles en esta lectura</h4>
          {personal.map((p) => (
            <div key={p.ipa} className={`personal-row ${p.delta >= 0 ? 'better' : 'worse'}`}>
              <code className="ipa">/{p.ipa}/</code>
              <span className="now mono">{p.now}</span>
              <span className="delta mono">
                {p.delta >= 0 ? '+' : ''}
                {p.delta}
              </span>
              <span className="vs">
                {p.delta >= 0 ? 'sobre' : 'bajo'} tu media de {p.baseline}
              </span>
              <SpeakButton cue={cue} id={`p${p.ipa}`} text={p.ipa} ipa={p.ipa} slow />
            </div>
          ))}
        </div>
      )}

      {worstWords.length > 0 && (
        <div className="worst-list">
          <h4>Escucha cómo debería sonar</h4>
          {worstWords.map((w) => (
            <div key={w.index} className="worst-row">
              <span className="word">{w.surface}</span>
              {w.ipa && <span className="ipa">/{w.ipa}/</span>}
              <span className="score">{Math.round(w.score)}</span>
              <SpeakButton cue={cue} id={`w${w.index}`} text={w.surface} ipa={w.ipa} />
              <SpeakButton cue={cue} id={`w${w.index}`} text={w.surface} ipa={w.ipa} slow />
            </div>
          ))}
        </div>
      )}

      {focus.length === 0 && worstWords.length === 0 && (
        <p className="clean">Sin patrones recurrentes en este intento.</p>
      )}

      {focus.map((f) => (
        <article key={f.code} className="focus">
          <header>
            <h3>{f.label}</h3>
            <span className="count">
              {f.occurrences} {f.occurrences === 1 ? 'vez' : 'veces'}
            </span>
          </header>
          <p>{f.explanation}</p>

          {f.examples.length > 0 && (
            <ul className="examples">
              {f.examples.map((ex, i) => (
                <li key={i}>{ex}</li>
              ))}
            </ul>
          )}

          {f.minimal_pairs.length > 0 && (
            <div className="pairs">
              <span className="pairs-label">
                Compara los dos sonidos — oírlos seguidos es lo que entrena el oído:
              </span>
              {f.minimal_pairs.map((pair) => (
                <span key={pair} className="pair">
                  {splitPair(pair).map((word, i) => (
                    <SpeakButton
                      key={word}
                      cue={cue}
                      id={`${f.code}:${pair}:${i}`}
                      text={word}
                      label={word}
                    />
                  ))}
                </span>
              ))}
            </div>
          )}
        </article>
      ))}

      {cue.error && <p className="error inline">{cue.error}</p>}
    </section>
  )
}

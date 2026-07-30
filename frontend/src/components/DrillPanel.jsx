import { useAudioCue } from '../hooks/useAudioCue'
import SpeakButton from './SpeakButton'

/**
 * Práctica dirigida a tu punto débil.
 *
 * Lo que cierra el círculo: el panel de Progreso dice qué sonido llevas peor,
 * y esto da con qué practicarlo. Las frases salen del libro que estás leyendo,
 * así que no es trabajo aparte — son renglones que te iban a tocar igual.
 *
 * `reason` importa lo suficiente para enseñarse. «Confirmado» significa que la
 * debilidad sobrevivió al contraste estadístico; «provisional» que es el peor
 * que tienes pero todavía sin evidencia suficiente. Presentar las dos cosas
 * igual sería justo el error que el baseline existe para no cometer.
 */
export default function DrillPanel({ drill, onPick, active }) {
  const cue = useAudioCue()
  if (!drill?.ipa) return null

  const { ipa, reason, your_mean: mean, pattern, words, sentences } = drill

  return (
    <section className="panel drill">
      <h2>
        Practica tu punto débil
        {/* «solicitado» es cuando lo elegiste tú en el mapa: ahí la etiqueta
            no aporta nada — ya sabes por qué estás viendo ese sonido — y
            llamarlo «provisional» sería decir algo falso sobre la medición. */}
        {reason !== 'solicitado' && (
          <span className={`tag ${reason}`}>
            {reason === 'confirmado' ? 'confirmado' : 'provisional'}
          </span>
        )}
      </h2>

      <div className="drill-head">
        <code className="ipa big">/{ipa}/</code>
        <div>
          {pattern ? (
            <>
              <strong>{pattern.label}</strong>
              <p>{pattern.explanation}</p>
            </>
          ) : (
            <p className="muted">
              Este sonido no tiene ficha en la taxonomía de errores del español, así
              que no hay consejo articulatorio que darte sin inventarlo. El material
              de abajo sirve igual.
            </p>
          )}
          {mean != null && <p className="hint">Tu media en este sonido: {mean}</p>}
        </div>
      </div>

      {pattern?.minimal_pairs.length > 0 && (
        <div className="pairs">
          <span className="pairs-label">
            Pares mínimos — oírlos seguidos es lo que entrena el oído:
          </span>
          {pattern.minimal_pairs.map((pair) => (
            <span key={pair} className="pair">
              {pair
                .split('/')
                .map((w) => w.replace(/\([^)]*\)/g, '').trim())
                .filter(Boolean)
                .map((word, i) => (
                  <SpeakButton
                    key={word}
                    cue={cue}
                    id={`mp:${pair}:${i}`}
                    text={word}
                    label={word}
                  />
                ))}
            </span>
          ))}
        </div>
      )}

      {words.length > 0 && (
        <div className="drill-words">
          <h4>Palabras de tu libro con este sonido</h4>
          {words.map((w) => (
            <div key={w.surface} className="drill-word">
              <span className="surface">{w.surface}</span>
              <code className="ipa">/{w.ipa}/</code>
              {w.your_mean != null && (
                <span className="yours" title="Tu media histórica en este sonido, en esta palabra">
                  {w.your_mean}
                </span>
              )}
              <SpeakButton cue={cue} id={`dw:${w.surface}`} text={w.surface} />
              <SpeakButton cue={cue} id={`dw:${w.surface}`} text={w.surface} slow />
            </div>
          ))}
        </div>
      )}

      {sentences.length > 0 && (
        <div className="drill-sentences">
          <h4>Frases para leer en voz alta</h4>
          {sentences.map((s) => (
            <button
              key={s.sentence_id}
              className={`drill-sentence ${active === s.text ? 'active' : ''}`}
              onClick={() => onPick(s.text)}
              title="Cargar esta frase para grabarla"
            >
              <span className="hits mono">{s.hits}</span>
              <span className="text">{s.text}</span>
            </button>
          ))}
        </div>
      )}

      {cue.error && <p className="error inline">{cue.error}</p>}
    </section>
  )
}

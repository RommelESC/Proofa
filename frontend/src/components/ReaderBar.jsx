import CoachPanel from './CoachPanel'
import FeedbackPanel from './FeedbackPanel'
import RhythmCompare from './RhythmCompare'

/**
 * Barra inferior fija: el único lugar donde ocurre la interacción.
 *
 * Antes los controles y las definiciones aparecían incrustados en la prosa,
 * cada uno donde cayera. El resultado no se leía como un libro. Concentrar
 * todo en un sitio estable hace dos cosas: el texto queda limpio, y siempre
 * sabes dónde mirar.
 */
export default function ReaderBar({
  sentence,
  gloss,
  assessment,
  speech,
  recording,
  busy,
  error,
  shadowing = false,
  coaching = false,
  rhythm,
  panel,
  side = false,
  onPractice,
  onPickAttempt,
  onPlay,
  onRecord,
  onClose,
  onCloseGloss,
}) {
  if (!sentence && !gloss) return null

  const speaking = sentence && speech.speakingId === sentence.id

  return (
    <aside
      className={`reader-bar ${side ? 'side' : ''}`}
      role="region"
      aria-label="Controles de lectura"
    >
      <div className="bar-inner">
        {gloss && (
          <div className="bar-gloss">
            <strong>{gloss.word}</strong>
            {/* La IPA llega primero: da algo útil de inmediato mientras el
                significado todavía viene en camino. */}
            {gloss.ipa && <span className="gloss-ipa">/{gloss.ipa}/</span>}
            {gloss.loading && !gloss.sense_es && <span className="muted"> · buscando el sentido…</span>}
            {gloss.error && <span className="err"> · {gloss.error}</span>}
            {gloss.sense_es && (
              <>
                {gloss.pos && <em> ({gloss.pos})</em>} — {gloss.sense_es}
              </>
            )}
            {gloss.lookups > 1 && (
              <span className="lookups" title="Veces que has consultado esta palabra">
                {' '}· {gloss.lookups}ª vez
              </span>
            )}
            {gloss.note_es && <span className="note"> · {gloss.note_es}</span>}
            <button className="dismiss" onClick={onCloseGloss} aria-label="Cerrar definición">
              &times;
            </button>
          </div>
        )}

        {sentence && (
          <div className="bar-main">
            <p className="bar-text" title={sentence.text_en}>
              {sentence.text_en}
            </p>

            <div className="bar-actions">
              <button onClick={onPlay} className={speaking ? 'on' : ''}>
                {speaking ? 'Detener' : 'Escuchar'}
              </button>
              <button
                onClick={onRecord}
                className={`primary ${recording ? 'on' : ''}`}
                disabled={busy}
              >
                {busy
                  ? 'Evaluando…'
                  : recording
                    ? 'Detener y evaluar'
                    : shadowing
                      ? 'Repetir encima'
                      : 'Leer en voz alta'}
              </button>
              <button className="dismiss" onClick={onClose} aria-label="Cerrar">
                &times;
              </button>
            </div>
          </div>
        )}

        {error && <p className="error inline">{error}</p>}

        {assessment && assessment.sentenceId === sentence?.id && (
          <div className="bar-result">
            {/* Shadowing corrige ritmo, no fonemas: para eso ya está Coach.
                Enseñar las dos cosas a la vez diluiría la única que este modo
                puede enseñar. */}
            {shadowing ? (
              rhythm ? (
                <RhythmCompare rhythm={rhythm} />
              ) : (
                <p className="muted">Comparando el ritmo…</p>
              )
            ) : coaching && panel?.found ? (
              <CoachPanel panel={panel} onPractice={onPractice} onPick={onPickAttempt} />
            ) : (
              <FeedbackPanel coaching={assessment.coaching} personal={assessment.personal} />
            )}
          </div>
        )}
      </div>
    </aside>
  )
}

import { useAudioCue } from '../hooks/useAudioCue'
import SpeakButton from './SpeakButton'

/**
 * El panel de corrección de Coach.
 *
 * Sustituye al resumen de patrones cuando hay sitio a la derecha. La
 * diferencia no es de forma: el resumen decía «terminación -ed, 3 veces»; esto
 * dice qué fonema falló, con qué lo cambiaste si se puede saber, qué palabra
 * te saltaste y por qué se salta en español, y dónde cortaste la frase.
 *
 * Lo que NO hace es rellenar huecos. Cuando el motor detecta que un fonema
 * falló pero no puede decir con qué lo sustituiste — que es el caso más
 * frecuente, medido — lo dice así en vez de inventar una sustitución
 * plausible. Un diagnóstico inventado manda a practicar lo que no toca.
 */

function Fonemas({ items, onPractice, cue }) {
  if (!items.length) return null
  return (
    <section className="cp-block">
      <h4>
        Fonemas <span className="count">{items.length}</span>
      </h4>
      {items.map((f, i) => (
        <div key={i} className="cp-phoneme">
          <div className="cp-word">
            <strong>{f.surface}</strong>
            <SpeakButton cue={cue} id={`cp${i}`} text={f.surface} ipa={f.word_ipa} slow />
          </div>
          <div className="cp-detail">
            <code className="ipa">/{f.word_ipa}/</code>
            {f.produced ? (
              <>
                {' → dijiste '}
                <code className="ipa said">/{f.produced}/</code>
              </>
            ) : (
              <span className="unknown">
                {' → tu /'}
                {f.phoneme}
                {'/ salió en '}
                {f.score}
                {', pero el motor no puede decir con qué lo cambiaste'}
              </span>
            )}
          </div>
          <button className="cp-practice" onClick={() => onPractice(f.phoneme)}>
            Practicar /{f.phoneme}/
          </button>
        </div>
      ))}
    </section>
  )
}

function Omitidas({ items }) {
  if (!items.length) return null
  return (
    <section className="cp-block">
      <h4>
        Palabras <span className="count">{items.length} omitida{items.length > 1 ? 's' : ''}</span>
      </h4>
      {items.map((o, i) => (
        <p key={i} className="cp-omission">
          Te saltaste <strong>{o.surface}</strong>
          {o.context && <> en «{o.context}»</>}.
          {o.times_in_session > 1 && (
            <em> {o.times_in_session}ª vez en esta sesión</em>
          )}
          {/* La causa importa: saltarse «any» no es descuido, es la gramática
              materna colándose, y eso cambia cómo lo corriges. */}
          {o.why && <span className="cp-why"> — {o.why}.</span>}
        </p>
      ))}
    </section>
  )
}

function Ritmo({ rhythm }) {
  if (!rhythm?.words?.length) return null
  const pico = Math.max(...rhythm.words.map((w) => w.ms), 1)

  return (
    <section className="cp-block">
      <h4>
        Ritmo
        <span className="count">
          {rhythm.wpm} wpm
          {rhythm.long_pauses > 0 && ` · ${rhythm.long_pauses} pausas largas`}
        </span>
      </h4>
      {/* Cada bloque es una palabra y su ancho es lo que duró: el reparto se
          ve antes de leer ninguna cifra. */}
      <div className="cp-rhythm">
        {rhythm.words.map((w, i) => (
          <span
            key={i}
            className="bar"
            style={{ height: `${Math.max((w.ms / pico) * 100, 12)}%` }}
            title={`${w.surface}: ${w.ms} ms`}
          />
        ))}
      </div>
      {rhythm.cut_before && (
        <p className="cp-hint">
          Cortaste antes de «{rhythm.cut_before}». Intenta llegar hasta la coma sin
          respirar.
        </p>
      )}
    </section>
  )
}

function Recientes({ items, onPick }) {
  if (items.length < 2) return null
  return (
    <section className="cp-block">
      <h4>
        Últimas {items.length} oraciones
      </h4>
      <div className="cp-recent">
        {items.map((r) => (
          <button
            key={r.attempt_id}
            className={!r.usable ? 'unusable' : r.overall >= 85 ? 'ok' : r.overall >= 70 ? 'near' : 'bad'}
            style={{ height: `${r.usable ? Math.max(r.overall, 12) : 100}%` }}
            onClick={() => onPick(r.attempt_id)}
            title={r.usable ? `${r.overall} · ${r.text}` : `Sin evaluar · ${r.text}`}
          />
        ))}
      </div>
    </section>
  )
}

export default function CoachPanel({ panel, onPractice, onPick }) {
  const cue = useAudioCue()
  if (!panel?.found) return null

  const limpia =
    !panel.phonemes.length && !panel.omissions.length && !panel.rhythm?.long_pauses

  return (
    <div className="coach-panel">
      <header className="cp-head">
        <span className="cp-label">
          {panel.sentence_idx != null ? `Oración ${panel.sentence_idx + 1}` : 'Lectura'} · cerrada
        </span>
        <span className={`cp-score ${panel.overall >= 85 ? 'ok' : panel.overall >= 70 ? 'near' : 'bad'}`}>
          {panel.overall}
        </span>
      </header>

      <p className="cp-text">{panel.text}</p>

      {limpia && <p className="cp-clean">Sin nada que corregir en esta oración.</p>}

      <Fonemas items={panel.phonemes} onPractice={onPractice} cue={cue} />
      <Omitidas items={panel.omissions} />
      <Ritmo rhythm={panel.rhythm} />
      <Recientes items={panel.recent} onPick={onPick} />

      {cue.error && <p className="error inline">{cue.error}</p>}
    </div>
  )
}

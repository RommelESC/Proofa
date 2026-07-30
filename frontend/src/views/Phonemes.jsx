import { useEffect, useState } from 'react'

import { baselineProgress, getDrill, submitAttempt } from '../api'
import { startRecording } from '../audio/recorder'
import DrillPanel from '../components/DrillPanel'
import FeedbackPanel from '../components/FeedbackPanel'
import SoundMap from '../components/SoundMap'
import WordHeatmap from '../components/WordHeatmap'

/**
 * Frases de calibracion: cada una concentra trampas tipicas de un
 * hispanohablante. Sirven para afinar umbrales contra tu propia voz en vez
 * de a ojo, y como suite de regresion al cambiar de motor.
 *
 * Se quedan aunque ahora exista la practica dirigida: son cosas distintas.
 * El drill sale de tu historial y cambia contigo; estas son fijas justamente
 * para que dos medidas separadas en el tiempo se puedan comparar.
 */
const PRESETS = [
  {
    label: 'Mezcla general',
    text: 'I think the students asked about the very small ship yesterday.',
  },
  {
    label: 'th / v / z',
    text: 'They breathe through those very thin leather things.',
  },
  {
    label: 's- inicial',
    text: 'The Spanish student spoke to a stranger in the school square.',
  },
  {
    label: 'Vocales i / ɪ',
    text: 'He will live here and leave the ship before it sleeps.',
  },
  {
    label: 'Schwa y ritmo',
    text: 'The photographer remembered a comfortable banana about seven times.',
  },
]

export default function Phonemes({ initialSound = null }) {
  const [text, setText] = useState(PRESETS[0].text)
  const [recorder, setRecorder] = useState(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [drill, setDrill] = useState(null)
  const [sounds, setSounds] = useState([])
  // null = «el que peor lleve», que es lo que decide el backend. Llega con
  // valor cuando vienes desde «Practicar /aɪ/» en la corrección.
  const [sound, setSound] = useState(initialSound)

  // Si falla no se dice nada: la vista sirve igual con las frases fijas, y un
  // error por no tener historial todavia seria ruido, no informacion.
  useEffect(() => {
    setDrill(null)
    getDrill(6, sound).then(setDrill).catch(() => {})
  }, [sound])

  useEffect(() => {
    baselineProgress(90)
      .then((d) => setSounds(d.phonemes.filter((p) => p.stdev != null)))
      .catch(() => {})
  }, [])

  function pick(next) {
    setText(next)
    setResult(null)
  }

  async function handleRecord() {
    setError(null)
    if (recorder) {
      setBusy(true)
      try {
        const wavBlob = await recorder.stop()
        setRecorder(null)
        setResult(await submitAttempt({ wavBlob, expectedText: text }))
      } catch (e) {
        setError(e.message)
      } finally {
        setBusy(false)
      }
      return
    }
    try {
      setResult(null)
      setRecorder(await startRecording())
    } catch (e) {
      setError(`No se pudo acceder al micrófono: ${e.message}`)
    }
  }

  return (
    <div className="page phonemes-page">
      <header className="page-head">
        <h1>Fonemas</h1>
        <p className="lede">
          Elige un sonido y practícalo con frases de tu propio libro.
        </p>
      </header>

      <SoundMap phonemes={sounds} current={drill?.ipa ?? sound} onPick={setSound} />

      <div className="sound-detail">
        <DrillPanel drill={drill} onPick={pick} active={text} />

      <section className="presets">
        <span className="presets-label">Calibración</span>
        {PRESETS.map((p) => (
          <button
            key={p.label}
            className={text === p.text ? 'active' : ''}
            onClick={() => pick(p.text)}
          >
            {p.label}
          </button>
        ))}
      </section>

      <textarea
        value={text}
        onChange={(e) => {
          setText(e.target.value)
          setResult(null)
        }}
        rows={3}
        spellCheck={false}
      />

      <div className="controls">
        <button
          className={`record ${recorder ? 'recording' : ''}`}
          onClick={handleRecord}
          disabled={busy}
        >
          {busy ? 'Evaluando…' : recorder ? 'Detener y evaluar' : 'Grabar'}
        </button>
        {recorder && <span className="hint">Lee la frase en voz alta. Sin prisa.</span>}
      </div>

      {error && <p className="error">{error}</p>}

        {result && (
          <>
            <WordHeatmap words={result.assessment.words} />
            <FeedbackPanel coaching={result.coaching} personal={result.personal} />
          </>
        )}
      </div>
    </div>
  )
}

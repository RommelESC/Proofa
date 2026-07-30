import { useCallback, useEffect, useMemo, useState } from 'react'

import {
  attemptPanel,
  compareRhythm,
  getPhonetics,
  glossWord,
  listChapters,
  readChapter,
  readingPace,
  savePosition,
  startTranslation,
  submitAttempt,
  translationProgress,
} from '../api'
import { startRecording } from '../audio/recorder'
import ChaptersAside from '../components/ChaptersAside'
import GuidedBar from '../components/GuidedBar'
import ModeSwitch, { MODES } from '../components/ModeSwitch'
import NarrationBar from '../components/NarrationBar'
import Paragraph from '../components/Paragraph'
import ReaderBar from '../components/ReaderBar'
import { useGuided } from '../hooks/useGuided'
import { useNarration } from '../hooks/useNarration'
import { useReadingPosition } from '../hooks/useReadingPosition'
import { useSpeech } from '../hooks/useSpeech'

/**
 * Cuánto español se revela.
 *
 * `graduada` es la idea que diferencia esto de un lector bilingüe normal: en
 * vez de dar siempre la traducción — con lo que acabas leyendo en español —
 * la ayuda baja con un control conforme mejoras.
 */
const HELP_MODES = [
  { key: 'off', label: 'Solo inglés' },
  { key: 'graded', label: 'Graduada' },
  { key: 'always', label: 'Siempre' },
]

/** Agrupa las oraciones en párrafos conservando el orden de lectura. */
function groupByParagraph(sentences) {
  const groups = []
  for (const s of sentences) {
    const last = groups[groups.length - 1]
    if (last && last[0].paragraph_idx === s.paragraph_idx) last.push(s)
    else groups.push([s])
  }
  return groups
}

export default function Reader({
  chapter,
  initialMode = 'read',
  onOpenChapter,
  onPractice,
  onBack,
}) {
  const [mode, setMode] = useState(initialMode)
  const [sentences, setSentences] = useState([])
  const [helpMode, setHelpMode] = useState('graded')
  const [help, setHelp] = useState(40)
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState(null)

  // Estado de interacción, elevado aquí: solo puede haber una oración activa
  // en todo el capítulo, y una sola barra necesita saber cuál es.
  const [selected, setSelected] = useState(null)
  const [gloss, setGloss] = useState(null)
  const [recorder, setRecorder] = useState(null)
  const [assessment, setAssessment] = useState(null)
  const [busy, setBusy] = useState(false)

  const [pace, setPace] = useState(null)
  const [rhythm, setRhythm] = useState(null)
  const [siblings, setSiblings] = useState([])
  // El panel de Coach. Sale en la respuesta del intento; se puede sustituir
  // por el de otra lectura al pulsar una de la tira de abajo.
  const [panel, setPanel] = useState(null)

  const speech = useSpeech()
  const narration = useNarration(sentences)
  const guided = useGuided(sentences, { wpm: pace?.wpm ?? 110 })
  const listening = mode === 'listen'
  const pacing = mode === 'guided'
  const shadowing = mode === 'shadowing'

  // La columna lateral sale cuando hay un resultado que leer junto al texto.
  // El diseño la pedía solo para Coach; Shadowing tiene el mismo problema —
  // su panel de ritmo tapa igual la oración que acabas de leer — así que se
  // aplica la misma regla al mismo problema.
  const sidePanel = (mode === 'coach' || shadowing) && assessment != null

  // Los tres hooks exponen la misma forma, así que `Paragraph` resalta igual
  // sin saber qué lo mueve: una voz del navegador, audio neuronal o un reloj.
  const highlighter = listening ? narration : pacing ? guided : speech

  // Cambiar de modo apaga lo que estuviera corriendo. Seguir oyendo una voz —
  // o viendo avanzar una banda — después de cambiar de pantalla desconcierta.
  useEffect(() => {
    if (!listening) narration.stop()
    if (!pacing) guided.stop()
    if (listening || pacing) speech.stop()
  }, [listening, pacing])

  useEffect(() => {
    if (pacing && !pace) readingPace().then(setPace).catch(() => {})
  }, [pacing])

  // Seguir la lectura: la oración activa se mantiene a la vista. Vale igual
  // para la voz que para el marcapasos — en Guiada es lo que hace que puedas
  // leer sin tocar nada.
  useEffect(() => {
    const id = highlighter.speakingId
    if ((!listening && !pacing) || id == null) return
    document
      .querySelector(`[data-sentence-id="${id}"]`)
      ?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [listening, pacing, highlighter.speakingId])

  // Solo se restaura en «Leer»: los otros modos tienen su propio recorrido y
  // arrastrarte a mitad del capítulo al entrar sería desconcertante.
  useReadingPosition({
    chapterId: chapter.id,
    sentences,
    restoreTo: mode === 'read' ? chapter.last_sentence_id : null,
  })

  useEffect(() => {
    readChapter(chapter.id).then(setSentences).catch((e) => setError(e.message))
    translationProgress(chapter.id).then(setProgress).catch(() => {})
    // Los hermanos, para la columna lateral. Si falla no se dice nada: la
    // columna simplemente no sale y el lector funciona igual.
    if (chapter.book_id) listChapters(chapter.book_id).then(setSiblings).catch(() => {})
    return () => speech.stop()
  }, [chapter.id])

  useEffect(() => {
    function onKey(e) {
      if (e.key !== 'Escape') return
      if (gloss) setGloss(null)
      else if (selected) closeSelection()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [gloss, selected])

  function closeSelection() {
    speech.stop()
    setSelected(null)
    setAssessment(null)
    setRhythm(null)
    setPanel(null)
    setError(null)
  }

  /** En «Escuchar», tocar una oración arranca la narración desde ahí.
   *  `Paragraph` entrega la oración; la narración trabaja por índice. */
  const playFromSentence = useCallback(
    (sentence) => {
      const i = sentences.findIndex((s) => s.id === sentence.id)
      if (i >= 0) narration.playAt(i)
    },
    [sentences, narration.playAt],
  )

  /** En «Guiada», tocar una oración mueve la banda ahí. El marcapasos cuenta
   *  palabras, así que hay que sumar las de las oraciones anteriores. */
  const paceFromSentence = useCallback(
    (sentence) => {
      let acc = 0
      for (const s of sentences) {
        if (s.id === sentence.id) break
        acc += (s.text_en.match(/[A-Za-z'’-]+/g) ?? []).length || 1
      }
      guided.seekTo(acc)
    },
    [sentences, guided.seekTo],
  )

  // Estable a propósito: `Paragraph` está memoizado y una función nueva en
  // cada render anularía la memoización justo cuando más importa.
  const handleSelect = useCallback(
    (sentence) => {
      if (recorder) return
      speech.stop()
      setSelected((prev) => (prev?.id === sentence.id ? prev : sentence))
      // Ahora que tocar una palabra también selecciona, volver a tocar dentro
      // de la oración que acabas de evaluar no debe borrarte el resultado:
      // consultar una palabra del feedback es justo lo que uno hace después.
      setAssessment((a) => (a?.sentenceId === sentence.id ? a : null))
      setRhythm((r) => (assessment?.sentenceId === sentence.id ? r : null))
      setError(null)
      // Segunda vía para anotar la posición, además del seguimiento por scroll.
      // Un clic es intención explícita — no hay que inferir nada — y no depende
      // de IntersectionObserver, que necesita que la página esté pintando.
      savePosition(chapter.id, sentence.id)
    },
    [recorder, chapter.id, speech.stop, assessment?.sentenceId],
  )

  const handleWord = useCallback(async (word, sentence) => {
    // La IPA llega en milisegundos y el significado puede tardar segundos con
    // un modelo local. Se muestra lo que ya se sabe en lugar de dejar la barra
    // vacía esperando: la interfaz responde al instante aunque la definición
    // todavía venga en camino.
    setGloss({ word, loading: true })
    getPhonetics(word)
      .then(({ ipa }) => setGloss((g) => (g?.word === word ? { ...g, ipa } : g)))
      .catch(() => {})

    try {
      const data = await glossWord(word, sentence.text_en, sentence.id)
      setGloss((g) => (g?.word === word ? { word, ...data } : g))
    } catch (e) {
      setGloss((g) => (g?.word === word ? { word, error: e.message } : g))
    }
  }, [])

  function handlePlay() {
    if (!selected) return
    if (speech.speakingId === selected.id) speech.stop()
    else speech.speak(selected.id, selected.text_en)
  }

  async function handleRecord() {
    if (!selected) return
    setError(null)

    if (recorder) {
      setBusy(true)
      try {
        const wavBlob = await recorder.stop()
        setRecorder(null)
        const data = await submitAttempt({
          wavBlob,
          expectedText: selected.text_en,
          sentenceId: selected.id,
        })
        setAssessment({ sentenceId: selected.id, ...data })
        setPanel(data.panel ?? null)
        // En Shadowing lo que importa es el ritmo, y se calcula aparte porque
        // necesita los tiempos del sintetizador además de los tuyos.
        if (shadowing && data.attempt_id) {
          setRhythm(null)
          compareRhythm(data.attempt_id).then(setRhythm).catch(() => {})
        }
      } catch (e) {
        setError(e.message)
      } finally {
        setBusy(false)
      }
      return
    }

    try {
      speech.stop()
      setAssessment(null)
      setRecorder(await startRecording())
    } catch (e) {
      setError(`Micrófono: ${e.message}`)
    }
  }

  async function handleTranslate() {
    setError(null)
    try {
      await startTranslation(chapter.id)
      const timer = setInterval(async () => {
        const p = await translationProgress(chapter.id)
        setProgress(p)
        if (p.pending === 0) {
          clearInterval(timer)
          setSentences(await readChapter(chapter.id))
        }
      }, 2500)
    } catch (e) {
      setError(e.message)
    }
  }

  function shouldShowEs(index) {
    if (helpMode === 'off') return false
    if (helpMode === 'always') return true
    if (help >= 100) return true
    if (help <= 0) return false
    // Estable por índice: la misma oración siempre decide igual.
    return (index * 37) % 100 < help
  }

  const current = MODES.find((m) => m.key === mode)
  const groups = useMemo(() => groupByParagraph(sentences), [sentences])

  return (
    <div
      className={`reader-view ${sidePanel ? 'with-side-panel' : ''} ${
        siblings.length > 1 ? 'with-chapters' : ''
      }`}
    >
      <header className="reader-head">
        <div className="crumbs">
          <button className="back" onClick={onBack}>
            Biblioteca
          </button>
          <span className="sep">·</span>
          <span className="here">{chapter.title || `Capítulo ${chapter.idx + 1}`}</span>
        </div>
        <ModeSwitch mode={mode} onChange={setMode} />
      </header>

      {!current?.ready ? (
        <div className="mode-pending">
          <h2>{current?.label}</h2>
          <p>{current?.blurb}</p>
          <p className="note">
            Todavía no está construido. El modo aparece aquí para que la estructura
            del producto se entienda completa, no para simular que funciona.
          </p>
          <button onClick={() => setMode('read')}>Volver a Leer</button>
        </div>
      ) : (
        <>
          <div className="reader-controls">
            <div className="segmented">
              {HELP_MODES.map((m) => (
                <button
                  key={m.key}
                  className={helpMode === m.key ? 'active' : ''}
                  onClick={() => setHelpMode(m.key)}
                >
                  {m.label}
                </button>
              ))}
            </div>

            {helpMode === 'graded' && (
              <label className="help-slider">
                <span>ayuda {help}%</span>
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="10"
                  value={help}
                  onChange={(e) => setHelp(Number(e.target.value))}
                />
              </label>
            )}

            {progress && progress.pending > 0 && (
              <button className="ghost" onClick={handleTranslate}>
                Traducir {progress.translated}/{progress.total}
              </button>
            )}
          </div>

          {!speech.supported && (
            <p className="hint">Este navegador no soporta síntesis de voz.</p>
          )}

          <ChaptersAside
            chapters={siblings}
            currentId={chapter.id}
            onOpen={(next) => onOpenChapter?.(next, mode)}
          />

          <div
            className={`reader ${selected && !listening && !pacing ? 'focused' : ''} ${
              selected || gloss || listening || pacing ? 'with-bar' : ''
            } ${pacing ? 'pacing' : ''}`}
          >
            {groups.map((group, i) => {
              // El índice de carácter solo baja al párrafo que suena. Los demás
              // reciben props idénticas entre latidos y la memoización los salta.
              const here = group.some((s) => s.id === highlighter.speakingId)
              return (
                <Paragraph
                  key={group[0].id}
                  sentences={group}
                  showEs={shouldShowEs(i)}
                  speakingId={here ? highlighter.speakingId : null}
                  charIndex={here ? highlighter.charIndex : -1}
                  selectedId={listening || pacing ? null : selected?.id ?? null}
                  assessment={assessment}
                  onSelect={
                    listening ? playFromSentence : pacing ? paceFromSentence : handleSelect
                  }
                  // En Escuchar y Guiada la barra inferior es otra, así que una
                  // definición no tendría dónde aparecer: ahí un toque solo
                  // mueve la reproducción o la banda.
                  onWord={listening || pacing ? undefined : handleWord}
                />
              )
            })}
          </div>

          {listening ? (
            <NarrationBar
              narration={narration}
              total={sentences.length}
              onExit={() => setMode('read')}
            />
          ) : pacing ? (
            <GuidedBar guided={guided} pace={pace} onExit={() => setMode('read')} />
          ) : (
            <ReaderBar
              sentence={selected}
              gloss={gloss}
              assessment={assessment}
              speech={speech}
              recording={!!recorder}
              busy={busy}
              error={error}
              shadowing={shadowing}
              coaching={mode === 'coach'}
              rhythm={rhythm}
              panel={panel}
              side={sidePanel}
              onPractice={onPractice}
              onPickAttempt={(id) => attemptPanel(id).then(setPanel).catch(() => {})}
              onPlay={handlePlay}
              onRecord={handleRecord}
              onClose={closeSelection}
              onCloseGloss={() => setGloss(null)}
            />
          )}
        </>
      )}
    </div>
  )
}

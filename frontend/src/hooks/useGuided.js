import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

/**
 * Marcapasos de lectura silenciosa.
 *
 * Una banda avanza por el texto a tu velocidad objetivo. No hay audio: lo que
 * entrena es no volver atrás. Leyendo solo, el ojo retrocede constantemente
 * sobre lo que ya entendió, y ese hábito es la mitad de la lentitud.
 *
 * Expone la misma forma que `useSpeech` y `useNarration` (`speakingId`,
 * `charIndex`), así que `Paragraph` resalta igual sin saber qué lo mueve. Los
 * tres modos que iluminan texto comparten el mismo contrato.
 *
 * La posición se calcula desde el RELOJ, no contando ticks. Un intervalo se
 * estrangula cuando la pestaña pasa a segundo plano, y contando ticks el
 * marcapasos se quedaría atrás en silencio — que es peor que pararse, porque
 * seguirías creyendo que vas a la velocidad que marcaste.
 */

const TICK_MS = 80

/** Offsets de carácter donde empieza cada palabra. Mismo criterio que Paragraph. */
function wordStarts(text) {
  const out = []
  const re = /[A-Za-z'’-]+/g
  let m
  while ((m = re.exec(text)) !== null) out.push(m.index)
  return out
}

export function useGuided(sentences, { wpm: initialWpm = 110 } = {}) {
  const [wpm, setWpm] = useState(initialWpm)
  const [playing, setPlaying] = useState(false)
  const [word, setWord] = useState(0) // palabra absoluta dentro del capítulo

  // Ancla del cálculo: desde qué palabra y desde qué instante se cuenta.
  const anchorRef = useRef({ at: 0, word: 0 })

  // Tu velocidad medida llega por red, después del primer render, y
  // `useState` ignora los cambios de su valor inicial. Sin esto la barra se
  // quedaba en el valor por defecto (110) mientras el propio aviso de debajo
  // decía «tu ritmo son 118 wpm» — dos números distintos en el mismo panel.
  //
  // Solo se adopta si no has tocado el control: una vez eliges velocidad,
  // manda tu elección.
  const touchedRef = useRef(false)
  useEffect(() => {
    if (touchedRef.current) return
    // Reanclar antes de cambiar el ritmo: si no, el tiempo ya transcurrido se
    // recalcularía a la velocidad nueva y la banda daría un salto.
    anchorRef.current = { at: Date.now(), word: anchorRef.current.word }
    setWpm(initialWpm)
  }, [initialWpm])

  // Índice del capítulo: dónde empieza cada oración y dónde cada palabra suya.
  const map = useMemo(() => {
    let acc = 0
    const rows = sentences.map((s) => {
      const starts = wordStarts(s.text_en)
      const row = { id: s.id, from: acc, count: starts.length || 1, starts }
      acc += row.count
      return row
    })
    return { rows, total: acc }
  }, [sentences])

  const stop = useCallback(() => {
    setPlaying(false)
    setWord(0)
    anchorRef.current = { at: 0, word: 0 }
  }, [])

  const seekTo = useCallback((next) => {
    const w = Math.max(0, next)
    setWord(w)
    anchorRef.current = { at: Date.now(), word: w }
  }, [])

  const toggle = useCallback(() => {
    setPlaying((was) => {
      if (!was) anchorRef.current = { at: Date.now(), word: word }
      return !was
    })
  }, [word])

  // Cambiar de velocidad no debe teletransportar la banda: se reancla en la
  // palabra actual y a partir de ahí corre al ritmo nuevo.
  const changeWpm = useCallback(
    (next) => {
      touchedRef.current = true
      anchorRef.current = { at: Date.now(), word: word }
      setWpm(next)
    },
    [word],
  )

  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => {
      const { at, word: from } = anchorRef.current
      const minutes = (Date.now() - at) / 60000
      const next = from + minutes * wpm
      if (next >= map.total) {
        setWord(map.total)
        setPlaying(false)
        return
      }
      setWord(next)
    }, TICK_MS)
    return () => clearInterval(id)
  }, [playing, wpm, map.total])

  // De palabra absoluta a (oración, offset de carácter).
  const position = useMemo(() => {
    if (!map.rows.length) return { id: null, charIndex: -1, index: null }
    const w = Math.floor(word)
    let lo = 0
    let hi = map.rows.length - 1
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1
      if (map.rows[mid].from <= w) lo = mid
      else hi = mid - 1
    }
    const row = map.rows[lo]
    const within = Math.min(w - row.from, row.starts.length - 1)
    return {
      id: row.id,
      index: lo,
      charIndex: within >= 0 && row.starts.length ? row.starts[within] : -1,
    }
  }, [word, map])

  return {
    // Mismo contrato que useSpeech / useNarration.
    speakingId: playing || word > 0 ? position.id : null,
    charIndex: playing || word > 0 ? position.charIndex : -1,

    index: position.index,
    playing,
    wpm,
    setWpm: changeWpm,
    toggle,
    stop,
    seekTo,
    /** Palabras leídas y totales: es el progreso que significa algo aquí. */
    word: Math.floor(word),
    words: map.total,
    /** Minutos que queda a la velocidad actual. */
    remaining: wpm > 0 ? Math.ceil((map.total - word) / wpm) : null,
  }
}

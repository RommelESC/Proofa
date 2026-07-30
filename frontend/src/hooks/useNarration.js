import { useCallback, useEffect, useRef, useState } from 'react'

import { speechMarks, speechUrl } from '../api'

/**
 * Narración continua del capítulo con resaltado palabra por palabra.
 *
 * Expone la misma forma que `useSpeech` (`speakingId`, `charIndex`), así que
 * `Paragraph` resalta igual sin saber de dónde viene el audio. Una es la voz
 * del navegador; ésta es voz neuronal con tiempos medidos por el motor.
 *
 * Diferencia que sí importa: aquí los tiempos vienen del sintetizador, no de
 * la estimación del navegador. El resaltado no se desfasa cuando hay una pausa
 * larga o un número leído en voz.
 */
export function useNarration(sentences) {
  const [index, setIndex] = useState(null)
  const [charIndex, setCharIndex] = useState(-1)
  const [playing, setPlaying] = useState(false)
  const [rate, setRate] = useState(1)
  const [error, setError] = useState(null)

  const audioRef = useRef(null)
  const marksRef = useRef([])
  const indexRef = useRef(null)
  // Cada reproducción lleva número. `play()` es asíncrono, así que cambiar de
  // oración o salir del modo aborta uno que sigue en vuelo; comparando el
  // número se sabe si esa promesa aún manda o ya la reemplazó otra.
  const tokenRef = useRef(0)
  const failuresRef = useRef(0)

  useEffect(() => {
    const audio = new Audio()
    audio.preload = 'auto'
    audioRef.current = audio
    return () => {
      audio.pause()
      audio.src = ''
    }
  }, [])

  useEffect(() => {
    if (audioRef.current) audioRef.current.playbackRate = rate
  }, [rate])

  const stop = useCallback(() => {
    tokenRef.current += 1 // invalida cualquier play() pendiente
    audioRef.current?.pause()
    setPlaying(false)
    setIndex(null)
    setCharIndex(-1)
    setError(null)
    indexRef.current = null
    marksRef.current = []
  }, [])

  const playAt = useCallback(
    async (i) => {
      const audio = audioRef.current
      if (!audio || i == null || i < 0 || i >= sentences.length) {
        stop()
        return
      }

      const token = ++tokenRef.current
      const sentence = sentences[i]
      indexRef.current = i
      setIndex(i)
      setCharIndex(-1)
      setError(null)

      try {
        // Las marcas primero: piden la síntesis, así que cuando el audio se
        // solicite ya estará en caché del servidor y arranca sin esperar.
        marksRef.current = (await speechMarks(sentence.text_en)).marks ?? []
      } catch {
        // Sin marcas se oye igual, solo que sin resaltado. No vale abortar.
        marksRef.current = []
      }
      if (tokenRef.current !== token) return // el usuario saltó mientras cargaba

      audio.src = speechUrl(sentence.text_en)
      audio.playbackRate = rate
      try {
        await audio.play()
        if (tokenRef.current !== token) return
        setPlaying(true)
      } catch (e) {
        // Que otra reproducción haya reemplazado a ésta es el funcionamiento
        // normal — pasa cada vez que saltas de oración o sales del modo — y
        // el navegador lo reporta como AbortError. Enseñarlo como fallo era
        // ruido: el mensaje aparecía justo cuando todo iba bien.
        if (tokenRef.current !== token || e.name === 'AbortError') return
        setError(`No se pudo reproducir: ${e.message}`)
        setPlaying(false)
      }

      // Adelantar la siguiente mientras suena ésta: sin esto se oye un hueco
      // entre oraciones mientras el servidor sintetiza.
      const next = sentences[i + 1]
      if (next) speechMarks(next.text_en).catch(() => {})
    },
    [sentences, rate, stop],
  )

  useEffect(() => {
    const audio = audioRef.current
    if (!audio) return

    const onTime = () => {
      const ms = audio.currentTime * 1000
      const marks = marksRef.current
      let offset = -1
      for (const m of marks) {
        if (m.audio_ms <= ms) offset = m.text_offset
        else break
      }
      setCharIndex(offset)
    }
    const onEnded = () => {
      failuresRef.current = 0 // una oración completa es prueba de que va bien
      const next = (indexRef.current ?? -1) + 1
      if (next < sentences.length) playAt(next)
      else stop()
    }

    // Un audio que falla no emite `ended`, así que sin esto una sola oración
    // que el sintetizador rechace deja el capítulo parado para siempre. Se
    // salta y se sigue; si fallan varias seguidas el problema es el servicio
    // y no la oración, y entonces sí vale la pena parar y decirlo.
    const onError = () => {
      const at = indexRef.current
      if (at == null) return
      failuresRef.current += 1
      if (failuresRef.current > 3) {
        stop()
        setError('La narración se detuvo: el sintetizador no responde.')
        return
      }
      const next = at + 1
      if (next < sentences.length) playAt(next)
      else stop()
    }

    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('ended', onEnded)
    audio.addEventListener('error', onError)
    return () => {
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('ended', onEnded)
      audio.removeEventListener('error', onError)
    }
  }, [sentences, playAt, stop])

  const toggle = useCallback(() => {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
      setPlaying(false)
    } else if (indexRef.current != null) {
      audio.play().catch(() => {}) // reanudar puede abortarse; no es un fallo
      setPlaying(true)
    } else {
      playAt(0)
    }
  }, [playing, playAt])

  const skip = useCallback(
    (delta) => playAt((indexRef.current ?? 0) + delta),
    [playAt],
  )

  return {
    // Misma forma que useSpeech: Paragraph no distingue el origen del audio.
    speakingId: index != null ? sentences[index]?.id ?? null : null,
    charIndex,
    index,
    playing,
    rate,
    error,
    setRate,
    playAt,
    toggle,
    skip,
    stop,
  }
}

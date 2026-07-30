import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Reproduce audio de referencia del backend (voz neuronal de Azure).
 *
 * Un solo elemento <audio> reutilizado: pedir un audio nuevo corta el
 * anterior. Al comparar un par mínimo quieres oír «think» e inmediatamente
 * «sink»; que se encimaran haría inútil justo el contraste que se enseña.
 */
export function useAudioCue() {
  const [playing, setPlaying] = useState(null)
  const [error, setError] = useState(null)
  const audioRef = useRef(null)

  useEffect(() => {
    const audio = new Audio()
    audio.addEventListener('ended', () => setPlaying(null))
    audio.addEventListener('error', () => {
      setPlaying(null)
      setError('No se pudo reproducir el audio')
    })
    audioRef.current = audio
    return () => {
      audio.pause()
      audio.src = ''
    }
  }, [])

  const play = useCallback((key, { text, ipa, slow = false }) => {
    const audio = audioRef.current
    if (!audio || !text) return

    const params = new URLSearchParams({ text })
    if (ipa) params.set('ipa', ipa)
    if (slow) params.set('slow', 'true')

    setError(null)
    audio.pause()
    audio.currentTime = 0
    audio.src = `/api/speech?${params}`
    setPlaying(key)
    audio.play().catch(() => {
      setPlaying(null)
      setError('No se pudo reproducir el audio')
    })
  }, [])

  return { play, playing, error }
}

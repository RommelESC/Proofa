import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Narracion con resaltado palabra por palabra (efecto karaoke).
 *
 * Usa la Web Speech API del navegador: gratis, sin backend, sin latencia de
 * red. La voz es mediocre comparada con un TTS neuronal, pero para empezar
 * vale mucho mas que cero — y la interfaz no cambia cuando se sustituya por
 * audio neuronal cacheado.
 *
 * Los eventos `onboundary` de palabra no estan igual de soportados en todos
 * los navegadores; si no llegan, el audio se reproduce igual y simplemente
 * no hay resaltado.
 */
export function useSpeech() {
  const [speakingId, setSpeakingId] = useState(null)
  const [charIndex, setCharIndex] = useState(-1)
  const [voices, setVoices] = useState([])
  const utteranceRef = useRef(null)

  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const load = () => setVoices(window.speechSynthesis.getVoices())
    load()
    window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', load)
      window.speechSynthesis.cancel()
    }
  }, [])

  const englishVoices = voices.filter((v) => v.lang?.startsWith('en'))

  const stop = useCallback(() => {
    window.speechSynthesis?.cancel()
    utteranceRef.current = null
    setSpeakingId(null)
    setCharIndex(-1)
  }, [])

  const speak = useCallback(
    (id, text, { rate = 0.9, voiceURI } = {}) => {
      if (!('speechSynthesis' in window)) return
      window.speechSynthesis.cancel()

      const utterance = new SpeechSynthesisUtterance(text)
      utterance.lang = 'en-US'
      utterance.rate = rate

      const voice =
        englishVoices.find((v) => v.voiceURI === voiceURI) ?? englishVoices[0]
      if (voice) utterance.voice = voice

      utterance.onboundary = (e) => {
        if (e.name === 'word' || e.charIndex != null) setCharIndex(e.charIndex)
      }
      utterance.onend = () => {
        setSpeakingId(null)
        setCharIndex(-1)
      }
      utterance.onerror = () => {
        setSpeakingId(null)
        setCharIndex(-1)
      }

      utteranceRef.current = utterance
      setSpeakingId(id)
      setCharIndex(-1)
      window.speechSynthesis.speak(utterance)
    },
    [englishVoices],
  )

  return {
    speak,
    stop,
    speakingId,
    charIndex,
    voices: englishVoices,
    supported: typeof window !== 'undefined' && 'speechSynthesis' in window,
  }
}

import { useEffect, useRef } from 'react'

import { savePosition } from '../api'

const SAVE_DELAY_MS = 1500

/**
 * Recuerda dónde vas leyendo.
 *
 * Usa IntersectionObserver en vez de escuchar `scroll`: el navegador ya sabe
 * qué está visible y lo calcula fuera del hilo principal. Con 232 oraciones,
 * medir posiciones a mano en cada evento de scroll sí se nota.
 *
 * `rootMargin` recorta la zona sensible al tercio central de la pantalla: la
 * oración que estás leyendo está a media altura, no pegada al borde.
 */
export function useReadingPosition({ chapterId, sentences, restoreTo }) {
  const timer = useRef(null)
  const lastSaved = useRef(null)
  const restored = useRef(false)

  // Guardar mientras lees.
  useEffect(() => {
    if (!chapterId || sentences.length === 0) return

    const nodes = document.querySelectorAll('[data-sentence-id]')
    if (nodes.length === 0) return

    let current = null
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue
          const id = Number(entry.target.dataset.sentenceId)
          // La más avanzada que se ve: leer es avanzar, y volver un poco atrás
          // no debería reescribir la marca hacia atrás en cada scroll.
          if (current === null || id > current) current = id
        }
        if (current === null || current === lastSaved.current) return

        clearTimeout(timer.current)
        timer.current = setTimeout(() => {
          lastSaved.current = current
          savePosition(chapterId, current)
        }, SAVE_DELAY_MS)
      },
      { rootMargin: '-33% 0px -33% 0px', threshold: 0 },
    )

    nodes.forEach((n) => observer.observe(n))
    return () => {
      observer.disconnect()
      clearTimeout(timer.current)
    }
  }, [chapterId, sentences.length])

  // Restaurar al abrir. Una sola vez por capítulo: si no, cualquier
  // re-render te arrastraría de vuelta mientras lees.
  useEffect(() => {
    if (restored.current || !restoreTo || sentences.length === 0) return
    const node = document.querySelector(`[data-sentence-id="${restoreTo}"]`)
    if (!node) return
    restored.current = true
    node.scrollIntoView({ block: 'center' })
  }, [restoreTo, sentences.length])

  useEffect(() => {
    restored.current = false
    lastSaved.current = null
  }, [chapterId])
}

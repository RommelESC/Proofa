import { memo } from 'react'

import WordHeatmap from './WordHeatmap'

/** Divide conservando offsets: el resaltado del TTS llega como índice de carácter. */
function tokenize(text) {
  const tokens = []
  const re = /[A-Za-z'’-]+|[^A-Za-z'’-]+/g
  let match
  while ((match = re.exec(text)) !== null) {
    tokens.push({ text: match[0], start: match.index, isWord: /[A-Za-z]/.test(match[0]) })
  }
  return tokens
}

/**
 * Un párrafo del libro. Componente puramente visual: no tiene estado ni
 * controles propios.
 *
 * Los botones vivían aquí, en línea con la prosa. Con una oración
 * seleccionada ya rompían el renglón, y al grabar aparecían en TODAS las
 * oraciones del párrafo a la vez. El texto tiene que ser texto: la
 * interacción ocurre en la barra inferior, siempre en el mismo sitio.
 *
 * Va memoizado, y recibe `speakingId`/`charIndex` sueltos en vez del objeto
 * del hook: durante la narración el índice de carácter cambia unas cuatro
 * veces por segundo, y sin esto un capítulo de 500 oraciones se repintaría
 * entero en cada latido. El lector solo pasa el índice al párrafo que suena.
 */
function Paragraph({
  sentences,
  showEs,
  speakingId,
  charIndex,
  selectedId,
  assessment,
  onSelect,
  onWord,
}) {
  const first = sentences[0]
  if (first?.is_heading) {
    return <h3 className="chapter-heading">{first.text_en}</h3>
  }

  // El español va por párrafo, no intercalado oración por oración: leer
  // traducciones sueltas entre medias rompe el hilo del texto.
  const spanish = sentences.map((s) => s.text_es).filter(Boolean).join(' ')
  const hasSelection = sentences.some((s) => s.id === selectedId)

  return (
    <div className={`paragraph ${hasSelection ? 'has-selection' : ''}`}>
      <p className="en">
        {sentences.map((s) => {
          const speaking = speakingId === s.id
          const selected = selectedId === s.id
          const scored = assessment?.sentenceId === s.id

          if (scored) {
            return (
              <span key={s.id} className="s scored" data-sentence-id={s.id}>
                <WordHeatmap words={assessment.assessment.words} />{' '}
              </span>
            )
          }

          return (
            <span
              key={s.id}
              // Ancla de la memoria de posición: el observador de visibilidad
              // busca por este atributo, y `scrollIntoView` lo usa al reanudar.
              data-sentence-id={s.id}
              className={`s ${speaking ? 'speaking' : ''} ${selected ? 'selected' : ''}`}
              // Cualquier toque en la oración la selecciona, incluido el que
              // cae sobre una palabra. Antes se ignoraban los toques sobre
              // palabras para no pisar la consulta del diccionario, y el
              // resultado era que la oración solo se podía seleccionar
              // acertando en un hueco entre palabras — el 40% de su
              // superficie, y ninguno donde uno apunta. Tocar el texto y que
              // no pase nada es la peor respuesta posible.
              //
              // El toque sobre palabra hace las dos cosas: la definición sube
              // por su propio manejador y esto se ejecuta después, al burbujear.
              // La barra inferior ya estaba hecha para mostrar ambas.
              onClick={() => onSelect(s)}
            >
              {tokenize(s.text_en).map((token, i) => {
                if (!token.isWord) return <span key={i}>{token.text}</span>
                const lit =
                  speaking &&
                  charIndex >= token.start &&
                  charIndex < token.start + token.text.length
                return (
                  <span
                    key={i}
                    // Sin `onWord` las palabras no son interactivas: en los
                    // modos donde la barra inferior no es la de lectura, una
                    // definición se quedaría sin sitio donde mostrarse.
                    className={`w ${lit ? 'lit' : ''} ${onWord ? 'tappable' : ''}`}
                    onClick={onWord ? () => onWord(token.text, s) : undefined}
                  >
                    {token.text}
                  </span>
                )
              })}{' '}
            </span>
          )
        })}
      </p>

      {showEs && spanish && <p className="es">{spanish}</p>}
    </div>
  )
}

export default memo(Paragraph)

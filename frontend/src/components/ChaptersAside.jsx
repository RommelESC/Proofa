/**
 * Los capítulos del libro, al lado del texto.
 *
 * Antes, saltar de capítulo obligaba a volver a Biblioteca, abrir el libro y
 * buscar en la lista — tres pasos y perder de vista lo que estabas leyendo.
 * En una pantalla ancha esa columna cabe sin quitarle un píxel a la lectura,
 * que es justo lo que sobra a los lados.
 *
 * Por debajo de 1440px se esconde: ahí el espacio sí sale del texto.
 */
export default function ChaptersAside({ chapters, currentId, onOpen }) {
  if (!chapters?.length) return null

  return (
    <nav className="chapters-aside" aria-label="Capítulos del libro">
      <h3>Capítulos</h3>
      <ol>
        {chapters.map((ch) => {
          const pct = ch.sentences ? (ch.reached / ch.sentences) * 100 : 0
          const actual = ch.id === currentId
          return (
            <li key={ch.id}>
              <button
                className={actual ? 'current' : ''}
                onClick={() => !actual && onOpen(ch)}
                aria-current={actual ? 'true' : undefined}
                title={`${ch.reached} de ${ch.sentences} oraciones alcanzadas`}
              >
                <span className="ch-name">{ch.title || `Capítulo ${ch.idx + 1}`}</span>
                <span className="ch-line">
                  <span className="track">
                    <span className="fill" style={{ width: `${pct}%` }} />
                  </span>
                  {/* «Practicado» no es «leído»: haber pasado por una oración no
                      es haberla dicho en voz alta. */}
                  {ch.practiced > 0 && <span className="said">{ch.practiced}</span>}
                </span>
              </button>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}

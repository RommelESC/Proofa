import { Sound, SoundSlow } from './icons'

/**
 * Botón para oír cómo debería sonar algo.
 *
 * `slow` no es un adorno: bajar la velocidad es lo que permite percibir un
 * sonido dentro de un grupo consonántico como el /t/ final de «asked».
 */
export default function SpeakButton({ cue, id, text, ipa, slow = false, label }) {
  const key = `${id}${slow ? ':slow' : ''}`
  const active = cue.playing === key

  return (
    <button
      type="button"
      className={`speak ${slow ? 'slow' : ''} ${active ? 'active' : ''}`}
      onClick={() => cue.play(key, { text, ipa, slow })}
      title={slow ? `Escuchar «${text}» despacio` : `Escuchar «${text}»`}
      aria-label={slow ? `Escuchar ${text} despacio` : `Escuchar ${text}`}
    >
      {slow ? <SoundSlow size={15} /> : <Sound size={15} />}
      {label && <span>{label}</span>}
    </button>
  )
}

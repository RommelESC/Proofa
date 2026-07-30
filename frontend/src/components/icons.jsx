/**
 * Iconos del sistema visual de Profa.
 *
 * Extraidos del diseno: SVG dibujados a proposito para este producto, no una
 * libreria generica. Usan `currentColor` y trazo 1.55, asi que heredan color
 * y peso del contexto sin configuracion.
 *
 * Los del diseno se generaron desde design/Profa-standalone-src.html y no se
 * editan a mano. Al final del archivo hay una seccion dibujada aqui, para
 * cosas que el diseno no cubria; sigue las mismas reglas de rejilla y trazo.
 */

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.55,
  strokeLinejoin: 'round',
  strokeLinecap: 'round',
}

function Icon({ children, size = 18, ...rest }) {
  return (
    <svg width={size} height={size} viewBox="0 0 18 18" {...base} {...rest} aria-hidden="true">
      {children}
    </svg>
  )
}

export const Coach = (p) => <Icon {...p}><rect x="6.9" y="2.6" width="4.2" height="8" rx="2.1"></rect><path d="M4.2 9.4a4.8 4.8 0 009.6 0M9 14.2v1.9"></path></Icon>

export const Guided = (p) => <Icon {...p}><path d="M3.2 5.2h11.6M3.2 12.8h6.6"></path><rect x="3.2" y="8" width="11.6" height="2.6" rx="1.3" fill="currentColor" stroke="none"></rect></Icon>

export const Import = (p) => <Icon {...p}><path d="M9 4v10M4 9h10"></path></Icon>

export const Library = (p) => <Icon {...p}><rect x="3" y="3.5" width="3.4" height="12" rx=".8"></rect><rect x="7.6" y="3.5" width="3.4" height="12" rx=".8"></rect><path d="M12.7 4.4l2.5.6-2.2 10.9-2.1-.5"></path></Icon>

export const Listen = (p) => <Icon {...p}><path d="M5.6 6.4v5.2M8.2 3.8v10.4M10.8 6v6M13.4 7.6v2.8"></path></Icon>

export const Phonemes = (p) => <Icon {...p}><circle cx="9" cy="9" r="6.4"></circle><path d="M6.2 7.3c1.7-1.5 3.9-1.5 5.6 0M6.2 11c1.7 1.3 3.9 1.3 5.6 0"></path></Icon>

export const Progress = (p) => <Icon {...p}><path d="M3.2 15.2h11.6"></path><path d="M5.4 12.4V9.6M9 12.4V5.4M12.6 12.4V7.6" strokeWidth="2.4"></path></Icon>

export const Read = (p) => <Icon {...p}><path d="M4 3.6h7.4L15 7.2v8.2H4z"></path><path d="M11.4 3.6V7.2H15"></path><path d="M6.6 9.4h5M6.6 12.2h3"></path></Icon>

export const Replay = (p) => <Icon {...p}><path d="M4.5 8V7a2.5 2.5 0 012.5-2.5h6.5M13.5 10v1a2.5 2.5 0 01-2.5 2.5H4.5"></path><path d="M11.4 2.6l2.2 1.9-2.2 1.9M6.6 11.6l-2.2 1.9 2.2 1.9"></path></Icon>

export const Resume = (p) => <Icon {...p}><path d="M6 4l8 5-8 5z"></path></Icon>

export const Search = (p) => <Icon {...p}><circle cx="8" cy="8" r="4.6"></circle><path d="M11.6 11.6l3.6 3.6"></path></Icon>

export const Settings = (p) => <Icon {...p}><path d="M3 6h3.4M10.4 6h4.6M3 12h6.4M13.4 12h1.6"></path><circle cx="8.4" cy="6" r="1.9"></circle><circle cx="11.4" cy="12" r="1.9"></circle></Icon>

export const Shadowing = (p) => <Icon {...p}><circle cx="6.2" cy="9" r="2.1"></circle><path d="M10 5.7a5.2 5.2 0 010 6.6M12.9 3.5a9 9 0 010 11"></path></Icon>

/* --- Dibujados a mano, no venian en el diseno --- */

/** Altavoz: «oye cómo debería sonar». */
export const Sound = (p) => <Icon {...p}><path d="M3.6 7.1h2.1L9.3 4.2v9.6L5.7 10.9H3.6z"></path><path d="M11.6 6.8a3.2 3.2 0 010 4.4M13.6 5.2a5.6 5.6 0 010 7.6"></path></Icon>

/**
 * Lo mismo, despacio. Los arcos se sustituyen por puntos separados: el
 * espaciado ES la metafora — sonido estirado en el tiempo — y a 16px se
 * distingue del altavoz normal de un vistazo, que es lo que hace falta
 * cuando los dos botones van uno al lado del otro.
 */
export const SoundSlow = (p) => <Icon {...p}><path d="M3.6 7.1h2.1L9.3 4.2v9.6L5.7 10.9H3.6z"></path><path d="M11.7 9h.01M13.7 9h.01M15.7 9h.01" strokeWidth="1.9"></path></Icon>

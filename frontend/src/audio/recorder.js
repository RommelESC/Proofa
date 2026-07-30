/**
 * Grabacion y conversion a WAV PCM 16 kHz mono en el navegador.
 *
 * Por que no mandamos el webm/opus de MediaRecorder directo: el SDK de Azure
 * y los modelos wav2vec2 esperan PCM 16 kHz. Convertir en el servidor exigiria
 * ffmpeg como dependencia externa. Haciendolo aqui con Web Audio, el backend
 * se queda sin dependencias binarias.
 */

const TARGET_SR = 16000

export async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  })

  const recorder = new MediaRecorder(stream)
  const chunks = []
  recorder.ondataavailable = (e) => {
    if (e.data.size > 0) chunks.push(e.data)
  }
  recorder.start()

  return {
    stop: () =>
      new Promise((resolve) => {
        recorder.onstop = async () => {
          stream.getTracks().forEach((t) => t.stop())
          const blob = new Blob(chunks, { type: recorder.mimeType })
          resolve(await blobToWav16k(blob))
        }
        recorder.stop()
      }),
  }
}

export async function blobToWav16k(blob) {
  const buffer = await blob.arrayBuffer()

  const ctx = new AudioContext()
  const decoded = await ctx.decodeAudioData(buffer)
  await ctx.close()

  // OfflineAudioContext remuestrea con mejor calidad que una interpolacion
  // lineal a mano, y de paso mezcla a mono.
  const offline = new OfflineAudioContext(
    1,
    Math.max(1, Math.ceil(decoded.duration * TARGET_SR)),
    TARGET_SR,
  )
  const source = offline.createBufferSource()
  source.buffer = decoded
  source.connect(offline.destination)
  source.start()

  const rendered = await offline.startRendering()
  return encodeWav(rendered.getChannelData(0), TARGET_SR)
}

/** Float32 [-1,1] -> Blob WAV PCM 16 bits. */
function encodeWav(samples, sampleRate) {
  const bytesPerSample = 2
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample)
  const view = new DataView(buffer)

  const writeString = (offset, str) => {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i))
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + samples.length * bytesPerSample, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true) // tamano del bloque fmt
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, 1, true) // mono
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * bytesPerSample, true) // byte rate
  view.setUint16(32, bytesPerSample, true) // block align
  view.setUint16(34, 8 * bytesPerSample, true)
  writeString(36, 'data')
  view.setUint32(40, samples.length * bytesPerSample, true)

  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i]))
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    offset += bytesPerSample
  }

  return new Blob([view], { type: 'audio/wav' })
}

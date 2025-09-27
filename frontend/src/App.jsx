import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'

export default function App() {
  const [status, setStatus] = useState('idle')
  const [sessionId, setSessionId] = useState(null)
  const [transcript, setTranscript] = useState([])
  const [artifact, setArtifact] = useState(null)
  const pollRef = useRef(null)
  const lastSpokenIdxRef = useRef(0)
  const voicesReadyRef = useRef(false)

  const canStart = useMemo(() => status === 'idle' || status === 'completed', [status])

  const fetchTranscript = useCallback(async () => {
    const res = await axios.get('/api/transcript')
    setStatus(res.data.status)
    setSessionId(res.data.session_id)
    setTranscript(res.data.transcript || [])
    setArtifact(res.data.artifact || null)
    if (res.data.status === 'completed' && pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const start = useCallback(async () => {
    setStatus('running')
    setTranscript([])
    setArtifact(null)
    await axios.post('/api/start')
    // begin polling
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(fetchTranscript, 800)
    // immediate fetch
    fetchTranscript()
  }, [fetchTranscript])

  const reset = useCallback(async () => {
    await axios.post('/api/reset')
    setStatus('idle')
    setSessionId(null)
    setTranscript([])
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => {
    // load any existing state
    fetchTranscript()
    // preload voices
    const synth = window.speechSynthesis
    if (synth) {
      const onVoices = () => { voicesReadyRef.current = true }
      synth.onvoiceschanged = onVoices
      // trigger load
      synth.getVoices()
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [fetchTranscript])

  // TTS helpers
  const getVoiceForRole = useCallback((role) => {
    const synth = window.speechSynthesis
    if (!synth) return null
    const voices = synth.getVoices() || []
    const pickByName = (name) => voices.find(v => v.name.indexOf(name)>-1) || null
    if ((role || '').toLowerCase().includes('maylim')) {
      return pickByName('Microsoft Luna') || voices[0] || null
    }
    if ((role || '').toLowerCase().includes('kumar')) {
      // Prefer Tamil (Malaysia) voice for Kumar; fallback to first available
      return pickByName('Microsoft Kani') || voices[0] || null
    }
    if ((role || '').toLowerCase().includes('broker')) {
      return pickByName('Microsoft WanLung') || voices[0] || null
    }
    return voices[0] || null
  }, [])


  const speakLine = useCallback((text, role) => {
    const synth = window.speechSynthesis
    if (!synth || !text) return
    const u = new SpeechSynthesisUtterance(text)
    const voice = getVoiceForRole(role)
    if (voice) u.voice = voice
    u.rate = 1
    u.pitch = 1
    synth.speak(u)
  }, [getVoiceForRole])

  // Speak newly arrived transcript_response lines
  useEffect(() => {
    if (!window.speechSynthesis) return
    const startIdx = lastSpokenIdxRef.current
    if (startIdx >= transcript.length) return
    for (let i = startIdx; i < transcript.length; i++) {
      const m = transcript[i]
      if (m && m.transcript_response) {
        speakLine(m.transcript_response, m.role)
      }
    }
    lastSpokenIdxRef.current = transcript.length
  }, [transcript, speakLine])

  return (
    <div style={{ fontFamily: 'Inter, system-ui, Arial', margin: '24px' }}>
      <h2 style={{ marginBottom: 8 }}>A2A Agents Negotiation</h2>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16 }}>
        <button onClick={start} disabled={!canStart} style={{ padding: '8px 12px' }}>Start</button>
        <button onClick={reset} style={{ padding: '8px 12px' }}>Reset</button>
        <span>Status: <strong>{status}</strong></span>
        {sessionId && <span>Session: {sessionId}</span>}
      </div>

      <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 8 }}>Transcript</div>
        {transcript.length === 0 ? (
          <div style={{ color: '#666' }}>No messages yet.</div>
        ) : (
          <ol style={{ paddingLeft: 16, margin: 0 }}>
            {transcript.map((m, idx) => (
              <li key={idx} style={{ marginBottom: 8 }}>
                <div style={{ fontWeight: 600 }}>{m.role}</div>
                <div>{m.content}</div>
                {m.rationale && (
                  <div style={{ color: '#555', marginTop: 4 }}>
                    <em>Rationale:</em> {m.rationale}
                  </div>
                )}
                {m.transcript_response && (
                  <div style={{ color: '#0b5', marginTop: 4 }}>
                    <em>Speak:</em> {m.transcript_response}
                  </div>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>

      {artifact && (
        <div style={{ border: '1px solid #ddd', borderRadius: 8, padding: 12, marginTop: 12 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>Final Artifact</div>
          <div>Type: <strong>{artifact.type}</strong></div>
          <pre style={{ background: '#fafafa', padding: 8, borderRadius: 6, overflowX: 'auto' }}>
{JSON.stringify(artifact.data, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}



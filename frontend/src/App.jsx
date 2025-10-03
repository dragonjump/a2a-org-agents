import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import brokerImg from './broker.jpeg'
import kumarImg from './kumar.jpeg'
import mayleeImg from './maylee.jpeg'

import axios from 'axios'

export default function App() {
  const [speakingIdx, setSpeakingIdx] = useState(null)
  const [status, setStatus] = useState('idle')
  const [sessionId, setSessionId] = useState(null)
  const [transcript, setTranscript] = useState([])
  const [artifact, setArtifact] = useState(null)
  const pollRef = useRef(null)
  const lastSpokenIdxRef = useRef(0)
  const voicesReadyRef = useRef(false)
  const [voicesLoaded, setVoicesLoaded] = useState(false)

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
      const onVoices = () => {
        voicesReadyRef.current = true;
        setVoicesLoaded(true);
      };
      synth.onvoiceschanged = onVoices;
      // trigger load
      if (synth.getVoices().length > 0) {
        voicesReadyRef.current = true;
        setVoicesLoaded(true);
      } else {
        synth.getVoices();
      }
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
      return pickByName('Microsoft Valluvar') || voices[0] || null
    }
    if ((role || '').toLowerCase().includes('broker')) {
      return pickByName('Microsoft Wayne') || voices[0] || null
    }
    return voices[0] || null
  }, [])


  const speakLine = useCallback((text, role, idx) => {
    const synth = window.speechSynthesis
    if (!synth || !text || !voicesReadyRef.current) return
    if (synth.speaking || synth.pending) synth.cancel();
    setTimeout(() => {
      const u = new window.SpeechSynthesisUtterance(text)
      const voice = getVoiceForRole(role)
      if (voice) u.voice = voice
      u.rate = 1.35
      u.pitch = 1
      setSpeakingIdx(idx)
      u.onend = () => setSpeakingIdx(null)
      u.onerror = () => setSpeakingIdx(null)
      synth.speak(u)
    }, 100)
  }, [getVoiceForRole])

  // Speak newly arrived transcript_response lines
  useEffect(() => {
    if (!window.speechSynthesis || !voicesLoaded) return
    const startIdx = lastSpokenIdxRef.current
    if (startIdx >= transcript.length) return
    // Only speak the latest transcript_response
    for (let i = transcript.length - 1; i >= startIdx; i--) {
      const m = transcript[i]
      if (m && m.transcript_response) {
        speakLine(m.transcript_response, m.role, i)
        break
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
            {transcript.map((m, idx) => {
              let img = null;
              const role = (m.role || '').toLowerCase();
              if (role.includes('broker')) img = brokerImg;
              else if (role.includes('kumar')) img = kumarImg;
              else if (role.includes('maylim') || role.includes('maylee')) img = mayleeImg;
              const isSpeaking = speakingIdx === idx;
              return (
                <li key={idx} style={{ marginBottom: 8, display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                  {img && (
                    <div style={{ position: 'relative', width: 40, height: 40 }}>
                      <img
                        src={img}
                        alt={m.role}
                        style={{
                          width: isSpeaking ? 60 : 40,
                          height: isSpeaking ? 60 : 40,
                          borderRadius: '50%',
                          objectFit: 'cover',
                          border: isSpeaking ? '3px solid #0b5' : '1px solid #ccc',
                          boxShadow: isSpeaking ? '0 0 12px 4px #0b5a' : 'none',
                          transition: 'all 0.2s cubic-bezier(.4,2,.6,1)',
                          zIndex: isSpeaking ? 2 : 1,
                          animation: isSpeaking ? 'blink-border 0.7s linear infinite alternate' : 'none',
                        }}
                      />
                      {isSpeaking && (
                        <div style={{
                          position: 'absolute',
                          top: -10,
                          left: -10,
                          width: 80,
                          height: 80,
                          borderRadius: '50%',
                          border: '2px solid #0b5',
                          boxShadow: '0 0 16px 6px #0b5a',
                          background: 'rgba(11,181,85,0.08)',
                          zIndex: 1,
                          pointerEvents: 'none',
                        }} />
                      )}
                    </div>
                  )}
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600 }}>{m.role}</div>
                    <div>{m.content}</div>
                {m.rationale && (
                  <div style={{ color: '#555', marginTop: 4 }}>
                    <em>Rationale:</em> {m.rationale}
                  </div>
                )}
                {m.transcript_response && (
                  <div style={{ color: '#0b5', marginTop: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                    <em>Speak:</em> {m.transcript_response}
                    <button
                      style={{ marginLeft: 8, padding: '2px 8px', fontSize: 12 }}
                      onClick={() => speakLine(m.transcript_response, m.role, idx)}
                      title="Replay TTS for this line"
                    >
                      🔊 Replay
                    </button>
                  </div>
                )}
                  </div>
                </li>
              );
            })}
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



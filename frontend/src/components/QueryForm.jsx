import { useState, useEffect } from 'react'
import { PROVIDER_MODELS } from '../config'

export default function QueryForm({ onQuery, querying }) {
  const [text, setText] = useState('')
  const [provider, setProvider] = useState('')
  const [model, setModel] = useState('')

  useEffect(() => {
    const models = PROVIDER_MODELS[provider]
    setModel(models ? models[0] : '')
  }, [provider])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!text.trim() || !provider || !model) return
    await onQuery(text, provider, model)
    setText('')
  }

  const handleProviderChange = (e) => {
    setProvider(e.target.value)
  }

  const handleModelChange = (e) => {
    setModel(e.target.value)
  }

  return (
    <section>
      <h2>Ask a Question</h2>
      <form onSubmit={handleSubmit}>
        <label>
          Question:
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            size={60}
            required
          />
        </label>
        <label>
          LLM Provider:
          <select value={provider} onChange={handleProviderChange}>
            <option value="" disabled>Select a provider...</option>
            {Object.keys(PROVIDER_MODELS).map((p) => (
              <option key={p} value={p}>
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Model:
          <select value={model} onChange={handleModelChange} disabled={!provider}>
            {provider && PROVIDER_MODELS[provider].map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!text.trim() || !provider || !model || querying}>
          {querying ? 'Asking...' : 'Ask'}
        </button>
      </form>
    </section>
  )
}

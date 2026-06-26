import { useState } from 'react'
import { query, uploadFile, getCollectionInfo, clearDatabase } from './api'
import UploadForm from './components/UploadForm'
import QueryForm from './components/QueryForm'
import ClearDatabase from './components/ClearDatabase'
import AnswerDisplay from './components/AnswerDisplay'
import FlashMessage from './components/FlashMessage'

export default function App() {
  const [answer, setAnswer] = useState('')
  const [message, setMessage] = useState({ type: '', text: '' })
  const [uploading, setUploading] = useState(false)
  const [querying, setQuerying] = useState(false)
  const [clearing, setClearing] = useState(false)

  const showMessage = (type, text) => setMessage({ type, text })
  const dismissMessage = () => setMessage({ type: '', text: '' })

  const handleUpload = async (file, strategy) => {
    setUploading(true)
    try {
      await uploadFile(file, strategy)
      showMessage('success', `Uploaded "${file.name}" successfully.`)
    } catch (err) {
      showMessage('error', `Upload failed: ${err.message}`)
    } finally {
      setUploading(false)
    }
  }

  const handleQuery = async (text, provider, model) => {
    setQuerying(true)
    try {
      const data = await query(text, provider, model)
      setAnswer(data.answer)
    } catch (err) {
      setAnswer(`Error: ${err.message}`)
    } finally {
      setQuerying(false)
    }
  }

  const handleClear = async () => {
    const info = await getCollectionInfo()
    if (!confirm(`Clear collection '${info.name}'? It contains ${info.count} document(s).`)) return
    setClearing(true)
    try {
      const data = await clearDatabase()
      showMessage('success', `Cleared ${data.count} document(s).`)
    } catch (err) {
      showMessage('error', `Clear failed: ${err.message}`)
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="app">
      <h1>KnowMesh — Student RAG Assistant</h1>
      <FlashMessage type={message.type} text={message.text} onDismiss={dismissMessage} />
      <UploadForm onUpload={handleUpload} uploading={uploading} />
      <QueryForm onQuery={handleQuery} querying={querying} />
      <ClearDatabase onClear={handleClear} clearing={clearing} />
      <AnswerDisplay text={answer} />
    </div>
  )
}

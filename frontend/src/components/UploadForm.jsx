import { useState } from 'react'

export default function UploadForm({ onUpload, uploading }) {
  const [file, setFile] = useState(null)
  const [strategy, setStrategy] = useState('recursive')

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) return
    await onUpload(file, strategy)
    setFile(null)
  }

  return (
    <section>
      <h2>Upload Materials</h2>
      <form onSubmit={handleSubmit}>
        <label>
          File (.txt, .pdf, .docx, .pptx, images):
          <input
            type="file"
            onChange={(e) => setFile(e.target.files[0])}
            required
          />
        </label>
        <label>
          Strategy:
          <select value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            <option value="recursive">Recursive</option>
            <option value="semantic">Semantic</option>
          </select>
        </label>
        <button type="submit" disabled={!file || uploading}>
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
      </form>
    </section>
  )
}

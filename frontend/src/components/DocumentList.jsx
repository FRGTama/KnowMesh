import { useState } from 'react'

export default function DocumentList({ docs, onDelete }) {
  const [expandedId, setExpandedId] = useState(null)

  const toggleExpand = (docId) => {
    setExpandedId(expandedId === docId ? null : docId)
  }

  const handleDelete = (doc) => {
    if (window.confirm(`Delete "${doc.filename}" and its chunks?`)) {
      onDelete(doc.id)
    }
  }

  if (docs.length === 0) {
    return (
      <section>
        <h2>Documents</h2>
        <p style={{ color: '#888', fontSize: '0.875rem' }}>No documents uploaded yet.</p>
      </section>
    )
  }

  return (
    <section>
      <h2>Documents</h2>
      <div className="doc-list">
        {docs.map((doc) => (
          <div key={doc.id} className="doc-block">
            <span className="doc-name">{doc.filename}</span>
            <span className="doc-actions">
              <button title="View details" onClick={() => toggleExpand(doc.id)}>
                &#128065;
              </button>
              <button title="Delete" onClick={() => handleDelete(doc)}>
                &#128465;
              </button>
            </span>
            {expandedId === doc.id && (
              <div className="doc-expanded">
                <p><strong>Status:</strong> {doc.status}</p>
                <p><strong>Pages:</strong> {doc.total_pages}</p>
                <p><strong>Chunks:</strong> {doc.chunk_count}</p>
                <p><strong>Tags:</strong> {doc.tags.length > 0 ? doc.tags.join(', ') : 'None'}</p>
                <p><strong>Created:</strong> {doc.created_at}</p>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  )
}

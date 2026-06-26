export default function FlashMessage({ type, text, onDismiss }) {
  if (!text) return null

  return (
    <div className={`message ${type}`}>
      {text}
      {onDismiss && <button className="dismiss" onClick={onDismiss}>×</button>}
    </div>
  )
}

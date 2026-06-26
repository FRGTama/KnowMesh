export default function ClearDatabase({ onClear, clearing }) {
  return (
    <section>
      <h2>Database</h2>
      <button onClick={onClear} disabled={clearing}>
        {clearing ? 'Clearing...' : 'Clear Database'}
      </button>
    </section>
  )
}

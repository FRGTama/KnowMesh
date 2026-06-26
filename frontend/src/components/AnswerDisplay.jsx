export default function AnswerDisplay({ text }) {
  if (!text) return null

  return (
    <section>
      <h2>Answer</h2>
      <div className="answer">{text}</div>
    </section>
  )
}

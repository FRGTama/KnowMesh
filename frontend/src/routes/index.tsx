import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/')({
  component: () => (
    <div className="mx-auto max-w-4xl p-8">
      <h1 className="text-3xl font-bold">KnowMesh</h1>
      <p className="mt-2 text-gray-600">Student RAG Assistant</p>
    </div>
  ),
})
